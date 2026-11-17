#include "verificationcode.h"
#include <QCoreApplication>
#include <QTextStream>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    struct Case { QString title; QString message; QString expected; };
    const Case cases[] = {
        {QString::fromUtf8("验证码：123456"),
         QString::fromUtf8("部署验证：测试通知（非真实登录验证码）\n发件人：server deployment test\n\nDeployment test only. Use the following verification code to complete the process:\n\n123456\n\nThis is not a real login code."),
         QStringLiteral("123456")},
        {QString::fromUtf8("验证码：123456"),
         QStringLiteral("Your Email Verification Code\nFrom: sender\nPlease use the following verification code to complete the process:\n123456\nExpires on 2026-10-07 at 01:27:33."),
         QStringLiteral("123456")},
        {QString::fromUtf8("验证码：１２３４５６"), QStringLiteral("server deployment test"), QStringLiteral("123456")},
        {QString::fromUtf8("验证码：A1B2C3"), QStringLiteral("server deployment test"), QStringLiteral("A1B2C3")},
        {QStringLiteral("Login"), QString::fromUtf8("您的验证码：123456，有效期15分钟。"), QStringLiteral("123456")},
        {QStringLiteral("Order"), QString::fromUtf8("订单号123456"), {}},
        {QStringLiteral("Login"), QString::fromUtf8("验证码：123456，验证码：654321"), {}},
        {QString::fromUtf8("验证码：123456 extra"), QString::fromUtf8("验证码：654321"), {}},
        // OPPO/ColorOS-style SMS: the excluded-field words ("手机号", "订单号",
        // "时间") appear in the sentence but not between the label and the code.
        {QStringLiteral("SMS"),
         QString::fromUtf8("【OPPO】您正在绑定手机号，验证码：123456，5分钟内有效。请勿泄露。"),
         QStringLiteral("123456")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("【OPPO】验证码 123 456 用于登录您的OPPO账号。"),
         QStringLiteral("123456")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("【OPPO】验证码：123-456，请勿泄露给他人。"),
         QStringLiteral("123456")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("您于12:30登录，验证码：123456（11:18前有效）。"),
         QStringLiteral("123456")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("【OPPO】验证码（5分钟内有效）：123456"),
         QStringLiteral("123456")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("【OPPO】登录验证码有效期10分钟：654321，请勿泄露。"),
         QStringLiteral("654321")},
        {QStringLiteral("SMS"),
         QString::fromUtf8("验证码错误，订单号123456已发货。"),
         {}},
        {QStringLiteral("SMS"),
         QString::fromUtf8("验证码已发送至手机 13800138000，请查收。"),
         {}},
    };
    const int count = int(sizeof(cases) / sizeof(cases[0]));
    QTextStream output(stdout);
    for (int i = 0; i < count; ++i) {
        if (VerificationCode::extract(cases[i].title, cases[i].message) != cases[i].expected) {
            output << "Verification code regression failed: case " << i << Qt::endl;
            return 1;
        }
    }
    output << "Verification code regression: " << count << " cases passed" << Qt::endl;
    return 0;
}
