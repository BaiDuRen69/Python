import requests
# from urllib.parse import urljoin
# def get_titles(url: str,s):
#     """通过链接获取标题"""
#     url=url.rstrip("/")+'/index.json'
#     re=s.get(url).json()
#     return re['doc']['title']
# url="https://developer.mozilla.org/zh-CN/docs/Learn_web_development/Core/Structuring_content/Basic_HTML_syntax"
# s=requests.Session()
# print(get_titles(url,s))
a={1:'a',2:'b',3:'c'}
a={k:v+"1" for k,v in a.items()}
print(a)