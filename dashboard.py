import ctypes
import html
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget
)

import branding as B
from projects import (
    BenchError, create_project, create_version, list_versions,
    open_project, resolve_project
)
from servers import ServerManager


STYLE = f"""
QMainWindow, QWidget {{
    background: {B.BG}; color: {B.TEXT};
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 13px;
}}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 18px; font-weight: 600; color: {B.TEXT}; }}
QLabel#muted {{ color: {B.TEXT_MUTED}; font-size: 12px; }}
QLabel#pill {{
    background: {B.SURFACE_RAISED}; border: 1px solid {B.BORDER};
    border-radius: 11px; padding: 3px 10px; color: {B.TEXT_SOFT}; font-size: 12px;
}}
QFrame#header {{ background: transparent; border: 0; border-bottom: 1px solid {B.BORDER}; }}

QLineEdit {{
    background: {B.SURFACE}; border: 1px solid {B.BORDER_STRONG}; border-radius: 10px;
    padding: 12px 14px; color: {B.TEXT};
    selection-background-color: {B.ACCENT_STRONG}; selection-color: #FFFFFF;
}}
QLineEdit:hover {{ border-color: #444B58; }}
QLineEdit:focus {{ border: 1px solid {B.ACCENT}; background: {B.SURFACE_RAISED}; }}

QPushButton {{
    background: {B.SURFACE}; color: {B.TEXT_SOFT}; border: 1px solid {B.BORDER};
    border-radius: 8px; padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {B.SURFACE_RAISED}; color: {B.TEXT}; border-color: {B.BORDER_STRONG}; }}
QPushButton:pressed {{ background: {B.BORDER}; }}
QPushButton:focus {{ border-color: {B.ACCENT}; }}
QPushButton#primary {{ background: {B.ACCENT_STRONG}; color: #FFFFFF; border: 1px solid {B.ACCENT_STRONG}; }}
QPushButton#primary:hover {{ background: {B.ACCENT}; border-color: {B.ACCENT}; color: #0B1220; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {B.TEXT_MUTED}; }}
QPushButton#ghost:hover {{ color: {B.TEXT}; background: {B.SURFACE}; }}

QTextEdit {{
    background: {B.SURFACE}; border: 1px solid {B.BORDER}; border-radius: 12px;
    padding: 12px 14px; color: {B.TEXT_SOFT};
    selection-background-color: {B.ACCENT_STRONG}; selection-color: #FFFFFF;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px 6px 0; }}
QScrollBar::handle:vertical {{ background: {B.BORDER_STRONG}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #4A5260; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""

ACCENT = B.ACCENT
ERROR = B.ERROR
WARN = B.WARN

MONO_FAMILIES = ["Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"]

# "double quoted phrase" or bare word. Predictable, unlike shlex(posix=False) + strip hacks.
TOKEN_RE = re.compile(r'"([^"]*)"|(\S+)')


def tokenize(raw):
    return [bare or quoted for quoted, bare in TOKEN_RE.findall(raw)]


def mono_font(size):
    font = QFont()
    font.setFamilies(MONO_FAMILIES)
    font.setPointSizeF(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class Dashboard(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._quitting = False
        self.servers = ServerManager(self.append_output)
        self.handlers = {
            "help": self.cmd_help,
            "create": self.cmd_create,
            "version": self.cmd_version,
            "versions": self.cmd_versions,
            "open": self.cmd_open,
            "run": self.cmd_run,
            "stop": self.cmd_stop,
        }
        self.setWindowTitle("CodeP Bench")
        self.resize(820, 580)
        self.setMinimumSize(640, 440)
        self.setStyleSheet(STYLE)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(14)

        # Header: product mark, name, workspace indicator
        header = QFrame()
        header.setObjectName("header")
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 16)
        h.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(B.make_pixmap(72).scaled(
            36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        mark.setFixedSize(36, 36)
        title = QLabel("CodeP Bench")
        title.setObjectName("title")
        subtitle = QLabel("Workspace manager")
        subtitle.setObjectName("muted")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        h.addWidget(mark)
        h.addLayout(titles)
        h.addStretch()
        self.workspace_pill = QLabel(self._workspace_name())
        self.workspace_pill.setObjectName("pill")
        self.workspace_pill.setToolTip(str(self.settings.workspace))
        h.addWidget(self.workspace_pill)
        layout.addWidget(header)

        # Command input
        self.command = QLineEdit()
        self.command.setPlaceholderText("Type a command, for example: Create NomadFS")
        self.command.returnPressed.connect(self.execute_command)
        self.command.setFont(mono_font(11))
        self.command.setClearButtonEnabled(True)
        layout.addWidget(self.command)

        # Quick actions
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        for label, command in [
            ("Create", "Create "),
            ("Version", "Version "),
            ("Versions", "Versions "),
            ("Open", "Open "),
            ("Help", "Help"),
        ]:
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, c=command: self.set_command(c))
            buttons.addWidget(button)
        buttons.addStretch()
        clear = QPushButton("Clear output")
        clear.setObjectName("ghost")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(lambda checked=False: self.output.clear())
        buttons.addWidget(clear)
        layout.addLayout(buttons)

        # Output
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(mono_font(10))
        self.output.setPlaceholderText("Command output appears here.")
        self.output.document().setMaximumBlockCount(2000)  # don't grow without bound
        layout.addWidget(self.output, 1)

        # Footer: workspace path on the left, shortcuts on the right
        footer = QHBoxLayout()
        footer.setSpacing(16)
        path_label = QLabel(f"Workspace  {self.settings.workspace}")
        path_label.setObjectName("muted")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        keys_label = QLabel("Ctrl+Alt+Space to show     Esc to hide")
        keys_label.setObjectName("muted")
        footer.addWidget(path_label, 1)
        footer.addWidget(keys_label, 0)
        layout.addLayout(footer)

        self.setCentralWidget(root)
        self.append_output("CodeP Bench is ready. Type Help to see available commands.", B.TEXT_MUTED)

    # ---- UI helpers -------------------------------------------------------------------------

    def _workspace_name(self):
        path = str(self.settings.workspace or "").rstrip("\\/")
        return re.split(r"[\\/]", path)[-1] if path else "No workspace"

    def set_command(self, value):
        self.command.setText(value)
        self.command.setFocus()
        self.command.setCursorPosition(len(value))

    def focus_command(self):
        self.command.setFocus()
        self.command.selectAll()

    def append_output(self, text, color=None):
        """Append plain text. Everything is HTML-escaped so '<name>' and user input render literally."""
        style = "white-space: pre-wrap; margin: 2px 0;" + (f" color: {color};" if color else "")
        self.output.append(f"<div style='{style}'>{html.escape(str(text))}</div>")

    def allow_quit(self):
        self._quitting = True

    def showEvent(self, event):
        super().showEvent(event)
        self._style_title_bar()

    def _style_title_bar(self):
        """Match the native title bar to the dark theme on Windows 10/11. Purely cosmetic."""
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            dark = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            # Windows 11 only: caption and text colours (COLORREF is 0x00BBGGRR).
            caption = ctypes.c_int(0x00151110)
            text = ctypes.c_int(0x00EDE9E7)
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))
        except Exception:
            pass

    def closeEvent(self, event):
        # Closing the window hides it; the tray app stays alive (unless we are really quitting,
        # in which case blocking the close would also block Windows shutdown).
        if self._quitting:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    # ---- command dispatch -------------------------------------------------------------------

    def execute_command(self):
        raw = self.command.text().strip()
        if not raw:
            return
        self.command.clear()
        self.append_output(f"\u203a {raw}", ACCENT)
        try:
            args = tokenize(raw)
            handler = self.handlers.get(args[0].lower())
            if handler is None:
                raise BenchError(f"Unknown command: {args[0]}. Type Help.")
            handler(args)
        except BenchError as exc:
            self.append_output(f"Error: {exc}", ERROR)
        except Exception as exc:  # last-resort guard so a bug never kills the tray app
            self.append_output(f"Unexpected error: {exc!r}", ERROR)

    @staticmethod
    def require_count(args, count, usage):
        if len(args) != count:
            raise BenchError(usage)

    def try_open(self, path):
        """Open in VS Code; a launch failure is a warning, not a failure of the command that preceded it."""
        try:
            open_project(path)
            self.append_output(f"Opened in VS Code: {path}")
        except BenchError as exc:
            self.append_output(f"Warning: {exc}", WARN)

    def cmd_help(self, args):
        self.append_output(
            "Commands\n"
            "  Create <name>                  Create a project and open v1 in VS Code\n"
            "  Version <name>                 Copy the active version into the next version\n"
            "  Versions <name>                List project versions\n"
            "  Open <name>                    Open the active version in VS Code\n"
            "  Run <name> <file.py>           Run a Python file in a terminal\n"
            "  Run <name> http <index.html>   Serve the active version over HTTP\n"
            "  Run <name> https <index.html>  Serve over HTTPS (certificate setup required)\n"
            "  Stop <name>                    Stop a process launched by Bench\n"
            "  Help                           Show this list\n\n"
            "Project names with spaces can be quoted: Create \"My Project\".\n"
            "Names may use letters, digits, space, . _ - (max 64 characters)."
        )

    def cmd_create(self, args):
        self.require_count(args, 2, "Usage: Create <ProjectName>")
        path = create_project(self.settings, args[1])
        self.append_output(f"Created project {args[1]} with v1: {path}", B.SUCCESS)
        self.try_open(path)

    def cmd_version(self, args):
        self.require_count(args, 2, "Usage: Version <ProjectName>")
        _, version, path = create_version(self.settings, args[1])
        self.append_output(f"Created {version}; active version updated: {path}", B.SUCCESS)
        self.try_open(path)

    def cmd_versions(self, args):
        self.require_count(args, 2, "Usage: Versions <ProjectName>")
        items = list_versions(self.settings, args[1])
        if not items:
            self.append_output("No versions found.")
        for name, path, active in items:
            marker = "  [ACTIVE]" if active else ""
            self.append_output(f"{name}{marker}  \u2014  {path}", B.SUCCESS if active else None)

    def cmd_open(self, args):
        self.require_count(args, 2, "Usage: Open <ProjectName>")
        self.try_open(resolve_project(self.settings, args[1], active=True))

    def cmd_run(self, args):
        if len(args) < 3:
            raise BenchError("Usage: Run <ProjectName> [http|https] <file.py|index.html>")
        path = resolve_project(self.settings, args[1], active=True)
        self.servers.run(args[1], path, args[2:])

    def cmd_stop(self, args):
        self.require_count(args, 2, "Usage: Stop <ProjectName>")
        self.servers.stop(args[1])
