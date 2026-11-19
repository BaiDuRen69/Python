import re
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
import requests
from pathlib import Path
from datetime import datetime
from urllib3.util.retry import Retry

URL_MDN = "https://developer.mozilla.org"
RAW_URLS:list[str]=['https://ghfast.top/','https://gh-proxy.com/','https://ghproxy.net/']


def canonical_url(url: str) -> str | None:
    """去掉锚点#、查询串?、尾部斜杠/，返回文档URL"""
    url = url.strip().split("#")[0].split("?")[0].rstrip("/")
    url=url.rstrip(").,;:!?]>}'\"")
    if not re.search(r"^https?://developer\.mozilla\.org/", url, re.I):
        return None
    return url


def read_text_file(urls_input) -> str|None:
    """从文本中获取链接时，返回文本内容"""
    path = Path(urls_input)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def manage_urls(urls_input) -> list[str]:
    """处理链接"""
    text = read_text_file(urls_input)
    if text is not None:
        urls_input = text
    urls_input = re.findall(r'(https?://[^\s]*)', urls_input, re.M)
    urls, urls_error = [], []
    for url_input in urls_input:
        url = canonical_url(url_input)
        if not url:
            urls_error.append(url_input)
            continue
        if url not in urls:
            urls.append(url)
    return urls, urls_error


def download_content(url: str, s) -> str:
    """下载文件内容，返回content"""
    if '/docs/' not in url:
        raise ValueError(f"不是文档页: {url}")
    path = url.split('docs', 1)[1].lower()
    url = ("https://raw.githubusercontent.com/mdn/translated-content/main/files/zh-cn" + path + "/index.md")

    for prefix in RAW_URLS:
        req_url = prefix.strip() + url
        try:
            r = s.get(req_url, timeout=(5, 30))
            r.raise_for_status()
            r.encoding = "utf-8"
            text= r.text
            if not text.lstrip().startswith('---'):
                raise requests.RequestException(f"内容异常: {req_url}")
            return text
        except requests.RequestException as e:
            continue
    return None


def get_url_title(url: str, s) -> str:
    """通过链接获取标题"""
    url = url.rstrip("/") + '/index.json'
    try:
        r = s.get(url, timeout=(5,10))
        r.raise_for_status()
        return r.json()['doc']['title']
    except (requests.RequestException, ValueError,KeyError):
        return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_title(content: str) -> str | None:
    """正则返回title"""
    m = re.search(r"^title:\s*[\"']?(.*?)[\"']?\s*$", content, re.M)
    return m.group(1).strip() if m else None


def delete_get_title(content: str, url: str, s) -> str:
    """调用get_title返回title并删除标题"""
    title = get_title(content)
    if not title:
        title = get_url_title(url, s)
    m = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)", flags=re.M)
    content = re.sub(m, "", content)
    return title, content


def fix_html_url(name: str) -> str:
    """只返回 href 的值，不包装标签"""
    if name.startswith("http"):
        return name
    if name.startswith("/"):
        return f"{URL_MDN}{name}"
    return f"{URL_MDN}/{name}"


def fix_menu_url(macro, params, s):
    parts = [p.strip().strip("'\"") for p in params.split(",")]
    # 去掉尾部可能存在的空项
    parts = [p for p in parts if p]
    urls = [f"https://developer.mozilla.org/zh-CN/docs/{p}" for p in parts]

    if macro == "PreviousMenuNext":
        prev, nxt = urls[0], urls[1]
    elif macro == "PreviousNext":
        prev, nxt = urls[0], urls[1]
    elif macro == "NextMenu":
        prev, nxt = None, urls[0]
    elif macro == "PreviousMenu":
        prev, nxt = urls[0], None
    else:
        return None

    menu = []
    if prev:
        menu.append(f"[上一章](<{get_url_title(prev, s)}.md>)")
    if nxt:
        menu.append(f"[下一章](<{get_url_title(nxt, s)}.md>)")
    return " · ".join(menu)


def fix_curly_url(line: str, args: list[str], s) -> str | None:
    """修复{{}}中的链接"""
    if not args[0]:
        return f"{line}====================================错误"
    if args[0] in ("NextMenu", "PreviousNext", "PreviousMenuNext","PreviousMenu"):
        return fix_menu_url(args[0],args[1], s)
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
        return f"=========={name}错误，未识别的元素============"

    return re.sub(
        r'\{\{\s*(.*?)\((.*?)\)\s*\}\}',
        lambda m: fix_element_url(m.group(1).lower(), m.group(2)),
        line
    )


def fix_url(line: str, url: str, s) -> str:
    """处理链接"""
    if m := re.search(r'\{\{\s*(.*?)\((.*?)\)\s*\}\}', line):
        line = fix_curly_url(line, m.groups(), s)
    if not line:
        return line
    line = re.sub(
        r'(<a\s+href=")([^"]*)(")',
        lambda m: m.group(1)+fix_html_url(m.group(2))+m.group(3),
        line,
    )
    line = re.sub(
        r"(!\[.*?\]\()([^)]*?)\)",
        lambda mm: f'{mm.group(1)}{urljoin(url.replace('zh-CN', 'en-US') + '/', mm.group(2))})',
        line
    )
    line = re.sub(
        r"(?<!!)(\[.*?\]\()(?!#)([^)]*?)\)",
        lambda mm: f'{mm.group(1)}{urljoin(URL_MDN, mm.group(2))})' if not re.search(r"\[(上一章|下一章)\]",
                                                                                     mm.group(0)) else mm.group(0),
        line
    )
    return line


def scan_lines(content: str, url: str, s) -> str:
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

        new_line = fix_url(line, url, s)
        # fix_url 返回 None 表示"这一行不要了"；返回 "" 也可能是合法结果
        if new_line is None:
            continue
        out.append(new_line)

    return '\n'.join(out)


def create_markdowm(content: str, title: str):
    """将文本内容保存为Markdown"""
    title = re.sub(r'[\\/:*?"<>|]', '_', title)
    base_dir = Path(r"D:\programme\GitHub\Markdown\HTML")
    # 确保目录存在（如果不存在则自动创建）
    base_dir.mkdir(parents=True, exist_ok=True)
    file_path = base_dir / f"{title}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)



if __name__ == "__main__":
    urls_input = input("可输入多个网址或单个文本路径：")
    urls, urls_error = manage_urls(urls_input)
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter=HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    if urls_error:
        print(f"错误链接：" + ' - '.join(urls_error))
    count = 0
    RAW_URLS.insert(0,' ')
    for url in urls:
        try:
            # 单个URL失败不中断整体
            content = download_content(url, s)
            if content is None:
                print(f"跳过 {url}:直连与镜像均失败")
                count+=1
                continue

            print(f"{url}====下载完成====正在处理格式====")
            title, content = delete_get_title(content, url, s)
            content = scan_lines(content, url, s)
            create_markdowm(content, title)
            print(f"{url}\n===============已完成==============={title}.md")
        except (requests.RequestException, ValueError,KeyError) as e:
            print(f"跳过 {url}：{typr(e).__name__}: {e}")
            count+=1
            continue
    print(f"============================================全部完成========================================================")
    print(f"一共输入正确链接={len(urls)}；成功={len(urls)-count}；失败={count}。")
