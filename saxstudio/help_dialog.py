"""「功能說明」 window: introduction, feature overview and a recording quick start."""
from __future__ import annotations

from . import AUTHOR, VERSION_LABEL, theme
from .help_text import ABOUT_HTML, FEATURE_GROUPS, QUICKSTART, QUICKSTART_INTRO, QUICKSTART_NEEDS
from .qt import QtWidgets as W

_GROUP = ("<h3 style='color:#e9b853; font-size:15px; margin:16px 0 4px'>{}</h3>"
          "<hr style='background-color:#263a50; height:1px; border:none'>")


def features_html():
    parts = []
    for group, items in FEATURE_GROUPS:
        rows = "".join(
            f"<tr><td width='150' style='padding:6px 12px 6px 0; vertical-align:top'>"
            f"<b style='color:#e6eff8'>{title}</b></td>"
            f"<td style='padding:6px 0; color:#b9c8d6; line-height:160%'>{text}</td></tr>"
            for title, text in items)
        parts.append(_GROUP.format(group) + f"<table cellspacing='0' width='100%'>{rows}</table>")
    return theme.css("".join(parts))


def quickstart_html():
    steps = []
    for n, (title, points) in enumerate(QUICKSTART, 1):
        bullets = "".join(f"<li style='margin-bottom:4px'>{p}</li>" for p in points)
        steps.append(
            "<table cellspacing='0' width='100%' style='margin-top:10px'><tr>"
            f"<td width='40' style='vertical-align:top; padding-top:2px'>"
            f"<span style='background-color:#2ac5bf; color:#06201f; font-weight:800; font-size:15px'>&nbsp;{n}&nbsp;</span></td>"
            f"<td><b style='color:#e6eff8; font-size:15px'>{title}</b>"
            f"<ul style='margin:4px 0 0 0; color:#b9c8d6; line-height:165%'>{bullets}</ul></td></tr></table>")
    html = (f"<p style='color:#b9c8d6; line-height:170%'>{QUICKSTART_INTRO}</p>"
            f"<p style='background-color:#17333a; padding:8px; line-height:170%'>{QUICKSTART_NEEDS}</p>"
            + "".join(steps))
    return theme.css(html)


def help_html():
    """Everything in one document (kept for tests and callers that want plain text)."""
    return theme.css(ABOUT_HTML) + features_html() + quickstart_html()


class HelpDialog(W.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("功能說明")
        self.resize(820, 860)
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        self.tabs = W.QTabWidget()
        self.browsers = []
        for title, html in (("介紹", theme.css(ABOUT_HTML)), ("功能一覽", features_html()),
                            ("錄音快速上手", quickstart_html())):
            browser = W.QTextBrowser()
            browser.setOpenExternalLinks(False)
            browser.setHtml(html)
            theme.apply(browser, "QTextBrowser { background: #142231; border: 1px solid #304359; "
                                 "border-radius: 8px; padding: 14px 18px; color: #c9d6e2; font-size: 14px; }")
            self.tabs.addTab(browser, title)
            self.browsers.append(browser)
        self.browser = self.browsers[0]
        layout.addWidget(self.tabs, 1)
        foot = W.QHBoxLayout()
        info = W.QLabel(f"{VERSION_LABEL} · {AUTHOR}　·　各效果的參數說明請點標題旁的 ⓘ")
        info.setObjectName("muted")
        foot.addWidget(info)
        foot.addStretch()
        ok = W.QPushButton("我知道了")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        foot.addWidget(ok)
        layout.addLayout(foot)

    def plain_text(self):
        return "\n".join(b.toPlainText() for b in self.browsers)
