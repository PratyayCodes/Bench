from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap

# Shared visual identity for the app window, tray icon and dialogs.
BG = "#0F1115"
SURFACE = "#15181D"
SURFACE_RAISED = "#1B1F26"
BORDER = "#252A32"
BORDER_STRONG = "#343A45"
TEXT = "#E7E9ED"
TEXT_SOFT = "#B3B9C4"
TEXT_MUTED = "#7B8392"
ACCENT = "#6EA8FF"
ACCENT_STRONG = "#4F86F7"
SUCCESS = "#6FD3A0"
WARN = "#F2C46D"
ERROR = "#FF8F8F"


def make_pixmap(size=64):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    inset = size * 0.06
    rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#8FBFFF"))
    gradient.setColorAt(1.0, QColor(ACCENT_STRONG))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    radius = size * 0.24
    painter.drawRoundedRect(rect, radius, radius)
    font = QFont("Segoe UI", max(1, int(size * 0.46)))
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#0B1220"))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "P")
    painter.end()
    return pixmap


def make_icon():
    """A tray icon must be non-empty or Windows shows nothing and the app is unreachable."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        icon.addPixmap(make_pixmap(size))
    return icon
