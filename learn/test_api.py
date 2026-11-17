import requests, os, json

s = requests.Session()
token = os.getenv("GITHUB_TOKEN")
s.headers.update(
    {"Accept": "application/vnd.github.v3+json",
     "X-GitHub-Api-Version": "2026-03-10",
     "Authorization": f"token {token}"
     })
r = s.get("https://api.github.com/user", timeout=30)
r.raise_for_status()
params = {
    "sort": "pushed",
    "direction": "desc"
}
ropes = s.get(r.json()["repos_url"],params=params, timeout=30)
ropes.raise_for_status()
ropes_data = ropes.json()
# with open("ropes.json", "w") as f:
#     json.dump(ropes_data, f, indent=4)
s=""
for i, item in enumerate(ropes_data):
    s+=(f"|{i}|: {item["name"]}    ")
print(s)
while True:
    try:
        choose_rope=int(input("Choose a num for rope: "))
        if choose_rope < 0 or choose_rope > len(ropes_data):
            print("请输入有效的仓库前的数字")
    except ValueError:
        print("请输入一个整数")
    except EOFError:
        print("没有读到输入，程序退出")
        raise SystemExit(1)
rope_name=ropes_data[choose_rope]["name"]