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

const QString &labelPattern()
{
    // "验证码" is a substring of "短信验证码"/"登录验证码", so it is implied by the first entry.
    static const QString pattern = QStringLiteral(
        "验证码|校验码|校验代码|动态码|动态密码|确认码|确认代码|认证码|安全码|登录码|"
        "验证代码|提取码|授权码|短信码|一次性密码|認証コード|確認コード|"
        "verification\\s+code|security\\s+code|one[- ]time\\s+(?:password|code)|"
        "otp|passcode|auth(?:entication)?\\s+code|login\\s+code");
    return pattern;
}

const QString &codePattern()
{
    // Codes forwarded inline may be split into groups ("123 456" / "123-456").
    // Groups are kept short so 11-digit phone numbers cannot match as a whole.
    static const QString pattern = QStringLiteral(
        "(?:(?:\\d{3,5}[\\- \\t　－]{1,2}){1,2}\\d{3,5}|[A-Za-z0-9]{4,10})");
    return pattern;
}

const QRegularExpression &labeledPattern()
{
    static const QRegularExpression pattern(
        QStringLiteral("(?:") + labelPattern() + QStringLiteral(")[^A-Za-z0-9]{0,24}(") +
            codePattern() + QStringLiteral(")(?![A-Za-z0-9])"),
        QRegularExpression::CaseInsensitiveOption);
    return pattern;
}

const QRegularExpression &trailingLabelPattern()
{
    static const QRegularExpression pattern(
        QStringLiteral("(?<![A-Za-z0-9])(") + codePattern() +
            QStringLiteral(")(?![A-Za-z0-9])[^\\n]{0,24}(?:") + labelPattern() +
            QStringLiteral(")"),
        QRegularExpression::CaseInsensitiveOption);
    return pattern;
}

const QRegularExpression &excludedFieldPattern()
{
    // Fields that must not be mistaken for a code when they appear between the
    // label and the candidate (e.g. "验证码错误，订单号123456").
    static const QRegularExpression pattern(
        QStringLiteral("(?:电话|手机|手机号|订单|订单号|物流|金额|余额|日期|时间|phone|telephone|order|invoice|amount|balance|date|time)"),
        QRegularExpression::CaseInsensitiveOption);
    return pattern;
}

bool containsExcludedField(const QString &text)
{
    return excludedFieldPattern().match(text).hasMatch();
}

QString compactCode(const QString &raw)
{
    static const QString separators = QStringLiteral(" \t　-－");
    QString code;
    code.reserve(raw.size());
    for (const QChar ch : raw) {
        if (!separators.contains(ch))
            code.append(ch);
    }
    return code;
}

bool isValidCode(const QString &code)
{
    static const QRegularExpression digit(QStringLiteral("[0-9]"));
    return code.size() >= 4 && code.size() <= 10 && code.contains(digit);
}

bool looksLikePhoneOrDate(const QString &text, int start, int length)
{
    const QString value = text.mid(start, length);
    if (value.size() >= 9)
        return true;
    // A bare year or a date component (e.g. "2026" in "2026-10-07").
    static const QRegularExpression year(QStringLiteral("^(?:19|20)\\d{2}$"));
    if (year.match(value).hasMatch())
        return true;
    static const QRegularExpression datePart(QStringLiteral("[-/.]\\d"));
    return datePart.match(text.mid(start + length, 3)).hasMatch();
}

QString stripValidityPhrases(QString text)
{
    // "验证码（5分钟内有效）：123456" puts digits between the label and the
    // code, which would otherwise break the label adjacency match.
    static const QRegularExpression validity(
        QStringLiteral("(?:有效期(?:为)?\\s*)?\\d{1,3}\\s*(?:分钟|minutes?)(?:内|后)?\\s*(?:有效|失效)?"),
        QRegularExpression::CaseInsensitiveOption);
    text.replace(validity, QStringLiteral(" "));
    return text;
}

void appendCandidate(QVector<Candidate> &candidates, const QString &text,
                     const QRegularExpressionMatch &match, int score, bool checkPrefix)
{
    const int start = match.capturedStart(1);
    const QString raw = match.captured(1);
    const QString code = compactCode(raw);
    if (!isValidCode(code) || looksLikePhoneOrDate(text, start, raw.size()))
        return;
    const QString context = checkPrefix
        ? text.mid(qMax(0, start - 28), 28)
        : text.mid(match.capturedStart(), start - match.capturedStart());
    if (containsExcludedField(context))
        return;
    candidates.append({code, score, start});
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

    const QString text = stripValidityPhrases(normalize(title + QStringLiteral("\n") + message));
    QVector<Candidate> candidates;

    // Domain-bound SMS format used by Apple: @example.com #123456.
    static const QRegularExpression domainBound(
        QStringLiteral("@[A-Za-z0-9.-]+\\s+#([A-Za-z0-9]{4,10})"));
    QRegularExpressionMatchIterator it = domainBound.globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        candidates.append({match.captured(1), 110, static_cast<int>(match.capturedStart(1))});
    }

    it = labeledPattern().globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        const QString code = compactCode(match.captured(1));
        appendCandidate(candidates, text, match, 100 + (code.size() == 6 ? 5 : 0), false);
    }

    // Also accept "123456 是您的验证码" style messages.
    it = trailingLabelPattern().globalMatch(text);
    while (it.hasNext()) {
        const QRegularExpressionMatch match = it.next();
        const QString code = compactCode(match.captured(1));
        appendCandidate(candidates, text, match, 90 + (code.size() == 6 ? 5 : 0), true);
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
