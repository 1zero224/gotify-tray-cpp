import email
import unittest
from email import policy
import bridge


class BridgeTests(unittest.TestCase):
    def test_chinese(self):
        self.assertEqual(bridge.code_from('您的验证码是：123456，有效期15分钟'), '123456')

    def test_english(self):
        self.assertEqual(bridge.code_from('Your verification code is 123456.'), '123456')

    def test_leading(self):
        self.assertEqual(bridge.code_from('123456 is your verification code'), '123456')

    def test_full_width(self):
        self.assertEqual(bridge.code_from('验证码：１２３４５６'), '123456')

    def test_ambiguous(self):
        self.assertEqual(bridge.code_from('验证码：123456，验证码：654321'), '')

    def test_ordinary(self):
        self.assertEqual(bridge.code_from('订单号123456，手机号13800000000'), '')
        self.assertEqual(bridge.code_from('Verification code expired'), '')

    def test_html(self):
        message = email.message_from_bytes(b'Subject: Login\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<style>OTP: 999999</style><p>Your verification code is <b>123456</b>.</p>', policy=policy.default)
        self.assertEqual(bridge.code_from(bridge.body_text(message)), '123456')

    def test_mime(self):
        from email.message import EmailMessage
        message = EmailMessage()
        message.set_content('Your verification code is 123456')
        message.add_alternative('<p>Your verification code is 123456</p>', subtype='html')
        message.add_attachment(b'OTP: 999999', maintype='application', subtype='octet-stream', filename='test.txt')
        self.assertEqual(bridge.code_from(bridge.body_text(message)), '123456')

    def test_seagm_quoted_printable_html(self):
        # Minimal anonymized reproduction of the user-provided MIME structure.
        from email.message import EmailMessage
        message = EmailMessage()
        message['Subject'] = 'Your Email Verification Code'
        message.set_content('''<table><tr><td><div>
<p>Dear user. We have received a request to verify your email address.
Please use the following verification code to complete the process:</p>
<p><b style="font-size:2em;letter-spacing:.1em;"> 123456</b></p>
<p>This code will expire on 2026-10-07 at 01:27:33 (UTC+8).
If you did not request this verification, please disregard this email.</p>
</div><p>Example Company (7654321-K)<br>69 Example Road, 32000 City</p>
</td></tr></table>''', subtype='html', charset='utf-8', cte='quoted-printable')
        parsed = email.message_from_bytes(message.as_bytes(), policy=policy.default)
        self.assertEqual(parsed['Content-Transfer-Encoding'], 'quoted-printable')
        self.assertEqual(bridge.code_from(str(parsed['Subject']) + '\n' + bridge.body_text(parsed)), '123456')

    def test_separate_paragraph(self):
        self.assertEqual(bridge.code_from('Use the following verification code to sign in:\n\n123456\n\nExpires in 15 minutes.'), '123456')
        self.assertEqual(bridge.code_from('您的验证码如下：\n\n１２３４５６'), '123456')
        self.assertEqual(bridge.code_from('Use the following security code:\nA1B2C3'), 'A1B2C3')

    def test_paragraph_candidates_must_be_unique(self):
        self.assertEqual(bridge.code_from('Use the following verification code:\n123456\n654321'), '')
        self.assertEqual(bridge.code_from('验证码：654321\nUse the following verification code:\n123456'), '')
        self.assertEqual(bridge.code_from('验证码：123456\nUse the following verification code:\n123456'), '123456')
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n123456\n123456\n123456\n654321'), '')

    def test_paragraph_requires_explicit_nearby_context(self):
        self.assertEqual(bridge.code_from('Your Email Verification Code\nOrder number\n123456'), '')
        self.assertEqual(bridge.code_from('Verification code expired\n123456'), '')
        self.assertEqual(bridge.code_from('Use the following verification code:\nUnrelated order details\n123456'), '')
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n' + '\n' * 161 + '123456'), '')
        self.assertEqual(bridge.code_from('Use the following verification code ' + 'x' * 161 + ':\n123456'), '')

    def test_paragraph_does_not_use_calendar_values(self):
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n2026'), '')
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n20261007'), '')
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n2026-10-07\n01:27:33'), '')

    def test_paragraph_does_not_use_footer_numbers(self):
        self.assertEqual(bridge.code_from('Use the following verification code to continue:\n\nFor security reasons, do not share this code.\n32000'), '')


if __name__ == '__main__': unittest.main()
