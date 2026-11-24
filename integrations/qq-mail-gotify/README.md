# QQ verification email bridge

Optional Linux server companion for Gotify Tray++. It polls QQ IMAP over
verified TLS, forwards only emails containing one unambiguous verification code
to Gotify over HTTPS, and uses the canonical `验证码：<code>` title understood by
the desktop client. No extra Python dependencies are required (Python 3.10+).

## Recognition

Recognition is two-staged. Every 4–8 character alphanumeric token (including
grouped forms such as `123 456` and `123-456`) becomes a candidate; candidates
are then scored by nearby label, a standalone paragraph after an introduction
line, HTML styling (`letter-spacing`, large font size, monospace, `<b>`), code
length, and negative context such as invoice, order, amount or phone numbers.
Calendar values, CSS lengths, URLs and repeated digits are discarded.

Exactly one candidate above the threshold is forwarded with the canonical
`验证码：<code>` title. When several candidates qualify the bridge forwards them
as `验证码候选：A / B` instead of dropping the email; the desktop shows both
candidates but offers no one-click copy. Emails without any candidate are
skipped. The introduction-line fallback keeps a 160-character boundary and
stops at intervening prose.

Ordinary emails and messages larger than 2 MB are not forwarded. The first run
initializes a mailbox cursor without forwarding historical emails. Keep the
state directory on upgrades: resetting it does not replay previously skipped
emails. Logs contain only UIDs and outcomes, not email content, candidate codes
or credentials.

## Test

```sh
cd integrations/qq-mail-gotify
python3 -m unittest -v
```

The regression suite includes anonymized reproductions of separate-paragraph
codes, codes styled with `letter-spacing`/large fonts, inline grouped codes,
unrelated numbers, dates, CSS values, invoice amounts, and ambiguous candidates.
Do not commit real mail samples or authorization codes.

## Deployment

Copy `bridge.py` to `/opt/qq-mail-gotify/bridge.py` and the provided systemd unit
to `/etc/systemd/system/qq-mail-gotify.service`. Create a root-owned private
directory `/etc/qq-mail-gotify` (mode `0700`) and a `config.json` (mode `0600`)
using a secure editor on the server:

```json
{
  "email": "YOUR_QQ_MAILBOX",
  "authorization_code": "YOUR_QQ_IMAP_AUTHORIZATION_CODE",
  "gotify_url": "https://YOUR_GOTIFY_SERVER",
  "gotify_token": "YOUR_SEND_ONLY_APPLICATION_TOKEN",
  "poll_seconds": 30
}
```

Use the QQ IMAP authorization code, not the account password. The unit uses
systemd credentials, a dynamic user, and a private persistent state directory.
Activate it with `systemctl daemon-reload` and
`systemctl enable --now qq-mail-gotify.service` (as root). For upgrades, back up
the existing source, replace only `bridge.py`, and restart the service; leave
the configuration and `/var/lib/qq-mail-gotify/state.json` unchanged.

Inspect `systemctl status qq-mail-gotify.service` and
`journalctl -u qq-mail-gotify.service`. A skipped UID means the message was
examined but no unique code was recognized; no new log entries during idle
polls is normal. A transient network failure is retried on the next poll.

TLS encrypts each network connection; this is not end-to-end encryption. QQ,
the bridge, and the Gotify server can process the plaintext email content.
