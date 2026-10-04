cmake_minimum_required(VERSION 3.5)

project(gotify-tray++ VERSION 0.1 LANGUAGES CXX)

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(KF6Notifications QUIET)
if(KF6Notifications_FOUND)
    add_definitions(-DUSE_KDE)
endif()

find_package(QT NAMES Qt6 Qt5 REQUIRED COMPONENTS Widgets Network WebSockets Sql)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Widgets Network WebSockets Sql)

if(QT_VERSION_MAJOR EQUAL 6)
    find_package(Qt6 REQUIRED COMPONENTS LinguistTools)
else()
    find_package(Qt5LinguistTools REQUIRED)
endif()

if (WIN32)
    set(APP_ICON_RESOURCE_WINDOWS "${CMAKE_CURRENT_SOURCE_DIR}/gotify-tray++.rc")
endif()

include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src)

set(PROJECT_SOURCES
        src/main.cpp
)

qt_add_executable(gotify-tray++
    MANUAL_FINALIZATION
    ${PROJECT_SOURCES}
    ${APP_ICON_RESOURCE_WINDOWS}

    resources.qrc
    README.md
    src/tray.h src/tray.cpp
    src/mainapplication.h src/mainapplication.cpp
    src/statuswidget.h src/statuswidget.cpp
    src/settings.h src/settings.cpp
    src/messageitemmodel.h src/messageitemmodel.cpp
    src/gotifyapi.h src/gotifyapi.cpp
    src/requesthandler.h src/requesthandler.cpp
    src/gotifymodels.h src/gotifymodels.cpp
    src/messageitem.h src/messageitem.cpp
    src/listener.h src/listener.cpp
    src/applicationitem.h src/applicationitem.cpp
    src/utils.h src/utils.cpp
    src/applicationitemmodel.h src/applicationitemmodel.cpp
    src/cache.h src/cache.cpp
    src/mainwindow.h src/mainwindow.cpp src/mainwindow.ui
    src/messagewidget.h src/messagewidget.cpp src/messagewidget.ui
    src/serverinfodialog.h src/serverinfodialog.cpp src/serverinfodialog.ui
    src/settingsdialog.h src/settingsdialog.cpp src/settingsdialog.ui
    src/appversion.h src/appversion.cpp
    src/clickablelabel.h src/clickablelabel.cpp
    src/processthread.h src/processthread.cpp
    src/imagepopup.h src/imagepopup.cpp
    src/verificationcode.h src/verificationcode.cpp
    src/notificationpopup.h src/notificationpopup.cpp

)

if(KF6Notifications_FOUND)
target_link_libraries(gotify-tray++ PRIVATE
    KF6::Notifications
)
endif()

target_link_libraries(gotify-tray++ PRIVATE Qt${QT_VERSION_MAJOR}::Widgets Qt${QT_VERSION_MAJOR}::Network Qt${QT_VERSION_MAJOR}::WebSockets Qt${QT_VERSION_MAJOR}::Sql)

# Qt for iOS sets MACOSX_BUNDLE_GUI_IDENTIFIER automatically since Qt 6.1.
# If you are developing for iOS or macOS you should consider setting an
# explicit, fixed bundle identifier manually though.
if(${QT_VERSION} VERSION_LESS 6.1.0)
  set(BUNDLE_ID_OPTION MACOSX_BUNDLE_GUI_IDENTIFIER com.example.gotify-tray++)
endif()
set_target_properties(gotify-tray++ PROPERTIES
    ${BUNDLE_ID_OPTION}
    MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
    MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}
    MACOSX_BUNDLE TRUE
    WIN32_EXECUTABLE TRUE
)

include(GNUInstallDirs)
install(TARGETS gotify-tray++
    BUNDLE DESTINATION .
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

if(QT_VERSION_MAJOR EQUAL 6)
    if(Qt6_VERSION VERSION_GREATER_EQUAL 6.9)
        set(GOTIFY_QT_TRANSLATIONS MERGE_QT_TRANSLATIONS QT_TRANSLATION_CATALOGS qtbase)
    endif()
    qt_add_translations(gotify-tray++
        TS_FILES translations/gotify-tray_zh_CN.ts
        RESOURCE_PREFIX "/i18n"
        ${GOTIFY_QT_TRANSLATIONS}
    )
    qt_finalize_executable(gotify-tray++)
else()
    qt5_add_translation(GOTIFY_TRANSLATIONS translations/gotify-tray_zh_CN.ts)
    configure_file(translations/translations.qrc.in ${CMAKE_CURRENT_BINARY_DIR}/translations.qrc @ONLY)
    add_custom_target(gotify-translations DEPENDS ${GOTIFY_TRANSLATIONS})
    add_dependencies(gotify-tray++ gotify-translations)
    target_sources(gotify-tray++ PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/translations.qrc)
endif()

option(GOTIFY_BUILD_TESTS "Build offline translation and language setting tests" OFF)
if(GOTIFY_BUILD_TESTS)
    enable_testing()
    find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Test)
    get_target_property(GOTIFY_TEST_SOURCES gotify-tray++ SOURCES)
    list(FILTER GOTIFY_TEST_SOURCES EXCLUDE REGEX "(main|mainapplication)\\.cpp$|gotify-tray\\+\\+\\.rc$|README\\.md$")
    configure_file(translations/translations.qrc.in ${CMAKE_CURRENT_BINARY_DIR}/test-translations.qrc @ONLY)
    add_executable(gotify-language-test tests/languagetest.cpp ${GOTIFY_TEST_SOURCES}
        ${CMAKE_CURRENT_BINARY_DIR}/test-translations.qrc)
    add_dependencies(gotify-language-test gotify-tray++)
    target_link_libraries(gotify-language-test PRIVATE Qt${QT_VERSION_MAJOR}::Widgets
        Qt${QT_VERSION_MAJOR}::Network Qt${QT_VERSION_MAJOR}::WebSockets
        Qt${QT_VERSION_MAJOR}::Sql Qt${QT_VERSION_MAJOR}::Test)
    if(KF6Notifications_FOUND)
        target_link_libraries(gotify-language-test PRIVATE KF6::Notifications)
    endif()
    add_test(NAME language-settings COMMAND gotify-language-test)
    set_tests_properties(language-settings PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endif()
