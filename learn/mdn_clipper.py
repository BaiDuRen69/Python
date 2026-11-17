import re
from tokenize import group
from turtledemo.chaos import line
from urllib.parse import urljoin
import requests
import json
import os

URL_MDN = "https://developer.mozilla.org"


def canonical_url(url: str) -> str:
    """去掉锚点#、查询串?、尾部斜杠/，返回文档URL"""
    url = url.strip().split("#")[0].split("?")[0].rstrip("/")
    if not re.search(r"^https?://developer\.mozilla\.org/", url, re.I):
        raise ValueError(f"不是 developer.mozilla.org 的文档 URL：{url}")
    return url


def download_content(url: str) -> str:
    """下载文件内容，返回content"""
    url = ("https://raw.githubusercontent.com/mdn/translated-content/main/files/zh-cn"
           + url.split('docs')[-1].lower() + "/index.md")
    r = requests.get(url)
    return r.text


def get_title(content):
    """正则返回title"""
    title = re.search(r"title:\s*(.*)", content)
    if not title:
        raise Exception("没有标题")
    return title.group(1)


def delete_get_title(content: str) -> str:
    """调用get_title返回title并删除标题"""
    title = get_title(content)
    m = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)", flags=re.M)
    content = re.sub(m, "", content)
    return title, content


def fix_html_url(name: str) -> str:
    """处理<a>的网址"""
    if name.startswith("http"):
        return name
    return f"<a href=\"{URL_MDN}/{name}\">"


def get_titles(url: str,s):
    """通过链接获取标题"""
    url = url.rstrip("/")+'/index.json'
    re=s.get(url).json()
    return re['doc']['title']


def fix_menu_url(args):
    """处理顶部和底部的菜单menu的链接"""
    args = [arg.strip().strip("'").strip('"')
            for arg in args
            for arg in arg.strip().split(',')
            ]
    m = re.findall(r"[A-Z][a-z]+", args[0])
    if not m:
        return None
    args=[f'https://developer.mozilla.org/zh-CN/docs/{arg}' for arg in args[1:]]
    dics = dict(zip(m, args))
    s=requests.Session()
    dic_titles={k:get_titles(v,s) for k,v in dics.items() if k!='Menu'}
    menu=[]
    for k,v in dic_titles.items():
        if k=='Previous':
            menu.append(f"[上一章](<{v}.md>)")
        elif k=='Next':
            menu.append(f"[下一章](<{v}.md>)")
    return ' · '.join(menu)


def fix_curly_url(line, args):
    """修复{{}}中的链接"""
    if args[0] in ("NextMenu", "PreviousNext", "PreviousMenuNext"):
        return fix_menu_url(args)
    elif args[0] == 'EmbedLiveSample':
        # 直接删除
        return None

    def fix_element_url(name, args):
        """处理element元素"""
        args = [arg.strip().strip("'").strip('"') for arg in args.split(',')]
        if name == 'glossary':
            return (f"[{args[1] if len(args) > 1 and args[1] else args[0]}]"
                    f"(https://developer.mozilla.org/zh-CN/docs/glossary/{args[0].replace(' ', '_')}) ")
        elif name == 'htmlelement':
            return f"[`<{args[0]}>`](https://developer.mozilla.org/zh-CN/docs/Web/HTML/Reference/Elements/{args[0]})"

    return re.sub(
        r'\{\{\s*(.*?)\((.*?)\)\s*\}\}',
        lambda m: fix_element_url(m.group(1), m.group(2)),
        line
    )
    return "==========错误，未识别的元素============"


def fix_url(line, url):
    """处理链接"""
    if m := re.search(r'\{\{\s*(.*?)\((.*?)\)\s*\}\}', line):
        line = fix_curly_url(line, m.groups())
    if not line:
        return line
    line = re.sub(
        r'<a href="([^"]*)">',
        lambda mm: fix_html_url(mm.group(1)),
        line,
    )
    line = re.sub(
        r"(!\[.*?\]\()([^)]*?)\)",
        lambda mm: f'{mm.group(1)}{urljoin(url.replace('zh-CN', 'en-US') + '/', mm.group(2))})',
        line
    )
    line = re.sub(
        r"(?<!!)(\[.*?\]\()(?!#)([^)]*?)\)",
        lambda mm: f'{mm.group(1)}{urljoin(URL_MDN, mm.group(2))})'if not re.search(r"\[.{1}一章\]",mm.group(0)) else mm.group(0),
        line
    )
    return line


def scan_lines(content: str, url: str) -> list:
    """逐行处理"""
    content = content.replace("\r\n", "\n")

    # 配备代码块
    fence_re = re.compile(r"^[ \t]*(?:>[ \t]*)?(`{3,}|~{3,})")
    out: list[str] = []
    in_fence = False
    fence_char, fence_len = '', 0
    for line in content.split('\n'):
        fm = fence_re.match(line)

        if fm:
            marker = fm.group(1)
            char, length = marker[0], len(marker)
            if not in_fence:
                # 开代码块
                in_fence, fence_char, fence_len = True, char, length
                out.append(line)
                continue
            # 已在代码块中：只有同字符且长度 >= 开启长度才是关闭
            if char == fence_char and length >= fence_len:
                in_fence = False
                out.append(line)
                continue
            # 代码块内部的伪 fence 行，原样保留
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        # 空行原样保留，避免段落粘连
        if not line.strip():
            out.append(line)
            continue

        new_line = fix_url(line, url)
        # fix_url 返回 None 表示"这一行不要了"；返回 "" 也可能是合法结果
        if new_line is None:
            continue
        out.append(new_line)

    return '\n'.join(out)


def create_markdowm(content: str, title: str):
    """将文本内容保存为Markdown"""
    with open(f"{title}.md", "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    url_input = input("输入网址")
    url = canonical_url(url_input)
    content = download_content(url)
    print("====下载完成====正在处理格式====")
    title, content = delete_get_title(content)
    content = scan_lines(content, url)
    create_markdowm(content, title)
    print(f"{url}\n===============已完成==============={title}.md")
