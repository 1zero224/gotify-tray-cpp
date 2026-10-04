#include "cache.h"
#include "requesthandler.h"
#include "settings.h"
#include "settingsdialog.h"
#include "tray.h"
#include "statuswidget.h"

#include <QApplication>
#include <QComboBox>
#include <QDialogButtonBox>
#include <QMessageBox>
#include <QPushButton>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <QTranslator>
#include <QTimer>
#include <QLabel>
#include <QDir>
#include <QTabWidget>

class LanguageTest : public QObject
{
    Q_OBJECT
private slots:
    void translations()
    {
        QTranslator translator;
        QVERIFY(translator.load(QStringLiteral(":/i18n/gotify-tray_zh_CN.qm")));
        qApp->installTranslator(&translator);
        QCOMPARE(Tray::tr("Settings"), QString::fromUtf8("设置"));
        QCOMPARE(SettingsDialog::tr("Language:"), QString::fromUtf8("语言："));
        QCOMPARE(StatusWidget::tr("Connecting..."), QString::fromUtf8("正在连接…"));
        {
            SettingsDialog dialog;
            QCOMPARE(dialog.findChild<QLabel *>(QStringLiteral("label_language"))->text(), QString::fromUtf8("语言："));
            auto *buttons = dialog.findChild<QDialogButtonBox *>(QStringLiteral("buttonBox"));
            QVERIFY(buttons->button(QDialogButtonBox::Apply)->text() != QStringLiteral("Apply"));
            const QString screenshots = qEnvironmentVariable("GOTIFY_TEST_SCREENSHOT_DIR");
            if (!screenshots.isEmpty()) {
                QDir().mkpath(screenshots);
                dialog.show();
                QTest::qWait(200);
                QVERIFY(dialog.grab().save(screenshots + "/settings-zh_CN.png"));
                auto *tabs = dialog.findChild<QTabWidget *>(QStringLiteral("tabWidget"));
                for (int i = 1; i < tabs->count(); ++i) {
                    tabs->setCurrentIndex(i);
                    QTest::qWait(100);
                    QVERIFY(dialog.grab().save(screenshots + "/settings-zh_CN-" + QString::number(i) + ".png"));
                }
            }
            QTest::qWait(100);
        }
        qApp->removeTranslator(&translator);
        QCOMPARE(Tray::tr("Settings"), QStringLiteral("Settings"));
    }

    void persistence_data()
    {
        QTest::addColumn<QString>("language");
        QTest::newRow("follow-system") << QStringLiteral("system");
        QTest::newRow("english") << QStringLiteral("en");
        QTest::newRow("chinese") << QStringLiteral("zh_CN");
    }

    void persistence()
    {
        QFETCH(QString, language);
        settings->setLanguage(QStringLiteral("unknown"));
        {
            SettingsDialog dialog;
            auto *combo = dialog.findChild<QComboBox *>(QStringLiteral("combo_language"));
            auto *buttons = dialog.findChild<QDialogButtonBox *>(QStringLiteral("buttonBox"));
            QVERIFY(combo);
            QCOMPARE(combo->count(), 3);
            QCOMPARE(combo->currentData().toString(), QStringLiteral("system"));
            combo->setCurrentIndex(combo->findData(language));
            settings->setLanguage(QStringLiteral("unknown"));
            QTimer::singleShot(0, [] {
                for (QWidget *widget : QApplication::topLevelWidgets())
                    if (auto *message = qobject_cast<QMessageBox *>(widget))
                        message->accept();
            });
            QVERIFY(QMetaObject::invokeMethod(&dialog, "saveSettings", Qt::DirectConnection));
            QCOMPARE(settings->language(), language);
            settings->sync();
            QSettings reloaded(qApp->applicationName());
            QCOMPARE(reloaded.value("language").toString(), language);
            QTest::qWait(100);
        }
        {
            SettingsDialog reopened;
            auto *combo = reopened.findChild<QComboBox *>(QStringLiteral("combo_language"));
            QCOMPARE(combo->currentData().toString(), language);
            QTest::qWait(100);
        }
    }

    void applyEnabled()
    {
        settings->setLanguage(QStringLiteral("system"));
        SettingsDialog dialog;
        auto *combo = dialog.findChild<QComboBox *>(QStringLiteral("combo_language"));
        auto *buttons = dialog.findChild<QDialogButtonBox *>(QStringLiteral("buttonBox"));
        QVERIFY(!buttons->button(QDialogButtonBox::Apply)->isEnabled());
        combo->setCurrentIndex(1);
        QVERIFY(buttons->button(QDialogButtonBox::Apply)->isEnabled());
        QTest::qWait(100);
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QTemporaryDir configuration;
    if (!configuration.isValid()) return 1;
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, configuration.path());
    QSettings::setPath(QSettings::IniFormat, QSettings::SystemScope, configuration.path());
    app.setApplicationName(QStringLiteral("GotifyLanguageTest"));
    QStandardPaths::setTestModeEnabled(true);
    settings = Settings::getInstance();
    cache = Cache::getInstance();
    requestHandler = RequestHandler::getInstance();
    LanguageTest test;
    return QTest::qExec(&test, argc, argv);
}

#include "languagetest.moc"
