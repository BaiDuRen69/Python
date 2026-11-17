import os
import re
from pathlib import Path

import requests


class ReleaseError(RuntimeError):
    """业务错误，统一由 main 捕获并转成非零退出码。"""


class TokenError(RuntimeError):
    """"环境变量 GITHUB_TOKEN 未设置"""


API_ROOT = "https://api.github.com/repos/"
OWNER = "BaiDuRen69"


def make_session():
    """封装一个 GitHub REST API 专用的 requests.Session"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise TokenError("环境变量 GITHUB_TOKEN 未设置")
    s = requests.Session()
    s.headers.update({
        "User-Agent": "BaiDuRen69",
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    })
    return s


def read_file(path: str, encoding: str = 'utf-8') -> str:
    """读取文本文件；失败抛出异常。"""
    try:
        return open(path, encoding=encoding).read()
    except FileNotFoundError:
        raise ReleaseError(f"文件不存在：{path}")
    except PermissionError:
        raise ReleaseError(f'没有权限读取：{path}')
    except UnicodeDecodeError as e:
        raise ReleaseError(f'编码错误（期望 {encoding}）：{e}')
    except OSError as e:
        raise ReleaseError(f'读取失败：{e}')


def read_apk() -> Path:
    """输入地址读取apk，失败则抛 ReleaseError。"""
    while True:
        apk_path = input('请输入apk的地址：').strip().strip("'").strip('"')
        apk = Path(apk_path)
        if not apk.is_file():
            print("⚠️ 文件不存在或路径有误")
            continue
        size = apk.stat().st_size
        if size == 0:
            raise ReleaseError(f"APK 为空文件：{apk}")
            continue
        return apk


def read_tag(body: str, encoding: str = 'utf-8') -> str | None:
    """从第一个非空行中读取 tag，找不到则抛 ReleaseError。"""
    for line in body.splitlines():
        if line.split():
            if tag := re.search(r"v\d+.\d+.\d+", line):
                return tag.group()
            raise ReleaseError("没有找到标签")
    raise ReleaseError("没有找到标签")


def find_release(s: requests.Session, tag: str, repository: str):
    """查找是否已存在当前tag版本release"""
    r = s.get(f"{API_ROOT}{OWNER}/{repository}/releases/tags/{tag}", timeout=30)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        return None
    raise ReleaseError(f"查询 release 失败：{r.status_code} {r.text}")


def create_release(s: requests.Session, *, repository: str, tag: str, name: str, body: str,
                   target: str = "main", draft: bool = False,
                   prerelease: bool = False):
    """创建release"""
    payload = {
        "tag_name": tag,  # 标签名
        "target_commitish": target,  # 提交的Git分支，默认：仓库的默认分支
        "name": name,  # 发布的标题
        "body": body,  # 发布的描述（介绍）
        "draft": draft,  # true为创建草稿（不发布），false为创建并发布
        "prerelease": prerelease,  # true这次为预发布，false则为正式发布
        "generate_release_notes": True,
        # 是否自动生成本次发布的名称和正文。如果指定了名称，则使用指定的名称；否则将自动生成一个名称。如果指定了正文，则该正文将自动添加到生成内容的开头。默认：false
        "make_latest": "false" if (draft or prerelease) else "true",
        # 指定此版本是否应设置为仓库的最新版本。草稿版和预发行版不能设置为最新版本。新发布的默认版本默认为 true。legacy 表示应根据发布日期和更高的语义版本来确定最新版本。可以是以下选项之一: true, false, legacy
    }
    url = f"{API_ROOT}{OWNER}/{repository}/releases"
    r = s.post(url, json=payload, timeout=30)
    if r.status_code == 201:
        return r.json()
    if r.status_code == 404:
        return None
    if r.status_code == 422:
        return r.json()
    raise ReleaseError(f"查询 release 失败：{r.status_code} {r.text}")


def get_or_create_release(s: requests.Session, **kw):
    """查找是否存在该标签，存在->复用，不存在->创建"""
    rel = find_release(s, kw['tag'], kw['repository'])
    if rel:
        # 复用已有标签
        print(f"复用已有release：{rel['html_url']}")
        return rel
    # 创建新的release
    rel = create_release(s, **kw)
    print(f"已创建release：{rel['html_url']}")
    return rel


def delete_asset(s: requests.Session, asset: dict) -> None:
    """删除已有的同名附件文件名"""
    # GitHub 的删除 asset 接口只认 asset 的 id/url
    r = s.delete(asset["url"], timeout=30)
    if r.status_code not in (200, 204):
        raise ReleaseError(f"删除 asset {asset['name']} 失败：{r.status_code} {r.text}")


def upload_release(s: requests.Session, release: dict, apk: Path):
    """上传apk，apk为apk位置"""

    # 同名 asset 会让 GitHub 返回 422，先删以支持断点重跑
    # 同一个GitHub项目下，所有Release的附件文件名（basename）必须保持唯一，不能重复
    for asset in release.get("assets", []):
        if apk.name == asset["name"]:
            delete_asset(s, asset)
    asset_url = release["upload_url"].replace("{?name,label}", "")
    headers = {"Content-Type": "application/vnd.android.package-archive"}
    # 读取apk并上传
    with open(apk, "rb") as f:
        # requests 会为文件对象自动设置 Content-Length 并流式发送
        r = s.post(asset_url, headers=headers
                   , params={"name": apk.name}, data=f, timeout=600)

    if r.status_code == 201:
        print("已上传:", r.json()["browser_download_url"])
    else:
        print("上传失败:", r.status_code, r.text)


def choose_rope(s: requests.Session) -> str:
    """列出仓库来选择，返回仓库名"""
    params = {
        "sort": "pushed",
        "direction": "desc"
    }
    ropes = s.get(API_ROOT, params=params, timeout=30)
    ropes.raise_for_status()
    ropes_data = ropes.json()
    ropes_str = ""
    for i, item in enumerate(ropes_data):
        ropes_str += (f"|{i}|: {item["name"]}    ")
    print(ropes_str)
    while True:
        try:
            choose_rope = int(input("Choose a num for rope: "))
            if choose_rope < 0 or choose_rope > len(ropes_data):
                print("请输入有效的仓库前的数字")
        except ValueError:
            print("请输入一个整数")
        except EOFError:
            print("没有读到输入，程序退出")
            raise SystemExit(1)
    rope_name = ropes_data[choose_rope]["name"]
    return rope_name


def main():
    s = make_session()

    body = read_file("a.md")
    tag = read_tag(body)
    apk = read_apk()
    rope = choose_rope(s)

    rel = get_or_create_release(s,
                                repository=rope,
                                tag=tag,
                                name=tag,
                                body=body,
                                target="main",
                                draft=False,
                                prerelease=False)
    upload_release(s, rel, apk)


if __name__ == '__main__':
    main()
