"""
学习资料《Python-100-Days-master》生成下一节跳转链接

为1~99添加跳转下一节的链接
链接格式为：
[下一节：下一节文件名](../相对路径/文件名.md)
"""


import re
from pathlib import Path, PureWindowsPath


def get_number(file_name):
    """
    获取文件序号,返回第一组
    用于文件排序
    """
    # 正则匹配数字开头的文件
    match = re.match(r"^(\d+)", file_name)
    if match:
        return int(match.group(1))  # 返回数字
    return 0


def add_next_file_link(file_list, file_dict, folder_path):
    """
    添加下一节的链接至文件
    :param file_list: 文件名列表
    :param file_dict: 文件名:文件
    :param folder_path: 操作目录、文件所在目录
    :return:
    """
    for index, file_name in enumerate(file_list):
        if index + 1 >= len(file_list):
            continue
        next_file_name = file_list[index + 1]
        with open(file_dict[file_name], "a", encoding="utf-8") as f:
            file_path = file_dict[next_file_name].relative_to(folder_path)
            new_file_path = PureWindowsPath(file_path).as_posix()
            f.write(f"\n[下一节：{next_file_name}](../{new_file_path})")


def clean_repeated_link(file_list, file_dict):
    """
    清理重复的跳转链接
    :param file_list: 文件名列表
    :param file_dict: 文件名:文件
    :return:
    """
    clean_key_word = "[下一节"
    for file_name in file_list:
        with open(file_dict[file_name], 'r', encoding='utf-8') as fr:
            lines = [line for line in fr if clean_key_word not in line]
        with open(file_dict[file_name], 'w', encoding='utf-8') as fw:
            fw.writelines(lines)


folder_path="D:\\programme\\GitHub\\Markdown\\学习资料\\Python-100-Days-master"
# folder_path = "D:\\下载\\Python-100-Days-master\\Python-100-Days-master"
file_list = []
file_dict = {}
for file in Path(folder_path).rglob("*.md"):
    if re.match(r"^(\d+)", file.name):
        file_list.append(file.name)
        file_dict[file.name] = file
file_list.sort(key=get_number)
clean_repeated_link(file_list, file_dict)
add_next_file_link(file_list, file_dict, folder_path)
