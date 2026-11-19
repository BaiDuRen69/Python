#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mdn_clip.py - 从 MDN 官方源 Markdown 生成干净的剪藏笔记（纯标准库，无需 pip 安装）。

为什么不用浏览器剪藏器：
  MDN 学习区页面是"交互式文档"，含 <details> 折叠答案、iframe 内嵌可运行示例、
  Playground 按钮。通用剪藏器读取的是「渲染后的 DOM」，会把 <summary> 摊平成裸文本
  （"点击这里显示解决方案"）、把答案平铺、把 iframe 变成"运行"二字，示例代码随之丢失。
  这些信息在 HTML -> Markdown 那一步就已经丢了，换模板、换插件都救不回来。

本脚本改为读取 MDN 自己发布的源数据：
  1) https://developer.mozilla.org/<locale>/docs/<slug>/index.json
     官方 JSON 接口，doc.source.github_url 直接指向该页的作者原稿 index.md。
  2) raw.githubusercontent.com 上的 index.md
     作者写的 Markdown：代码块带语言、<details> 完整、图片与链接都是原始相对路径。
  再对 KumaScript 宏、相对路径、折叠块做确定性清洗，输出 Obsidian 友好的 Markdown。

用法：
  python mdn_clip.py "https://developer.mozilla.org/zh-CN/docs/Learn_web_development/Core/Structuring_content/Basic_HTML_syntax"
  python mdn_clip.py URL1 URL2 ...              # 批量
  python mdn_clip.py URL --stdout               # 只看结果，不写文件
  python mdn_clip.py URL --fold details         # 保留原生 <details>（跨 Markdown 阅读器通用）
  python mdn_clip.py URL --force                # 允许覆盖同名文件
  python mdn_clip.py URL --name "自定义文件名.md"
  python mdn_clip.py URL --no-frontmatter       # 不写 YAML frontmatter
  python mdn_clip.py URL --summary "点击这里显示解决方案"   # 保留 MDN 原折叠标题

输出目录默认为脚本同目录下的 Clippings/。
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

MDN_ORIGIN = "https://developer.mozilla.org"
UA = "Mozilla/5.0 (compatible; mdn_clip/1.0; +local markdown archiver)"

# 已知术语表：Glossary slug 不是简单的下划线拼接，常见不规则项在此兜底
GLOSSARY_SLUGS = {
    "html": "HTML",
    "css": "CSS",
    "javascript": "JavaScript",
    "dom": "DOM",
    "api": "API",
    "url": "URL",
    "uri": "URI",
    "http": "HTTP",
    "https": "HTTPS",
    "utf-8": "UTF-8",
    "ide": "IDE",
    "boolean attribute": "Boolean/HTML",
    "void element": "Void_element",
    "character reference": "Character_reference",
    "element": "Element",
    "tag": "Tag",
    "attribute": "Attribute",
    "doctype": "Doctype",
}

# 代码块围栏里的非标准 info string（MDN 作者标记）统一收敛成通用语言名
LANG_ALIASES = {
    "html-nolint": "html",
    "html": "html",
    "css-nolint": "css",
    "css": "css",
    "js-nolint": "js",
    "js": "js",
    "javascript": "js",
    "json": "json",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "plain": "",
    "text": "",
    "": "",
}


def log(msg):
    """日志函数，输出到标准错误流"""
    print(msg, file=sys.stderr)


def fetch(url):
    """获取源文件的内容"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def canonical_url(url):
    """去掉锚点、查询串、尾部斜杠，得到文档 URL。"""
    url = url.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    if not re.match(r"^https?://developer\.mozilla\.org/", url, re.I):
        raise ValueError("不是 developer.mozilla.org 的文档 URL：%s" % url)
    return url


def get_doc_meta(doc_url):
    """通过mdn的接口获取GitHub上的Markdown源文件链接"""
    data = json.loads(fetch(doc_url + "/index.json"))
    doc = data["doc"]
    src = doc.get("source") or {}
    gh = src.get("github_url")
    if not gh:
        raise RuntimeError("该页没有官方源 Markdown（index.json 缺少 source.github_url）")
    return doc, gh


def to_raw_url(github_blob_url):
    """https://github.com/o/r/blob/main/path -> https://raw.githubusercontent.com/o/r/main/path"""
    m = re.match(
        r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", github_blob_url
    )
    if not m:
        raise ValueError("无法解析 GitHub 源地址：%s" % github_blob_url)
    owner, repo, branch, path = m.groups()
    path = path.split("?", 1)[0]
    return "https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, path)


# 同时识别顶层 ``` 和 callout 内 > ``` 两种围栏
FENCE_RE = re.compile(r"^\s*(?:>\s*)?(`{3,}|~{3,})")


def scan_lines(text, on_outside, on_fence=None):
    """逐行处理，跳过代码块内部（含 Obsidian callout 内的代码块）。"""
    out = []
    in_fence = False
    ch = None
    for line in text.split("\n"):
        fm = FENCE_RE.match(line)
        if fm and not in_fence:
            in_fence, ch = True, fm.group(1)[0]
            out.append(on_fence(line) if on_fence else line)
        elif fm and in_fence and fm.group(1)[0] == ch:
            in_fence, ch = False, None
            out.append(line)
        elif not in_fence:
            out.append(on_outside(line))
        else:
            out.append(line)
    return out


# ---------------------------------------------------------------- KumaScript


def parse_macro(inner):
    """解析宏"""
    m = re.match(r"^([A-Za-z_][\w]*)\s*(?:\((.*)\))?\s*$", inner.strip(), re.S)
    if not m:
        return None, []
    name = m.group(1).lower()
    argstr = m.group(2) or ""
    args = []
    for a, b, c in re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,\s]+)', argstr):
        args.append(a or b or c)
    return name, args


def glossary_slug(key):
    k = key.strip().lower()
    if k in GLOSSARY_SLUGS:
        return GLOSSARY_SLUGS[k]
    words = re.split(r"[\s/]+", key.strip())
    return "_".join(w[:1].upper() + w[1:] for w in words if w)


def expand_macros(md, doc, warnings):
    """展开宏"""
    locale = doc.get("locale", "en-US")
    base = MDN_ORIGIN + "/" + locale + "/docs/"
    doc_url = MDN_ORIGIN + doc["mdn_url"]

    def repl(m):
        """重做宏"""
        raw = m.group(0)
        name, args = parse_macro(m.group(1))
        if name is None:
            warnings.append("无法解析的宏：" + raw[:60])
            return "<!-- 未展开的 MDN 宏：%s -->" % raw.replace("-->", "-- >")

        a0 = args[0] if args else ""
        a1 = args[1] if len(args) > 1 else ""

        if name in ("nextmenu", "previousnext", "previousmenunext"):
            # NextMenu(下一页 slug, 章节目录 slug)
            parts = []
            if len(args) > 1:
                parts.append("[章节目录](%s%s)" % (base, args[1].lstrip("/")))
            if a0:
                parts.append("[下一页](%s%s)" % (base, a0.lstrip("/")))
            return " · ".join(parts) if parts else ""

        if name == "glossary":
            label = a1 or a0
            return "[%s](%sGlossary/%s)" % (label, base, glossary_slug(a0))

        if name in ("htmlelement", "htmlattrxref"):
            if name == "htmlelement":
                label = "`<%s>`" % a0
                target = "Web/HTML/Reference/Elements/" + a0
            else:
                label = "`%s`" % a0
                target = "Web/HTML/Reference/Attributes/" + a0
            return "[%s](%s%s)" % (label, base, target)

        if name == "cssxref":
            label = a1 or a0
            return "[`%s`](%sWeb/CSS/Reference/Properties/%s)" % (label, base, a0)

        if name == "jsxref":
            label = a1 or a0
            return "[`%s`](%sWeb/JavaScript/Reference/Global_Objects/%s)" % (label, base, a0)

        if name == "domxref":
            label = a1 or a0
            return "[`%s`](%sWeb/API/%s)" % (label, base, a0)

        if name in ("httpheader", "httpmethod", "httpstatus"):
            label = "`" + a0 + "`"
            return "[%s](%sWeb/HTTP/Reference/Headers/%s)" % (label, base, a0)

        if name in ("embedlivesample", "embedghlivesample", "embedinteractiveexample",
                    "interactiveexample", "embedinteractiveexample"):
            return "<!-- MDN 在线示例：%s；运行地址 %s -->" % (a0, doc_url)

        if name in ("compat", "specifications", "browsercompat", "seecompattable"):
            return "<!-- MDN 动态区块（浏览器兼容性/规范表）：%s，请查看原文 %s -->" % (
                name, doc_url
            )

        if name in ("deprecated_inline", "non-standard_inline", "experimental_inline"):
            friendly = {
                "deprecated_inline": "已弃用",
                "non-standard_inline": "非标准",
                "experimental_inline": "实验性",
            }
            return "**%s**" % friendly[name]

        if name in ("learnsidebar", "cssref", "jsref", "domref", "htmlref", "sidebar"):
            return ""  # 纯导航宏，源 Markdown 正文不需要

        warnings.append("未识别的宏：%s" % name)
        return "<!-- 未展开的 MDN 宏：%s -->" % raw.replace("-->", "-- >")

    lines = scan_lines(md,
                       lambda line: re.sub(r"\{\{(.*?)\}\}", repl, line, flags=re.S),
                       )
    return "\n".join(lines)


# ---------------------------------------------------------------- 折叠答案块


def convert_details(md, mode, summary=None):
    if mode == "details" and not summary:
        return md

    # 只匹配「独占一行」的块级 <details>。行内代码里的 `<details>` 不能被吞掉。
    pattern = re.compile(
        r"(?m)^[ \t]*<details[^>]*>[ \t]*\r?\n(?P<body>.*?)^[ \t]*</details>[ \t]*$",
        re.S,
    )

    def repl(m):
        # 再防一层：跳过示例代码块里出现的同名标签
        fences = re.findall(r"(?m)^\s*(?:>\s*)?(?:`{3,}|~{3,})", m.string[:m.start()])
        if len(fences) % 2:
            return m.group(0)

        whole = m.group(0)
        start_tag = re.match(r"[ \t]*(<details[^>]*>)", whole).group(1)
        block = m.group("body")
        sm = re.search(r"<summary[^>]*>(.*?)</summary>", block, re.S | re.I)
        original = re.sub(r"<[^>]+>", "", sm.group(1)).strip() if sm else "展开查看详情"
        title = summary or original

        if mode == "details":
            new_block = block
            if sm and summary:
                new_block = block[:sm.start()] + re.sub(
                    r"(<summary[^>]*>).*?(</summary>)",
                    lambda x: x.group(1) + summary + x.group(2),
                    block[sm.start():sm.end()],
                    flags=re.S,
                ) + block[sm.end():]
            return "%s\n%s\n</details>" % (start_tag, new_block.strip("\n"))

        body = (block[sm.end():] if sm else block).strip("\n")
        body = re.sub(r"\n{3,}", "\n\n", body)
        if mode == "plain":
            return "**%s**\n\n%s" % (title, body)
        # Obsidian 折叠标注：内容每行加 ">"，里面的代码块也能正常渲染
        quoted = "\n".join(("> " + ln) if ln.strip() else ">" for ln in body.split("\n"))
        return "> [!example]- %s\n>\n%s" % (title, quoted)

    return pattern.sub(repl, md)


# ---------------------------------------------------------------- 代码块围栏


def normalize_fence(line):
    """规范化围栏"""
    m = re.match(r"^(\s*(?:>\s*)?)(`{3,}|~{3,})([^\n]*)$", line)
    if not m:
        return line
    indent, ticks, info = m.groups()
    tokens = info.strip().split()
    lang = LANG_ALIASES.get(tokens[0].lower(), tokens[0].lower()) if tokens else ""
    # 丢弃 live-sample___id / hidden / example-bad / html-nolint 等 MDN 专属标记
    return "%s%s%s" % (indent, ticks, lang)


def normalize_all_fences(md):
    """规范化所以围栏"""
    out = []
    in_fence = False
    ch = None
    for line in md.split("\n"):
        m = FENCE_RE.match(line)
        if m and not in_fence:
            out.append(normalize_fence(line))
            in_fence, ch = True, m.group(1)[0]
        elif m and in_fence and m.group(1)[0] == ch:
            out.append(line.rstrip())
            in_fence, ch = False, None
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- 链接绝对化


def absolutize(md, doc):
    """链接绝对化"""
    doc_url = MDN_ORIGIN + doc["mdn_url"]
    asset_base = doc_url.rstrip("/") + "/"

    def fix_target(target):
        """处理链接"""
        t = target.strip()
        if not t or t.startswith(("http://", "https://", "#", "mailto:", "//", "data:")):
            return t
        if t.startswith("/"):
            return MDN_ORIGIN + t
        # 相对文件名（通常是图片）：挂到当前文档目录下
        return asset_base + t

    def outside(line):
        """处理图片、href 链接"""
        # Markdown 链接 / 图片
        line = re.sub(
            r"(\]\()([^)\s]+)(\))",
            lambda m: m.group(1) + fix_target(m.group(2)) + m.group(3),
            line,
        )
        # HTML 属性里的站内绝对路径
        line = re.sub(
            r'((?:href|src)=")/(?!/)([^"]*)"',
            lambda m: m.group(1) + MDN_ORIGIN + "/" + m.group(2) + '"',
            line,
        )
        return line

    return "\n".join(scan_lines(md, outside))


# ---------------------------------------------------------------- 组装输出


def build(doc, source_md, args):
    warnings = []
    # 把来自不同平台、不同编辑器的文本统一成同一种换行格式，避免后续按行处理、正则
    # 匹配、字符串比较、渲染解析时因 \r 残留而产生难以察觉的 bug。 这是文本处理里非常常见的一步"清洗"操作。
    md = source_md.replace("\r\n", "\n")

    # frontmatter 之后才是正文
    fm = ""
    # 去除换行
    if md.startswith("---\n"):
        end = md.find("\n---", 4)
        if end != -1:
            fm = md[4:end]
            md = md[end + 4:].lstrip("\n")

    def plain_title(raw):
        txt = html.unescape(re.sub(r"<[^>]+>", "", raw or "")).strip()
        return txt.lstrip(":： ").strip()

    # 参考页的 short_title 常是纯标签（如 "<details>"），剥离后会空，需回退到完整标题
    title = (plain_title(doc.get("short_title"))
             or plain_title(doc.get("title"))
             or "MDN 文档")
    source_commit = ""
    sc = re.search(r"sourceCommit:\s*(\S+)", fm)
    if sc:
        source_commit = sc.group(1)

    md = expand_macros(md, doc, warnings)
    md = convert_details(md, args.fold, args.summary)
    md = normalize_all_fences(md)
    md = absolutize(md, doc)

    # 压缩多余空行
    md = re.sub(r"\n{4,}", "\n\n\n", md).strip("\n")

    if not re.search(r"^# ", md, re.M):
        md = "# %s\n\n%s" % (title, md)

    if not args.no_frontmatter:
        today = datetime.date.today().isoformat()
        modified = (doc.get("modified") or "")[:10]
        gh = (doc.get("source") or {}).get("github_url", "")

        def esc(s):
            return str(s).replace("\\", "\\\\").replace('"', '\\"')

        header = [
            "---",
            'title: "%s"' % esc(title),
            'source: "%s"' % esc(MDN_ORIGIN + doc["mdn_url"]),
            'author: "MDN Web Docs"',
            'clipped: %s' % today,
        ]
        if modified:
            header.append("mdn_modified: %s" % modified)
        if gh:
            header.append('mdn_source: "%s"' % esc(gh))
        if source_commit:
            header.append("mdn_source_commit: %s" % source_commit)
        header += ["tags:", "  - clippings", "  - mdn", "---", ""]
        md = "\n".join(header) + "\n" + md

    return md + "\n", title, warnings


def safe_filename(name):
    """保存文件名"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "mdn_clip"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="从 MDN 官方源 Markdown 剪藏为干净的笔记")
    ap.add_argument("urls", nargs="+", help="一个或多个 MDN 文档 URL")
    ap.add_argument("--out", default=None, help="输出目录（默认脚本同目录的 Clippings/）")
    ap.add_argument("--name", default=None, help="输出文件名（仅单 URL 时有效）")
    ap.add_argument("--stdout", action="store_true", help="只打印到标准输出，不写文件")
    ap.add_argument("--force", action="store_true", help="允许覆盖同名文件")
    ap.add_argument("--no-frontmatter", action="store_true", help="不生成 YAML frontmatter")
    ap.add_argument("--fold", choices=["callout", "details", "plain"], default="callout",
                    help="折叠答案块的写法：callout=Obsidian 折叠标注（默认）；"
                         "details=原生 <details>；plain=完全展开")
    ap.add_argument("--summary", default="参考答案",
                    help="折叠块标题（默认「参考答案」；传 --summary 原文可保留 MDN 原句）")
    args = ap.parse_args()

    out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Clippings")
    if not args.stdout:
        os.makedirs(out_dir, exist_ok=True)

    failed = 0
    for url in args.urls:
        try:
            doc_url = canonical_url(url)
            log("[1/3] 读取文档元数据 %s" % doc_url)
            doc, gh = get_doc_meta(doc_url)
            raw = to_raw_url(gh)
            log("[2/3] 下载官方源 Markdown %s" % raw)
            source_md = fetch(raw)

            result, title, warnings = build(doc, source_md, args)
            for w in sorted(set(warnings)):
                log("      提醒：%s（原文已保留为 HTML 注释）" % w)

            if args.stdout:
                sys.stdout.write(result)
                continue

            filename = safe_filename(args.name or title) + (
                "" if (args.name or "").lower().endswith(".md") else ".md"
            )
            path = os.path.join(out_dir, filename)
            if os.path.exists(path) and not args.force:
                stem, ext = os.path.splitext(filename)
                path = os.path.join(out_dir, "%s (源版)%s" % (stem, ext))
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(result)
            log("[3/3] 已写入 %s（%d 字符）" % (path, len(result)))
        except Exception as e:
            failed += 1
            log("失败：%s -> %s: %s" % (url, type(e).__name__, e))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
