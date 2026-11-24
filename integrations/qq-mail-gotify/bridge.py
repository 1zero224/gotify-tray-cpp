#!/usr/bin/env python3
"""QQ IMAP to Gotify bridge. Uses only the Python standard library."""
import email
import html
import imaplib
import json
import logging
import os
import re
import ssl
import time
import urllib.request
from bisect import bisect_right
from dataclasses import dataclass
from email import policy
from html.parser import HTMLParser
from pathlib import Path

CONFIG = Path(os.environ.get('CREDENTIALS_DIRECTORY', '/etc/qq-mail-gotify')) / 'config.json'
STATE = Path('/var/lib/qq-mail-gotify/state.json')

# --- Recognition -----------------------------------------------------------
LABEL = (r'(?:验证码|校验码|动态码|安全码|登录码|verification\s+code|confirmation\s+code|'
         r'security\s+code|one[-\s]time\s+(?:code|password)|OTP|passcode|login\s+code)')
LABEL_PATTERN = re.compile(LABEL, re.I)
# Code placed before the label: "123456 is your verification code".
BEFORE = re.compile(
    r'(?<![A-Za-z0-9])([A-Za-z0-9]{4,8})(?![A-Za-z0-9])'
    r'(?:\s*(?:is|是|为|您的|your)\s*){0,4}' + LABEL, re.I)
INTRODUCTION = re.compile(r'\b(?:following|below)\b|如下|以下|下方', re.I)
# Every 4-8 character alphanumeric token is a candidate; scoring decides.
TOKEN = re.compile(r'(?<![A-Za-z0-9])([A-Za-z0-9]{4,8})(?![A-Za-z0-9])')
# Codes forwarded inline may be split into groups ("123 456" / "123-456").
GROUPED = re.compile(r'(?<!\d)(?:\d{3,5}[\- \t　]{1,2}){1,2}\d{3,5}(?!\d)')
NEGATIVE = re.compile(
    r'(?:order|invoice|receipt|shipment|tracking|amount|balance|phone|telephone|'
    r'订单|金额|余额|手机|电话|物流|发货)', re.I)
CSS_UNIT = re.compile(r'\d+(?:px|pt|em|rem|vh|vw)', re.I)
YEAR = re.compile(r'(?:19|20)\d{2}')
CALENDAR = re.compile(r'(?:19|20)\d{6}')
STANDALONE = re.compile(r'[A-Za-z0-9]{4,8}(?:[\- \t　][A-Za-z0-9]{3,5})*')
VALIDITY = re.compile(
    r'(?:有效期(?:为)?\s*)?\d{1,3}\s*(?:分钟|minutes?)(?:内|后)?\s*(?:有效|失效)?', re.I)
SCORE_THRESHOLD = 50
MAX_CANDIDATES = 2
BLOCK_TAGS = frozenset({'br', 'p', 'div', 'tr', 'td', 'li', 'h1', 'h2', 'h3', 'h4',
                        'table', 'section', 'article'})
VOID_TAGS = frozenset({'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'area',
                       'base', 'col', 'embed', 'param', 'track', 'wbr'})


@dataclass(frozen=True)
class Candidate:
    code: str
    score: int
    position: int


def _emphasized(tag, attrs):
    """True when the element's own text is visually presented as a code."""
    style = ''
    hints = ''
    for key, value in attrs:
        if not value:
            continue
        if key == 'style':
            style += value.lower()
        elif key in ('class', 'id'):
            hints += ' ' + value.lower()
    if tag in ('b', 'strong', 'h1', 'h2', 'h3'):
        return True
    if re.search(r'font-family\s*:[^;"]*(?:mono|courier|consolas|menlo)', style):
        return True
    if 'letter-spacing' in style and not re.search(
            r'letter-spacing\s*:\s*(?:normal|0(?:\.0+)?(?:px|em|rem|pt)?)\s*(?:;|$)', style):
        return True
    size = re.search(r'font-size\s*:\s*(\d+(?:\.\d+)?)\s*(px|pt|em|rem)', style)
    if size:
        value, unit = float(size.group(1)), size.group(2)
        if ((unit == 'px' and value >= 24) or (unit == 'pt' and value >= 18)
                or (unit in ('em', 'rem') and value >= 1.5)):
            return True
    return bool(re.search(r'(?:^|[\s_-])(?:otp|code|pin|verification)(?:$|[\s_-])', hints))


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.emphasized = set()
        self.hidden = 0
        self._stack = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
            return
        if not self.hidden and tag in BLOCK_TAGS:
            self.parts.append('\n')
        if tag in VOID_TAGS:
            return
        self._stack.append([tag, not self.hidden and _emphasized(tag, attrs), []])

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag in BLOCK_TAGS:
            self.parts.append('\n')
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] != tag:
                continue
            _, emphasized, parts = self._stack.pop(index)
            token = re.sub(r'[\- \t　]', '', ''.join(parts).strip())
            if emphasized and TOKEN.fullmatch(token):
                self.emphasized.add(token)
            break

    def handle_data(self, data):
        if self.hidden:
            return
        self.parts.append(data)
        for frame in self._stack:
            frame[2].append(data)


def body_text(message):
    part = message.get_body(preferencelist=('plain', 'html'))
    if part is None: return ''
    text = part.get_content()
    if part.get_content_type() == 'text/html':
        parser = PlainHTML()
        parser.feed(text)
        text = ''.join(parser.parts)
    text = html.unescape(text).replace('\r\n', '\n')
    return re.sub(r'\n[\t ]*\n(?:[\t ]*\n)+', '\n\n', text).strip()


def email_content(message):
    """Return the flattened body plus tokens styled as codes in the HTML part."""
    text = body_text(message)
    emphasized = set()
    part = message.get_body(preferencelist=('html',))
    if part is not None and part.get_content_type() == 'text/html':
        parser = PlainHTML()
        try:
            parser.feed(part.get_content())
            parser.close()
        except Exception:
            return text, emphasized
        emphasized = parser.emphasized
    return text, emphasized


def _normalize(text):
    # Normalize full-width ASCII without altering the original email body.
    return ''.join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in text)


def _gap_ok(gap):
    """Between a label and its code only punctuation, whitespace and a copula."""
    if len(gap) > 24 or NEGATIVE.search(gap):
        return False
    if not re.search(r'[A-Za-z0-9]', gap):
        return True
    return re.fullmatch(r'[^A-Za-z0-9]{0,12}(?:is|为|是)[^A-Za-z0-9]{0,12}', gap, re.I) is not None


def _candidates(text):
    spans = []
    for match in GROUPED.finditer(text):
        raw = match.group(0)
        spans.append((match.start(), match.end(), raw, re.sub(r'[\- \t　]', '', raw)))
    for match in TOKEN.finditer(text):
        start, end = match.span()
        if any(start < other_end and other_start < end for other_start, other_end, _, _ in spans):
            continue
        spans.append((start, end, match.group(1), match.group(1)))
    spans.sort()
    return spans


def _rejected(text, start, end, code):
    if not any(ch.isdigit() for ch in code):
        return True
    if not 4 <= len(code) <= 8 or len(set(code)) == 1:
        return True
    if YEAR.fullmatch(code) or CALENDAR.fullmatch(code) or CSS_UNIT.fullmatch(code):
        return True
    before = text[start - 1] if start else ''
    if before and before in '¥$€£￥':
        return True
    after = text[end:end + 1]
    if after == '@' or after == '%':
        return True
    if re.match(r'[-/.:]\d', text[end:end + 3]):
        return True
    prefix = text[max(0, start - 24):start]
    return '://' in prefix or 'www.' in prefix.lower()


def _intro_bonus(lines, offsets, line_index, start):
    """An explicit introduction line ("... code:") directly above a bare code."""
    anchor = line_index - 1
    while anchor >= 0:
        line = lines[anchor].strip()
        if not line:
            anchor -= 1
            continue
        if STANDALONE.fullmatch(line):
            anchor -= 1
            continue
        label = LABEL_PATTERN.search(lines[anchor])
        if not label:
            return 0
        if not (lines[anchor].rstrip().endswith((':', '：')) or INTRODUCTION.search(lines[anchor])):
            return 0
        if len(lines[anchor]) - label.end() > 160:
            return 0
        if start - (offsets[anchor] + len(lines[anchor])) > 160:
            return 0
        return 20
    return 0


def _score(text, lines, offsets, start, end, raw, code, emphasized, labels, before_starts):
    line_index = bisect_right(offsets, start) - 1
    standalone = 0 <= line_index < len(lines) and lines[line_index].strip() == raw
    score = 0
    labelled = False
    for label_end in labels:
        if 0 <= start - label_end <= 24 and _gap_ok(text[label_end:start]):
            score += 40
            labelled = True
            break
    if not labelled and start in before_starts:
        score += 40
        labelled = True
    if code in emphasized:
        score += 25
    if standalone:
        score += 20 + _intro_bonus(lines, offsets, line_index, start)
    if code.isdigit():
        score += 5
    if len(code) == 6:
        score += 10
    elif len(code) == 8:
        score += 5
    if not labelled and code not in emphasized:
        window = text[max(0, start - 24):min(len(text), end + 24)]
        if NEGATIVE.search(window):
            score -= 25
    return score


def rank_codes(text, emphasized=frozenset()):
    """Score every plausible code token; return candidates at or above threshold."""
    text = _normalize(VALIDITY.sub(' ', text))
    lines = text.split('\n')
    offsets = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line) + 1
    labels = [match.end() for match in LABEL_PATTERN.finditer(text)]
    before_starts = set()
    for match in BEFORE.finditer(text):
        token = match.group(1)
        # A product name with a digit ("Prove2Me") must not become a candidate.
        if any(ch.isdigit() for ch in token) and not re.search(r'[a-z]', token):
            before_starts.add(match.start(1))
    best = {}
    for start, end, raw, code in _candidates(text):
        if _rejected(text, start, end, code):
            continue
        score = _score(text, lines, offsets, start, end, raw, code, emphasized, labels, before_starts)
        if score < SCORE_THRESHOLD:
            continue
        current = best.get(code)
        if current is None or score > current[0]:
            best[code] = (score, start)
    ranked = sorted(((score, start, code) for code, (score, start) in best.items()),
                    key=lambda item: (-item[0], item[1]))
    return [Candidate(code, score, start) for score, start, code in ranked]


def code_from(text, emphasized=frozenset()):
    """The unique code, or an empty string when there is none or it is ambiguous."""
    ranked = rank_codes(text, emphasized)
    return ranked[0].code if len(ranked) == 1 else ''


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE)


def push(config, title, content):
    payload = json.dumps({'title': title, 'message': content[:12000], 'priority': 5}).encode('utf-8')
    request = urllib.request.Request(config['gotify_url'].rstrip('/') + '/message', data=payload,
        headers={'Content-Type': 'application/json', 'X-Gotify-Key': config['gotify_token']})
    with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as reply:
        if reply.status != 200: raise RuntimeError('Gotify rejected message')


def push_email(config, code, subject, sender, text):
    # Canonical title is also understood by the installed desktop extractor.
    push(config, '验证码：' + code, f'{subject}\n发件人：{sender}\n\n{text}')


def push_ambiguous(config, codes, subject, sender, text):
    # Desktop shows both candidates but does not offer one-click copy.
    title = '验证码候选：' + ' / '.join(codes)
    leading = '检测到多个候选，请核对后复制：' + ' / '.join(codes)
    push(config, title, f'{leading}\n\n{subject}\n发件人：{sender}\n\n{text}')


def poll(config):
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    with imaplib.IMAP4_SSL('imap.qq.com', 993, ssl_context=ssl.create_default_context(), timeout=20) as mailbox:
        mailbox.login(config['email'], config['authorization_code'])
        status, _ = mailbox.select('INBOX', readonly=True)
        if status != 'OK': raise RuntimeError('Cannot select inbox')
        validity = mailbox.response('UIDVALIDITY')[1][0].decode()
        next_uid = int(mailbox.response('UIDNEXT')[1][0])
        if state.get('uidvalidity') != validity:
            save_state({'uidvalidity': validity, 'last_uid': next_uid - 1})
            logging.info('Initialized mailbox baseline; historical emails excluded')
            return
        first_uid = state['last_uid'] + 1
        if first_uid >= next_uid: return
        status, data = mailbox.uid('search', None, 'UID', f'{first_uid}:{next_uid - 1}')
        if status != 'OK': raise RuntimeError('UID search failed')
        for raw_uid in data[0].split():
            uid = int(raw_uid)
            if uid < first_uid: continue
            status, size_data = mailbox.uid('fetch', raw_uid, '(RFC822.SIZE)')
            if status != 'OK': raise RuntimeError('Size fetch failed')
            size = re.search(rb'RFC822.SIZE\s+(\d+)', b' '.join(x for x in size_data if isinstance(x, bytes)))
            if size is None: raise RuntimeError('Missing message size')
            if int(size.group(1)) > 2_000_000:
                logging.info('Skipped oversized email UID=%s', uid)
            else:
                status, data = mailbox.uid('fetch', raw_uid, '(BODY.PEEK[])')
                if status != 'OK': raise RuntimeError('Message fetch failed')
                chunks = [x[1] for x in data if isinstance(x, tuple)]
                if not chunks: raise RuntimeError('Missing email body')
                message = email.message_from_bytes(b''.join(chunks), policy=policy.default)
                subject = str(message.get('Subject', ''))
                sender = str(message.get('From', ''))
                text, emphasized = email_content(message)
                ranked = rank_codes(subject + '\n' + text, emphasized)
                if len(ranked) == 1:
                    push_email(config, ranked[0].code, subject, sender, text)
                    logging.info('Forwarded verification email UID=%s', uid)
                elif ranked:
                    codes = [candidate.code for candidate in ranked[:MAX_CANDIDATES]]
                    push_ambiguous(config, codes, subject, sender, text)
                    logging.info('Forwarded ambiguous verification email UID=%s', uid)
                else:
                    logging.info('Skipped email without verification code UID=%s', uid)
            state['last_uid'] = uid
            save_state(state)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    for key in ('email', 'authorization_code', 'gotify_url', 'gotify_token'):
        if not config.get(key): raise RuntimeError('Missing configuration: ' + key)
    if not config['gotify_url'].startswith('https://'): raise RuntimeError('Gotify must use HTTPS')
    while True:
        try:
            poll(config)
        except Exception as error:
            # Do not log exception details: server replies may contain credentials or email content.
            logging.error('Mail bridge operation failed (%s); retrying', type(error).__name__)
        time.sleep(max(15, int(config.get('poll_seconds', 30))))


if __name__ == '__main__': main()
