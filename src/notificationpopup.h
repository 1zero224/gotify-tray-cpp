#ifndef NOTIFICATIONPOPUP_H
#define NOTIFICATIONPOPUP_H

#include <QWidget>

class QLabel;
class QPushButton;
class QTimer;
class QIcon;
class QEnterEvent;
class QEvent;

class NotificationPopup : public QWidget
{
    Q_OBJECT

public:
    static void showNotification(const QString &title, const QString &message,
                                 const QString &verificationCode, const QIcon &icon,
                                 int durationMs);

private:
    void showEvent(QShowEvent *event) override;
    void enterEvent(QEnterEvent *event) override;
    void leaveEvent(QEvent *event) override;
    void fitBodyHeight();
    void paintEvent(QPaintEvent *event) override;
    explicit NotificationPopup(const QString &title, const QString &message,
                               const QString &verificationCode, const QIcon &icon,
                               int durationMs);
    void copyCode();

    QString code;
    QTimer *closeTimer;
    int timeoutMs = 0;
    int remainingMs = 0;
};

#endif // NOTIFICATIONPOPUP_H
