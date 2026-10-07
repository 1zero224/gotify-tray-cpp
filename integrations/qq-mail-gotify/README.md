# QQ verification email bridge

Optional Linux server companion for Gotify Tray++. It polls QQ IMAP over
verified TLS, forwards only emails containing one unambiguous verification code
to Gotify over HTTPS, and uses the canonical `验证码：<code>` title understood by
the desktop client. No extra Python dependencies are required (Python 3.10+).

## Recognition

The bridge recognizes Chinese and English labels with nearby 4–8 character
alphanumeric codes containing a digit. It also supports HTML emails that place
a standalone code in the next paragraph after an explicit instruction such as
`use the following verification code to complete the process:`. This fallback
has a 160-character boundary and stops at intervening prose; calendar values
are excluded. Different candidate codes cause the email to be skipped.

Ordinary emails and messages larger than 2 MB are not forwarded. The first run
initializes a mailbox cursor without forwarding historical emails. Keep the
state directory on upgrades: resetting it does not replay previously skipped
emails. Logs contain only UIDs and outcomes, not email content or credentials.

## Test

```sh
cd integrations/qq-mail-gotify
python3 -m unittest -v
```

The regression suite includes an anonymized quoted-printable HTML reproduction
of a separate-paragraph verification code, unrelated numbers, dates, and
ambiguous candidates. Do not commit real mail samples or authorization codes.

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
