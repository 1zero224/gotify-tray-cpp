# Gotify Tray++


A tray notification application for receiving messages from a [Gotify server](https://github.com/gotify/server).


## Features

- Receive gotify messages in the native notification area.
- Reconnect after wake from sleep or losing network connection.
- Disable notification banners for low priority messages.
- Manually delete received messages.
- Go through a history of all previously received messages.
- Receive missed messages after losing network connection.
- English and Simplified Chinese UI. Choose Follow system, English, or
  Simplified Chinese in Settings > General > Interface > Language, then
  restart the application to apply the saved preference.
- Detect labeled SMS one-time codes locally and show a `复制验证码` action in
  the notification popup and message history. Only high-confidence candidates
  are offered; bare numbers are ignored to avoid copying phone numbers,
  amounts, dates, or order numbers.


## Installation

### Optional QQ email forwarding

The [QQ mail bridge](integrations/qq-mail-gotify/README.md) can run on a Linux
server and forward recognized email verification codes to the same Gotify
server. It includes separate-paragraph HTML code detection and regression tests.
Update the desktop client for authoritative `验证码：<code>` title handling so
English text in forwarded emails cannot hide the copy-code action.

Source builds require the Qt LinguistTools development package for compiling
`translations/gotify-tray_zh_CN.ts`. Qt 6.9 and newer also merge the Qt `qtbase`
translation catalog when available (install the Qt translations package for
localized standard dialogs). Translation resources are embedded in the executable;
end users do not need Qt Linguist installed.

### Windows

[Download the latest release here.](https://github.com/seird/gotify-tray-cpp/releases/latest)

### Arch Linux

Install from AUR package:

```
gotify-tray-cpp
```


## Images


### Main window

Light                                         |  Dark                                                      
:-------------------------------------------------:|:---------------------------------------------------------:
![window-light](https://raw.githubusercontent.com/seird/gotify-tray-cpp/master/images/window-light.png)            |  ![window-dark](https://raw.githubusercontent.com/seird/gotify-tray-cpp/master/images/window-dark.png)


### Settings window

Light                                         |  Dark                                                      
:-------------------------------------------------:|:---------------------------------------------------------:
![settings-light](https://raw.githubusercontent.com/seird/gotify-tray-cpp/master/images/settings-light.png)            |  ![settings-dark](https://raw.githubusercontent.com/seird/gotify-tray-cpp/master/images/settings-dark.png)
