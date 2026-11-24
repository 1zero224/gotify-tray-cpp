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
        self.assertEqual(bridge.code_from('A1B2C3 is your confirmation code'), 'A1B2C3')

    def test_leading_ignores_brand_names(self):
        # "Prove2Me" contains a digit but is a product name, not a code.
        self.assertEqual(bridge.code_from('Prove2Me Your confirmation code:\n630279\nIt expires in 1 hour.'), '630279')

    def test_full_width(self):
        self.assertEqual(bridge.code_from('验证码：１２３４５６'), '123456')

    def test_ambiguous(self):
        self.assertEqual(bridge.code_from('验证码：123456，验证码：654321'), '')

    def test_ambiguous_candidates_are_returned(self):
        # P0: ambiguous mail must still expose its candidates instead of vanishing.
        ranked = bridge.rank_codes('验证码：123456，验证码：654321')
        self.assertEqual([candidate.code for candidate in ranked], ['123456', '654321'])
        self.assertEqual(bridge.rank_codes('订单号123456'), [])

    def test_grouped_code(self):
        self.assertEqual(bridge.code_from('【OPPO】验证码 123 456 用于登录'), '123456')
        self.assertEqual(bridge.code_from('【OPPO】验证码：123-456，请勿泄露。'), '123456')

    def test_validity_phrase_between_label_and_code(self):
        self.assertEqual(bridge.code_from('【OPPO】验证码（5分钟内有效）：123456'), '123456')
        self.assertEqual(bridge.code_from('【OPPO】登录验证码有效期10分钟：654321'), '654321')

    def test_label_after_copula(self):
        self.assertEqual(bridge.code_from('Your confirmation code is 630279.'), '630279')

    def test_css_and_invoice_values_are_not_codes(self):
        self.assertEqual(bridge.code_from('body { font-size: 32px; color: #f3f4f6; }'), '')
        self.assertEqual(bridge.code_from('Invoice 123456 is ready'), '')

    def test_excluded_field_between_label_and_code(self):
        self.assertEqual(bridge.code_from('验证码错误，订单号123456已发货。'), '')
        self.assertEqual(bridge.code_from('验证码已发送至手机 13800138000，请查收。'), '')

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

    def test_html_emphasis_without_label(self):
        # P2: a code styled as its own large/spaced element is a structural signal.
        message = email.message_from_bytes(
            b'Subject: Signup\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'
            b'<div style="font-size:32px;letter-spacing:6px">630279</div>',
            policy=policy.default)
        text, emphasized = bridge.email_content(message)
        self.assertIn('630279', emphasized)
        self.assertEqual(bridge.code_from(text, emphasized), '630279')

    def test_html_emphasis_requires_isolated_element(self):
        message = email.message_from_bytes(
            b'Subject: Signup\r\nContent-Type: text/html; charset=utf-8\r\n\r\n'
            b'<div style="font-size:32px">Use 630279 now</div>',
            policy=policy.default)
        text, emphasized = bridge.email_content(message)
        self.assertEqual(emphasized, set())
        self.assertEqual(bridge.code_from(text, emphasized), '')

    def test_confirmation_code_label(self):
        # Anonymized Prove2Me layout: the code follows the label as a paragraph.
        text = ('Prove2Me Your confirmation code:\n630279\n'
                'Enter it on the sign in page, or give it to your agent. '
                'It expires in 1 hour. Only the newest code works. Not you? Ignore this email.')
        self.assertEqual(bridge.code_from('Confirm your Prove2Me Signup\n' + text), '630279')


if __name__ == '__main__': unittest.main()
