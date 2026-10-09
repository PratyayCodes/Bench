import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QLockFile, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon
)

from branding import make_icon
from dashboard import Dashboard
from projects import APP_DIR, Settings, ensure_workspace


HOTKEY_ID = 0xBEEF
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000  # don't fire repeatedly while the keys are held
VK_SPACE = 0x20
WM_HOTKEY = 0x0312


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", POINT),
    ]


class WindowsHotkeyFilter(QAbstractNativeEventFilter):
    """Receives WM_HOTKEY messages while the Qt event loop is running."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0


class BenchApp:
    def __init__(self, app):
        self.app = app
        self.icon = make_icon()
        self.app.setWindowIcon(self.icon)
        self.settings = Settings.load()
        self.prepare_workspace()

        self.dashboard = Dashboard(self.settings)
        self.dashboard.setWindowIcon(self.icon)

        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray.setToolTip("CodeP Bench")
        menu = QMenu()
        open_action = QAction("Open CodeP Bench", menu)
        open_action.triggered.connect(self.show_dashboard)
        menu.addAction(open_action)
        workspace_action = QAction("Open Workspace", menu)
        workspace_action.triggered.connect(self.open_workspace)
        menu.addAction(workspace_action)
        menu.addSeparator()
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)
        menu.setStyleSheet(
            "QMenu { background: #15181D; color: #E7E9ED; border: 1px solid #343A45; padding: 6px; }"
            "QMenu::item { padding: 7px 28px 7px 14px; border-radius: 5px; }"
            "QMenu::item:selected { background: #252A32; }"
            "QMenu::separator { height: 1px; background: #252A32; margin: 5px 8px; }"
        )
        self.tray_menu = menu  # keep a reference; Qt does not take ownership
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        self.hotkey_registered = False
        self.hotkey_filter = None
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            user32.RegisterHotKey.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint
            ]
            user32.RegisterHotKey.restype = ctypes.c_int
            self.hotkey_registered = bool(
                user32.RegisterHotKey(
                    None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_SPACE
                )
            )
            if self.hotkey_registered:
                self.hotkey_filter = WindowsHotkeyFilter(self.show_dashboard)
                self.app.installNativeEventFilter(self.hotkey_filter)
            else:
                self.dashboard.append_output(
                    "Could not register Ctrl+Alt+Space (another app may use it). "
                    "Open CodeP Bench from the system tray."
                )
        else:
            self.dashboard.append_output("The global hotkey is available on Windows only.")

        # Start hidden; use Ctrl+Alt+Space or the tray menu to show it.
        self.dashboard.hide()

    def prepare_workspace(self):
        """Ensure a usable workspace exists, asking the user whenever it is missing or unusable."""
        while True:
            if self.settings.workspace:
                try:
                    ensure_workspace(Path(self.settings.workspace))
                    return
                except OSError as exc:
                    QMessageBox.warning(
                        None, "CodeP Bench",
                        f"Cannot use workspace:\n{self.settings.workspace}\n\n{exc}\n\nPlease choose another."
                    )
            chosen = QFileDialog.getExistingDirectory(
                None, "Choose your CodeP Bench workspace",
                str(Path.home() / "CodePWorkspace")
            )
            if not chosen:
                QMessageBox.information(
                    None, "CodeP Bench",
                    "Choose a workspace to use CodeP Bench. The app will now exit."
                )
                raise SystemExit(0)
            self.settings.workspace = str(Path(chosen).resolve())
            try:
                self.settings.save()
            except OSError as exc:
                QMessageBox.warning(
                    None, "CodeP Bench",
                    f"Could not save settings ({exc}). You will be asked again next launch."
                )

    def show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()
        self.dashboard.focus_command()

    def open_workspace(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.settings.workspace))

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.dashboard.isVisible():
                self.dashboard.hide()
            else:
                self.show_dashboard()

    def exit_app(self):
        running = self.dashboard.servers.running_projects()
        if running:
            answer = QMessageBox.question(
                None, "CodeP Bench",
                "These processes launched by Bench are still running:\n  "
                + "\n  ".join(running) + "\n\nStop them and exit?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.dashboard.servers.stop_all()
        if sys.platform == "win32" and self.hotkey_registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self.hotkey_registered = False
        self.dashboard.allow_quit()
        self.tray.hide()
        self.app.quit()


def main():
    if sys.platform != "win32":
        print("CodeP Bench currently targets Windows.")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("CodeP Bench")
    app.setQuitOnLastWindowClosed(False)

    # Single instance: a second copy could never register the hotkey and would just confuse things.
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    lock = QLockFile(str(APP_DIR / "bench.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "CodeP Bench",
            "CodeP Bench is already running. Use Ctrl+Alt+Space or the system tray icon."
        )
        return 0

    bench = BenchApp(app)
    app._bench = bench  # keep a reference alive for the full event loop
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
