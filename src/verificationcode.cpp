#include "verificationcode.h"

#include <QRegularExpression>
#include <QVector>
#include <algorithm>

namespace {

struct Candidate {
    QString code;
    int score = 0;
    int position = 0;
};

QString normalize(QString text)
{
    const QString fullWidth = QStringLiteral("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ");
    const QString ascii = QStringLiteral("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz");
    for (int i = 0; i < fullWidth.size(); ++i)
        text.replace(fullWidth.at(i), ascii.at(i));
    const QString arabicIndic = QStringLiteral("٠١٢٣٤٥٦٧٨٩");
    for (int i = 0; i < arabicIndic.size(); ++i)
        text.replace(arabicIndic.at(i), QChar(static_cast<ushort>('0' + i)));
    const QString easternArabicIndic = QStringLiteral("۰۱۲۳۴۵۶۷۸۹");
    for (int i = 0; i < easternArabicIndic.size(); ++i)
        text.replace(easternArabicIndic.at(i), QChar(static_cast<ushort>('0' + i)));
    return text;
}

bool hasExcludedPrefix(const QString &text, int start)
{
    const QString prefix = text.mid(qMax(0, start - 28), 28);
    static const QRegularExpression excluded(
        QStringLiteral("(?:电话|手机|手机号|订单|订单号|物流|金额|余额|日期|时间|phone|telephone|order|invoice|amount|balance|date|time)"),
        QRegularExpression::CaseInsensitiveOption);
    return excluded.match(prefix).hasMatch();
}

bool looksLikePhoneOrDate(const QString &text, int start, int length)
{
    const QString value = text.mid(start, length);
    const QString around = text.mid(qMax(0, start - 8), length + 16);
    if (value.size() >= 9)
        return true;
    if (QRegularExpression(QStringLiteral("(?:20\\d{2}[-/.])?\\d{1,2}[-/.]\\d{1,2}"))
            .match(around).hasMatch())
        return true;
    return QRegularExpression(QStringLiteral("\\d{1,2}:\\d{2}"))
        .match(around).hasMatch();
}

}

QString VerificationCode::extract(const QString &title, const QString &message)
{
    // The mail bridge emits this exact title only after resolving a unique code.
    // Do not let English words in the forwarded subject/body override that code.
    static const QRegularExpression canonicalTitle(
        QStringLiteral("^验证码[：:]\\s*([A-Za-z0-9]{4,8})$"));
    const auto canonical = canonicalTitle.match(normalize(title).trimmed());
    if (canonical.hasMatch() && canonical.captured(1).contains(QRegularExpression(QStringLiteral("[0-9]"))))
        return canonical.captured(1);

    const QString text = normalize(title + QStringLiteral("\n") + message);
    QVector<Candidate> candidates;

    // Domain-bound SMS format used by Apple: @example.com #123456.
    static const QRegularExpression domainBound(
        QStringLiteral("@[A-Za-z0-9.-]+\\s+#([A-Za-z0-9]{4,10})"));
    QRegularExpressionMatchIterator it = domainBound.globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        candidates.append({match.captured(1), 110, match.capturedStart(1)});
    }

    static const QRegularExpression labeled(
        QStringLiteral("(?:验证码|校验码|动态码|确认码|安全码|登录码|验证代码|提取码|授权码|短信码|認証コード|確認コード|"
                       "verification\\s+code|security\\s+code|one[- ]time\\s+(?:password|code)|"
                       "otp|passcode|auth(?:entication)?\\s+code|login\\s+code)"
                       "[^A-Za-z0-9]{0,24}([A-Za-z0-9]{4,10})(?![A-Za-z0-9])"),
        QRegularExpression::CaseInsensitiveOption);
    it = labeled.globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        const int start = match.capturedStart(1);
        const QString code = match.captured(1);
        if (!looksLikePhoneOrDate(text, start, code.size()) && !hasExcludedPrefix(text, match.capturedStart()))
            candidates.append({code, 100 + (code.size() == 6 ? 5 : 0), start});
    }

    // Also accept "123456 是您的验证码" style messages.
    static const QRegularExpression trailingLabel(
        QStringLiteral("(?<![A-Za-z0-9])([A-Za-z0-9]{4,10})(?![A-Za-z0-9])"
                       "[^\\n]{0,24}(?:验证码|校验码|动态码|确认码|安全码|登录码|"
                       "verification\\s+code|security\\s+code|otp|passcode)"),
        QRegularExpression::CaseInsensitiveOption);
    it = trailingLabel.globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        const int start = match.capturedStart(1);
        const QString code = match.captured(1);
        if (!looksLikePhoneOrDate(text, start, code.size()) && !hasExcludedPrefix(text, start))
            candidates.append({code, 90 + (code.size() == 6 ? 5 : 0), start});
    }

    if (candidates.isEmpty())
        return {};
    std::sort(candidates.begin(), candidates.end(), [](const Candidate &a, const Candidate &b) {
        if (a.score != b.score)
            return a.score > b.score;
        return a.position > b.position;
    });
    if (candidates.size() > 1 && candidates.at(0).code != candidates.at(1).code &&
        candidates.at(0).score - candidates.at(1).score < 10)
        return {};
    return candidates.first().code;
}
