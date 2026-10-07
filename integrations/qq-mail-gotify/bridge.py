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
from email import policy
from html.parser import HTMLParser
from pathlib import Path

CONFIG = Path(os.environ.get('CREDENTIALS_DIRECTORY', '/etc/qq-mail-gotify')) / 'config.json'
STATE = Path('/var/lib/qq-mail-gotify/state.json')
LABEL = r'(?:验证码|校验码|动态码|安全码|登录码|verification\s+code|security\s+code|one[-\s]time\s+(?:code|password)|OTP|passcode|login\s+code)'
AFTER = re.compile(LABEL + r'(?:\s*(?:is|为|是)\s*)?[\s:：=,，\-]*([A-Za-z0-9]{4,8})(?![A-Za-z0-9])', re.I)
BEFORE = re.compile(r'(?<![A-Za-z0-9])([A-Za-z0-9]{4,8})(?![A-Za-z0-9])(?:\s*(?:is|是|为|您的|your)\s*){0,4}' + LABEL, re.I)
LABEL_PATTERN = re.compile(LABEL, re.I)
STANDALONE_CODE = re.compile(r'[A-Za-z0-9]{4,8}')
INTRODUCTION = re.compile(r'\b(?:following|below)\b|如下|以下|下方', re.I)
CALENDAR_NUMBER = re.compile(r'(?:19|20)\d{2}(?:(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01]))?')


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if not self.hidden and tag in ('br', 'p', 'div', 'tr', 'td', 'li'): self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in ('p', 'div', 'tr', 'td', 'li'): self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


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


def code_from(text):
    # Normalize full-width ASCII without altering the original email body.
    normalized = ''.join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in text)
    codes = {m.group(1) for pattern in (AFTER, BEFORE) for m in pattern.finditer(normalized)
             if any(c.isdigit() for c in m.group(1))}
    # HTML emails often put the code in a separate paragraph after instructions,
    # e.g. "use the following verification code to complete the process:".
    # Only consider standalone tokens immediately after an explicit introduction;
    # never scan every number in an email or use a subject-only label as a hint.
    lines = normalized.splitlines()
    for index, line in enumerate(lines):
        label = LABEL_PATTERN.search(line)
        if not label or len(line) - label.end() > 160:
            continue
        if not (line.rstrip().endswith((':', '：')) or INTRODUCTION.search(line)):
            continue
        distance = 0
        for following in lines[index + 1:]:
            distance += len(following) + 1
            if distance > 160:
                break
            token = following.strip()
            if not token:
                continue
            if not STANDALONE_CODE.fullmatch(token):
                break
            if any(c.isdigit() for c in token) and not CALENDAR_NUMBER.fullmatch(token):
                codes.add(token)
    return next(iter(codes)) if len(codes) == 1 else ''


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(STATE)


def push(config, code, subject, sender, text):
    # Canonical title is also understood by the installed desktop extractor.
    title = '验证码：' + code
    content = f'{subject}\n发件人：{sender}\n\n{text}'
    payload = json.dumps({'title': title, 'message': content[:12000], 'priority': 5}).encode('utf-8')
    request = urllib.request.Request(config['gotify_url'].rstrip('/') + '/message', data=payload,
        headers={'Content-Type': 'application/json', 'X-Gotify-Key': config['gotify_token']})
    with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as reply:
        if reply.status != 200: raise RuntimeError('Gotify rejected message')


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
                text = body_text(message)
                code = code_from(subject + '\n' + text)
                if code:
                    push(config, code, subject, sender, text)
                    logging.info('Forwarded verification email UID=%s', uid)
                else:
                    logging.info('Skipped email without unique verification code UID=%s', uid)
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
