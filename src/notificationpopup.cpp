#include "notificationpopup.h"

#include <QApplication>
#include <QClipboard>
#include <QHBoxLayout>
#include <QIcon>
#include <QLabel>
#include <QPushButton>
#include <QScreen>
#include <QTimer>
#include <QVBoxLayout>
#include <QTextBrowser>
#include <QTextDocument>
#include <QTextOption>
#include <QFontMetrics>
#include <QtMath>
#include <QPainter>
#include <QRegularExpression>
#include <QShowEvent>
#include <QScrollBar>

namespace {
QString notificationBody(const QString &message)
{
    // Strip only explicitly labelled forwarding metadata, never embedded SMS text.
    static const QRegularExpression metadata(
        QStringLiteral("^\\s*(?:SIM\\d+_?|(?:SIM(?:\\s*卡)?|SIM\\s*卡槽|sub[_ -]?id|subscription[_ -]?id)\\s*[:：=]\\s*[^\\r\\n]*)\\s*$"),
        QRegularExpression::CaseInsensitiveOption);
    QStringList lines;
    for (const QString &line : message.split(QLatin1Char('\n'))) {
        if (!metadata.match(line).hasMatch()) lines.append(line);
    }
    return lines.join(QLatin1Char('\n'));
}
}

NotificationPopup::NotificationPopup(const QString &title, const QString &message,
                                     const QString &verificationCode, const QIcon &icon,
                                     int durationMs)
    : QWidget(nullptr, Qt::Tool | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint)
    , code(verificationCode)
    , closeTimer(new QTimer(this))
{
    setAttribute(Qt::WA_DeleteOnClose);
    setAttribute(Qt::WA_ShowWithoutActivating);
    setAttribute(Qt::WA_TranslucentBackground);
#ifdef Q_OS_WIN
    setFont(QFont(QStringLiteral("Microsoft YaHei UI"), 10));
#endif
    setWindowTitle(title);
    setWindowIcon(icon);
    const QScreen *screen = QGuiApplication::primaryScreen();
    const QRect area = screen ? screen->availableGeometry() : QRect(0, 0, 800, 600);
    setFixedWidth(qMin(384, qMax(180, area.width() - 36)));
    setObjectName(QStringLiteral("GotifyNotificationPopup"));
    setStyleSheet(QStringLiteral("QLabel { color: palette(window-text); } QPushButton { padding: 6px 12px; }"));

    auto *root = new QVBoxLayout(this);
    root->setContentsMargins(12, 10, 12, 10);
    root->setSpacing(6);
    if (!code.isEmpty()) {
        auto *heading = new QHBoxLayout();
        auto *codeLabel = new QLabel(code, this);
        codeLabel->setObjectName(QStringLiteral("notificationCode"));
        codeLabel->setTextFormat(Qt::PlainText);
        codeLabel->setTextInteractionFlags(Qt::TextSelectableByMouse);
        auto *copyButton = new QPushButton(tr("Copy verification code"), this);
        copyButton->setObjectName(QStringLiteral("copyCodeButton"));
        copyButton->setToolTip(tr("Copy the detected verification code to the clipboard"));
        QFont codeFont = font();
#ifdef Q_OS_WIN
        codeFont.setFamily(QStringLiteral("Segoe UI"));
#endif
        codeFont.setBold(true);
        codeFont.setPointSize(26);
        const int codeWidth = width() - 24 - copyButton->sizeHint().width() - heading->spacing();
        while (codeFont.pointSize() > 12 && QFontMetrics(codeFont).horizontalAdvance(code) > codeWidth)
            codeFont.setPointSize(codeFont.pointSize() - 1);
        codeLabel->setFont(codeFont);
        heading->addWidget(codeLabel, 1);
        heading->addWidget(copyButton);
        connect(copyButton, &QPushButton::clicked, this, &NotificationPopup::copyCode);
        root->addLayout(heading);
    }

    auto *messageLabel = new QTextBrowser(this);
    messageLabel->setObjectName(QStringLiteral("notificationMessage"));
    messageLabel->setFrameShape(QFrame::NoFrame);
    messageLabel->setStyleSheet(QStringLiteral("QTextBrowser { background: transparent; border: none; }"));
    messageLabel->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    messageLabel->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    messageLabel->setLineWrapMode(QTextEdit::WidgetWidth);
    messageLabel->setWordWrapMode(QTextOption::WrapAtWordBoundaryOrAnywhere);
    messageLabel->ensurePolished();
    messageLabel->document()->setDefaultFont(messageLabel->font());
    messageLabel->setPlainText(notificationBody(message));
    messageLabel->document()->setDocumentMargin(2);
    root->addWidget(messageLabel);
    fitBodyHeight();

    adjustSize();
    if (screen) {
        move(area.right() - width() - 18, area.bottom() - height() - 18);
    }

    connect(closeTimer, &QTimer::timeout, this, &QWidget::close);
    closeTimer->start(qMax(1000, durationMs));
}

void NotificationPopup::fitBodyHeight()
{
    auto *body = findChild<QTextBrowser *>(QStringLiteral("notificationMessage"));
    if (!body) return;
    ensurePolished();
    body->ensurePolished();
    body->document()->setDefaultFont(body->font());
    const QScreen *targetScreen = screen();
    const int screenHeight = targetScreen ? targetScreen->availableGeometry().height() : 600;
    const int limit = qMin(body->fontMetrics().lineSpacing() * 8 + 8, qMax(48, screenHeight - 140));
    const QMargins margins = layout()->contentsMargins();
    const int bodyWidth = width() - margins.left() - margins.right();
    // Measure a polished document at the real viewport width; reserve a scrollbar only on overflow.
    body->document()->setTextWidth(bodyWidth);
    int textHeight = qCeil(body->document()->size().height());
    if (textHeight + 4 > limit) {
        body->document()->setTextWidth(bodyWidth - body->verticalScrollBar()->sizeHint().width());
        textHeight = qCeil(body->document()->size().height());
    }
    body->setFixedHeight(qMin(limit, textHeight + 4));
    layout()->invalidate();
    adjustSize();
    layout()->activate();
}

void NotificationPopup::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    fitBodyHeight();
    if (const QScreen *targetScreen = screen()) {
        const QRect area = targetScreen->availableGeometry();
        move(area.right() - width() - 18, area.bottom() - height() - 18);
    }
}

void NotificationPopup::paintEvent(QPaintEvent *)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(palette().color(QPalette::Mid));
    painter.setBrush(palette().color(QPalette::Window));
    painter.drawRoundedRect(QRectF(rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12);
}

void NotificationPopup::copyCode()
{
    QGuiApplication::clipboard()->setText(code);
    close();
}

void NotificationPopup::showNotification(const QString &title, const QString &message,
                                         const QString &verificationCode, const QIcon &icon,
                                         int durationMs)
{
    auto *popup = new NotificationPopup(title, message, verificationCode, icon, durationMs);
    popup->show();
}
