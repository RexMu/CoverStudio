"""「功能說明」 window: product introduction plus a feature overview."""
from __future__ import annotations

from . import AUTHOR, VERSION_LABEL, theme
from .help_text import ABOUT_HTML, FEATURES
from .qt import QtWidgets as W


def help_html():
    cards = "".join(
        f"<tr><td style='padding:8px 10px; vertical-align:top; color:#32d4ce; font-weight:700'>{n}</td>"
        f"<td style='padding:8px 4px'><b style='color:#e6eff8'>{title}</b><br>"
        f"<span style='color:#b9c8d6'>{text}</span></td></tr>"
        for n, (title, text) in enumerate(FEATURES, 1))
    html = (ABOUT_HTML +
            "<h2 style='color:#e6eff8; font-size:17px; margin-top:22px'>功能一覽</h2>"
            f"<table cellspacing='0' width='100%'>{cards}</table>")
    return theme.css(html)


class HelpDialog(W.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("功能說明")
        self.resize(820, 860)
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        self.browser = W.QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(help_html())
        theme.apply(self.browser, "QTextBrowser { background: #142231; border: 1px solid #304359; "
                                  "border-radius: 8px; padding: 14px 18px; color: #c9d6e2; font-size: 14px; }")
        layout.addWidget(self.browser, 1)
        foot = W.QHBoxLayout()
        info = W.QLabel(f"{VERSION_LABEL} · {AUTHOR}　·　各效果的參數說明請點標題旁的 i")
        info.setObjectName("muted")
        foot.addWidget(info)
        foot.addStretch()
        ok = W.QPushButton("我知道了")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        foot.addWidget(ok)
        layout.addLayout(foot)
