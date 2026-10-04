#ifndef VERIFICATIONCODE_H
#define VERIFICATIONCODE_H

#include <QString>

namespace VerificationCode {

// Returns a code only when the message contains a strong OTP label. This
// deliberately refuses bare numbers because SMS also contains phone numbers,
// amounts, dates, and order numbers.
QString extract(const QString &title, const QString &message);

}

#endif // VERIFICATIONCODE_H
