import os, requests

token = os.environ.get("GITHUB_TOKEN", "").strip()
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2026-03-10",
}

r = requests.get("https://api.github.com/user", headers=headers, timeout=30)
print(r.status_code)
print(r.json())
