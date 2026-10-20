from clipboard import ClipboardMonitor

import ctypes
import keyboard
import os
import pyautogui
import re
import socket
import subprocess
import sys
import threading
import time
import winreg

from urllib.parse import quote_plus

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import QByteArray, QCoreApplication, QEvent, QEasingCurve, QObject, QPropertyAnimation, QRect, QSize, Qt, pyqtSignal, QSettings, QThread, QTimer
from PyQt6.QtGui import QAction, QIcon, QPixmap
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QMainWindow, QLineEdit, QLabel, QPushButton, QWidget, QSystemTrayIcon

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
WM_HOTKEY = 0x0312
VK_SPACE = 0x20
HOST = 'localhost'

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

qss_file = resource_path("firefox_go.qss")
close_button_file = resource_path("images/closeButton.png")
firefox_file = resource_path("images/firefox.png")
go_button_file = resource_path("images/goButton.png")

class SearchBox(QLineEdit):
    def __init__(self, parent):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Search or enter web address")

    def focusOutEvent(self, event):
        self.setReadOnly(True)
        self.parent().goButton.hide()

    def focusInEvent(self, event):
        self.setReadOnly(False)
        self.parent().goButton.show()

    def is_valid_url(self, url):
        url_regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(url_regex, url) is not None

    def search(self):
        print(self.parent().clipboardAddress)
        print(self.parent().clipboardUrl)
        url = self.text()
        if not url:
            return
        if self.parent().clipboardAddress == self.text():
            url = self.parent().clipboardUrl
        elif not url.startswith('mailto:'):
            if not self.is_valid_url(url) and not self.is_valid_url('https://' + url):
                url = 'https://www.google.com/search?q=' + quote_plus(url)
            elif not url.startswith('http'):
                url = 'https://' + url
        subprocess.call(f'explorer "{url}"', shell=True)

class Floater(QPushButton):
    def __init__(self, *args, **kwargs):
        QPushButton.__init__(self, *args, **kwargs)
        self.moving = False
        self.moved = False
        self.offset = None
        self.isCollapsed = False
        
        self.collapsedSize = QSize(64, 64)
        self.animation = QPropertyAnimation(self.parent(), b"size")
        self.animation.setDuration(500)  # Set duration as per your requirements
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self.onAnimationFinished)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.context_menu = QMenu(self)
        self.menu_item_names = []

    def onAnimationFinished(self):
        if self.isCollapsed:
            self.parent().setWindowOpacity(0.25)
            self.parent().background.setHidden(True)
            self.parent().searchBox.clear()

    def createMenuItems(self):
        self.context_menu.clear()

        menu_items = [
            ("Launch with WIN+SPACE hotkey", self.parent().settings.value("hotkey_enabled", type=bool), self.toggleHotkey),
            ("Launch by pushing top of screen", self.parent().settings.value("edgeLaunch_enabled", type=bool), self.toggleEdgeLaunch),
            ("Always close to floating icon", self.parent().settings.value("floater_mode", type=bool), self.toggleFloaterMode),
            ("Save search bar location between launches", self.parent().settings.value("save_position", type=bool), self.toggleSavePosition),
            ("Populate search bar with clipboard contents", self.parent().settings.value("clipboard_enabled", type=bool), self.toggleClipboard),
            ("Run Firefox Go on startup", self.parent().settings.value("run_at_startup", type=bool), self.toggleRunAtStartup)
        ]

        for name, value, function in menu_items:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(value)
            action.triggered.connect(function)
            self.context_menu.addAction(action)
            print("Added menu item: " + name + " with value " + str(value))

        action = QAction("Exit", self)
        action.triggered.connect(QApplication.instance().quit)
        self.context_menu.addAction(action)

    def contextMenuEvent(self, event):
        self.createMenuItems()
        self.context_menu.exec(self.mapToGlobal(event.pos()))

    def toggleHotkey(self):
        self.saveSetting("hotkey_enabled", not self.parent().settings.value("hotkey_enabled", type=bool))
        self.parent().registerHotkey()

    def toggleEdgeLaunch(self):
        self.saveSetting("edgeLaunch_enabled", not self.parent().settings.value("edgeLaunch_enabled", type=bool))

    def toggleFloaterMode(self):
        self.saveSetting("floater_mode", not self.parent().settings.value("floater_mode", type=bool))
        self.parent().setFloaterMode()

    def toggleSavePosition(self):
        self.saveSetting("save_position", not self.parent().settings.value("save_position", type=bool))

    def toggleClipboard(self):
        self.saveSetting("clipboard_enabled", not self.parent().settings.value("clipboard_enabled", type=bool))

    def toggleRunAtStartup(self):
        self.saveSetting("run_at_startup", not self.parent().settings.value("run_at_startup", type=bool))
        self.parent().setRunAtStartup()

    def saveSetting(self, setting_name, value):
        self.parent().settings.setValue(setting_name, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.moving = True
            self.offset = event.globalPosition().toPoint() - self.parent().frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.moving:
            self.parent().move(event.globalPosition().toPoint() - self.offset)
            self.moved = True

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.moved:
                self.parent().searchBox.setFocus()
            self.parent().settings.setValue("saved_positionx", self.parent().frameGeometry().topLeft().x())
            self.parent().settings.setValue("saved_positiony", self.parent().frameGeometry().topLeft().y())
            self.moving = False
            self.moved = False

    def mouseDoubleClickEvent(self, event):
        if not self.isCollapsed:
            print("Collapsing")
            self.animation.setStartValue(self.parent().defaultSize)
            self.animation.setEndValue(self.collapsedSize)
            self.isCollapsed = True
            self.setFocus()
            self.parent().searchBox.clear()
        else:
            print("Expanding")
            self.animation.setStartValue(self.collapsedSize)
            self.animation.setEndValue(self.parent().defaultSize)
            self.parent().setWindowOpacity(1.0)
            self.parent().background.setHidden(False)
            self.isCollapsed = False
        self.animation.start()

class MainWindow(QMainWindow):
    taskbarButtonSignal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.settings = QSettings("Mozilla", "FirefoxGo")

        if not self.settings.contains("floater_mode"):
            self.settings.setValue("floater_mode", False)
        
        if not self.settings.contains("save_position"):
            self.settings.setValue("save_position", False)

        if not self.settings.contains("hotkey_enabled"):
            self.settings.setValue("hotkey_enabled", True)

        if not self.settings.contains("run_at_startup"):
            self.settings.setValue("run_at_startup", False)

        if not self.settings.contains("edgeLaunch_enabled"):
            self.settings.setValue("edgeLaunch_enabled", True)

        if not self.settings.contains("clipboard_notifications"):
            self.settings.setValue("clipboard_notifications", True)
        
        if not self.settings.contains("copy_and_go"):
            self.settings.setValue("copy_and_go", True)

        if not self.settings.contains("saved_positionx"):
            self.settings.setValue("saved_positionx", 500)

        if not self.settings.contains("clipboard_enabled"):
            self.settings.setValue("clipboard_enabled", True)

        if not self.settings.contains("saved_positiony"):
            self.settings.setValue("saved_positiony", 500)

        self.clipboardMonitor = ClipboardMonitor(self, app)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(firefox_file))
        self.tray_icon.setToolTip("Firefox Go")
        
        tray_menu = QMenu(self)
        turn_on_action = tray_menu.addAction("Firefox Go (WIN+SPACE)")
        turn_on_action.triggered.connect(self.turnOn)
        copyAndGo_action = tray_menu.addAction("Copy and Go (CTRL+C+C)")
        copyAndGo_action.setCheckable(True)
        copyAndGo_action.setChecked(self.settings.value("copy_and_go", type=bool))
        copyAndGo_action.triggered.connect(self.toggleCopyAndGo)
        clipboard_action = tray_menu.addAction("Clipboard monitor notifications")
        clipboard_action.setCheckable(True)
        clipboard_action.setChecked(self.settings.value("clipboard_notifications", type=bool))
        clipboard_action.triggered.connect(self.toggleClipboardNotifications)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.trayIconActivated)

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.tray_icon.show()

        self.animation = None
        self.isClosing = False
        self.isOn = True
        self.clipboardUrl = None
        self.clipboardAddress = None
        self.previousSearchText = None

        self.defaultSize = QtCore.QSize(720, 64)
        self.resize(self.defaultSize)

        self.background = QWidget(self)
        self.setCentralWidget(self.background)
        self.background.setObjectName("background")
                
        iconPixmap = QPixmap(firefox_file)
        self.floater = Floater(QIcon(iconPixmap), '', self)
        self.floater.setGeometry(0, 0, 64, 64)
        self.floater.setIcon(QIcon(iconPixmap))
        self.floater.setIconSize(QtCore.QSize(48,48)) 

        self.hintText = QLabel(self)
        self.hintText.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hintText.setGeometry(64, 4, 592, 16)
        self.hintText.setObjectName("hintText")

        self.searchBox = SearchBox(self)
        self.searchBox.setGeometry(64, 22, 592, 32)
        self.searchBox.returnPressed.connect(self.search)

        iconPixmap = QPixmap(go_button_file)
        self.goButton = QPushButton(QIcon(iconPixmap), '', self)
        self.goButton.setGeometry(625, 24, 28, 28)
        self.goButton.setObjectName("goButton")
        self.goButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.goButton.clicked.connect(self.search)
        self.goButton.raise_()
        
        iconPixmap = QPixmap(close_button_file)
        self.closeButton = QPushButton(QIcon(iconPixmap), '', self)
        self.closeButton.setGeometry(664, 8, 48, 48)
        self.closeButton.setIcon(QIcon(iconPixmap))
        self.closeButton.setIconSize(QtCore.QSize(48,48)) 
        self.closeButton.setObjectName("closeButton")
        self.setFloaterMode()

        with open(qss_file, "r") as f:
            self.setStyleSheet(f.read())

        QApplication.instance().installEventFilter(self)

        self.mouseMoveTimer = QTimer()
        self.mouseMoveTimer.timeout.connect(self.checkMousePosition)
        self.mouseMoveTimer.start(100)

        self.edgeLaunchTimer = QTimer()
        self.edgeLaunchTimer.setSingleShot(True)
        self.edgeLaunchTimer.timeout.connect(self.animateFromTop)

        self.clipboardTimer = QtCore.QTimer()
        self.clipboardTimer.setInterval(20000)
        self.clipboardTimer.timeout.connect(self.checkAndClearSearchBox)

        if self.settings.value("save_position", type=bool):
            self.moveToSavedPosition()
        else:
            self.moveToTopCenter()

        self.registerHotkey()
        self.setRunAtStartup()
        
        ctypes.windll.user32.SetForegroundWindow(self.winId().__int__())
        self.searchBox.setFocus()
    
    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.turnOff()
        return super().eventFilter(source, event)

    def trayIconActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.turnOn()

    def registerHotkey(self):
        if self.settings.value("hotkey_enabled", type=bool):
            self.hintText.setText("Firefox Go: Activate with WIN+SPACE -- ESC to hide -- CTRL+C+C to 'Copy and Go' from any app")
            try:
                keyboard.add_hotkey('win+space', self.toggleByHotkey)
            except Exception:
                pass
        else:
            self.hintText.setText("Firefox Go: Use ESC to hide. Use CTRL+C+C to 'Copy and Go' from any app")
            try:
                keyboard.remove_hotkey('win+space')
            except Exception:
                pass

    def setFloaterMode(self):
        if self.settings.value("floater_mode", type=bool):
            try:
                self.closeButton.clicked.disconnect(self.turnOff)
            except TypeError:
                pass
            self.closeButton.clicked.connect(self.floater.mouseDoubleClickEvent)
        else:
            try:
                self.closeButton.clicked.disconnect(self.floater.mouseDoubleClickEvent)
            except TypeError:
                pass
            self.closeButton.clicked.connect(self.turnOff)


    def setRunAtStartup(self):
        if self.settings.value("run_at_startup", type=bool):
            exePath = os.getcwd() + "\\firefox_go.exe"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                0, 
                winreg.KEY_ALL_ACCESS
            )
            winreg.SetValueEx(key, "Firefox Go", 0, winreg.REG_SZ, exePath)
            winreg.CloseKey(key)
        
        else:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                r"Software\Microsoft\Windows\CurrentVersion\Run", 
                0, 
                winreg.KEY_ALL_ACCESS
            )
            try:
                winreg.DeleteValue(key, "Firefox Go")
            except FileNotFoundError:
                pass
                winreg.CloseKey(key)

    def search(self):
        self.searchBox.search()
        self.turnOff()
    
    def taskbarButtonPressed(self):
        if not self.underMouse():
            if not self.isOn and not self.floater.isCollapsed:
                print("Taskbar button pressed while bar was off. Turning on by taskbar.")
                self.turnOnByTaskbar()
            else:
                print("Taskbar button pressed while bar was on. Turning off.")
                self.turnOff()

    def turnOnByTaskbar(self):
        self.isOn = True
        self.searchBox.setFocus()
        self.resize(self.defaultSize)
        if self.settings.value("save_position", type=bool):
            self.moveToSavedPosition()
            self.setWindowOpacity(1.0)
        else:
            taskbarButtonCenter = QtGui.QCursor.pos()

            screen = QtGui.QGuiApplication.screenAt(taskbarButtonCenter)
            if not screen:
                screen = QtGui.QGuiApplication.primaryScreen()
            screenRect = screen.availableGeometry()
            
            if taskbarButtonCenter.x() - 32 + self.width() + 20 > screenRect.right():
                windowX = screenRect.right() - self.width() - 20
            elif taskbarButtonCenter.x() - 32 - 20 < screenRect.left():
                windowX = screenRect.left() + 20
            else:
                windowX = taskbarButtonCenter.x() - 32

            self.move(windowX, taskbarButtonCenter.y())
            self.setWindowOpacity(1.0)

            targetY = screenRect.bottom() - self.height() - 10

            startRect = self.geometry()
            endRect = QtCore.QRect(windowX, targetY, self.width(), self.height())

            self.animation = QtCore.QPropertyAnimation(self, b"geometry")
            self.animation.setDuration(500)
            self.animation.setStartValue(startRect)
            self.animation.setEndValue(endRect)
            self.animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            self.animation.start()
           
        ctypes.windll.user32.SetForegroundWindow(self.winId().__int__())

    def toggleByHotkey(self):
        if not self.isOn:
            if self.settings.value("clipboard_enabled"):
                pyautogui.hotkey('ctrl', 'c')
            else:
                pyautogui.hotkey('ctrl', 'alt', 'f12')
            time.sleep(0.15)

        if QtCore.QThread.currentThread() != QtCore.QCoreApplication.instance().thread():
            QtCore.QTimer.singleShot(0, self.toggleByHotkey)
        else:
            if self.isOn and not self.floater.isCollapsed:
                print("Hotkey received while bar is on. Turning off.")
                self.turnOff()
            else:
                print("Hotkey received while bar is off. Turning on by hotkey.")
                self.turnOn()

    def turnOn(self):
        if self.floater.isCollapsed:
            print("turnOn() in floater_mode")
            self.floater.mouseDoubleClickEvent(None)
        else:
            print("turnOn() in normal mode")
            self.isOn = True
            self.resize(self.defaultSize)
            if self.settings.value("save_position", type=bool):
                self.moveToSavedPosition()
            else:
                self.moveToTopCenter()
            self.setWindowOpacity(1.0)
            self.searchBox.setFocus()
            ctypes.windll.user32.SetForegroundWindow(self.winId().__int__())

    def turnOff(self):
        if self.settings.value("floater_mode", type=bool):
            print("turnOff() in floater_mode")
            self.floater.mouseDoubleClickEvent(None)
        else:
            print("turnOff() in normal mode")
            self.isOn = False
            self.setWindowOpacity(0.0)
            
            windowCenter = self.geometry().center()
            screen = QtGui.QGuiApplication.screenAt(windowCenter)
            if not screen:
                screen = QtGui.QGuiApplication.primaryScreen()
            screenRect = screen.availableGeometry()
            
            newPos = QtCore.QPoint(screenRect.left(), screenRect.bottom())
            self.move(newPos)
            self.resize(1, 1)
            
            self.searchBox.clear()

    def moveToSavedPosition(self):
        self.move(self.settings.value("saved_positionx", type=int), self.settings.value("saved_positiony", type=int))

    def moveToTopCenter(self):
        mouse_position = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(mouse_position)
        if not screen:
            screen = QtGui.QGuiApplication.primaryScreen()
        screen_geometry = screen.geometry()
        top_center = (screen_geometry.width() - self.width()) // 2
        self.move(top_center, 100)
        self.settings.setValue("saved_positionx", self.pos().x())
        self.settings.setValue("saved_positiony", self.pos().y())

    def checkMousePosition(self):
        if self.settings.value("edgeLaunch_enabled", type=bool):
            mousePos = QtGui.QCursor.pos()
            if mousePos.y() <= 0 and not self.isOn:  
                if not self.edgeLaunchTimer.isActive():
                    self.edgeLaunchTimer.start(500)
            else:
                if self.edgeLaunchTimer.isActive():
                    self.edgeLaunchTimer.stop()

    def animateFromTop(self):
        self.isOn = True
        self.searchBox.setFocus()
        self.resize(self.defaultSize)
        self.setWindowOpacity(1.0)
        
        if self.settings.value("save_position", type=bool):
            self.moveToSavedPosition()
            ctypes.windll.user32.SetForegroundWindow(self.winId().__int__())
        else:
            mousePos = QtGui.QCursor.pos()
            screen = QtGui.QGuiApplication.screenAt(mousePos)
            if not screen:
                screen = QtGui.QGuiApplication.primaryScreen()
            screenRect = screen.availableGeometry()

            topLeft = screenRect.topLeft()
            startRect = QRect(topLeft.x() + (screenRect.width() - self.width()) // 2, topLeft.y() - self.height(), self.width(), self.height())
            endRect = QRect(topLeft.x() + (screenRect.width() - self.width()) // 2, topLeft.y() + 100, self.width(), self.height())

            self.animation = QPropertyAnimation(self, QByteArray(b"geometry"))
            self.animation.setDuration(250)
            self.animation.setStartValue(startRect)
            self.animation.setEndValue(endRect)
            self.animation.finished.connect(self.animateFromTopFinished)
            self.animation.start()

            self.settings.setValue("saved_positionx", endRect.x())
            self.settings.setValue("saved_positiony", endRect.y())

    def animateFromTopFinished(self):
        self.animationFinishedTimer = QtCore.QTimer()
        self.animationFinishedTimer.setSingleShot(True)
        self.animationFinishedTimer.timeout.connect(self.animateFromTopFinishedTimeout)
        self.animationFinishedTimer.start(100)
    
    def animateFromTopFinishedTimeout(self):
        ctypes.windll.user32.SetForegroundWindow(self.winId().__int__())

    def clipboardUpdated(self, matchType, displayText, url):
        if matchType == "search query" or matchType == "link":
            self.searchBox.setText(displayText)
        elif matchType == "address" or "tracking number" in matchType:
            self.searchBox.setText(displayText)
            self.clipboardUrl = url
            self.clipboardAddress = displayText
        else:
            self.searchBox.setText(matchType + " " + displayText)
        self.searchBox.selectAll()

        self.previousSearchText = self.searchBox.text()
        self.clipboardTimer.start()
    
    def checkAndClearSearchBox(self):
        if (self.searchBox.text() == self.previousSearchText and 
                len(self.searchBox.selectedText()) == len(self.searchBox.text())):
            self.searchBox.clear()

    def toggleClipboardNotifications(self):
        self.settings.setValue("clipboard_notifications", not self.settings.value("clipboard_notifications", type=bool))

    def toggleCopyAndGo(self):
        self.settings.setValue("copy_and_go", not self.settings.value("copy_and_go", type=bool))

class Listener(QObject):
    taskbarButtonSignal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.server = QLocalServer()
        self.server.newConnection.connect(self.handle_new_connection)

        if not self.server.listen(HOST):
            print(f"Unable to start the server: {self.server.errorString()}")
            QCoreApplication.exit(1)

    def handle_new_connection(self):
        while self.server.hasPendingConnections():
            client_connection = self.server.nextPendingConnection()
            if client_connection:
                client_connection.waitForReadyRead()
                data = client_connection.readAll().data().decode('utf-8')
                self.taskbarButtonSignal.emit()
                client_connection.disconnectFromServer()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()

        listener = Listener()
        listener_thread = QThread()
        listener.moveToThread(listener_thread)

        listener_thread.started.connect(listener.handle_new_connection)
        listener.taskbarButtonSignal.connect(window.taskbarButtonPressed) 

        listener_thread.start()

        sys.exit(app.exec())
    except Exception as e:
        if getattr(sys, 'frozen', False):
            with open('error.log', 'a') as log_file:
                log_file.write(str(e))
            QCoreApplication.exit(1)
        else:
            raise

