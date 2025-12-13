"""HTML 清洗工具

攻略正文会以 `|safe` 的方式渲染，为了避免 XSS，建议在入库前进行清洗。

优先使用 bleach（建议写入 requirements.txt）。如果 bleach 不可用，提供一个
非常保守的降级版本（仅移除 <script> 标签与 on* 事件属性）。
"""

from __future__ import annotations

import re


_SCRIPT_RE = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.I | re.S)
_ON_EVENT_ATTR_RE = re.compile(r"\son[a-zA-Z]+\s*=\s*([\"']).*?\1", re.I | re.S)


def sanitize_html(html: str | None) -> str:
    """对 HTML 做白名单清洗。

    - 允许常见富文本标签（p/strong/em/ul/ol/li/h1-h4/img/a/pre/code 等）
    - 允许 a[href,target,rel]、img[src,alt] 等必要属性
    - 自动补充 a 的 rel="noopener noreferrer"（避免 tabnabbing）
    """

    if not html:
        return ""

    try:
        import bleach  # type: ignore
    except Exception:
        # 降级：移除 script 标签 + on* 事件属性
        cleaned = _SCRIPT_RE.sub("", html)
        cleaned = _ON_EVENT_ATTR_RE.sub("", cleaned)
        return cleaned

    allowed_tags = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "s",
        "blockquote",
        "pre",
        "code",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "hr",
        "span",
        "div",
        "img",
        "a",
    ]

    allowed_attrs = {
        "*": ["class"],
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "title"],
    }

    # 允许 http/https/mailto/以及站内相对路径
    allowed_protocols = ["http", "https", "mailto"]

    cleaned = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=allowed_protocols,
        strip=True,
    )

    # linkify 会自动把纯文本 URL 变成链接（可选），这里不开启，避免误伤。
    # 但我们要补充 rel。
    def _fix_rel(match: re.Match[str]) -> str:
        tag = match.group(0)
        # 若已经有 rel，直接返回
        if re.search(r"\srel=", tag, re.I):
            return tag
        # 若 target=_blank，补 rel
        if re.search(r"target=\"?_blank\"?", tag, re.I):
            return tag[:-1] + ' rel="noopener noreferrer">'
        return tag

    cleaned = re.sub(r"<a\b[^>]*>", _fix_rel, cleaned, flags=re.I)
    return cleaned
