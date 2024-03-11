
import re
from bs4 import BeautifulSoup
import requests
from loguru import logger


# 替换非法字符
def rename(name):
    # 定义非法字符的正则表达式模式
    illegal_characters_pattern = r'[\/:*?"<>|]'

    # 定义替换的中文符号
    replacement_dict = {
        '/': '／',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '“',
        '<': '＜',
        '>': '＞',
        '|': '｜'
    }

    # 使用正则表达式替换非法字符
    sanitized_path = re.sub(illegal_characters_pattern, lambda x: replacement_dict[x.group(0)], name)

    return sanitized_path


def fix_publisher(text):
    # 针对性去除所有 出版物 所携带的标签
    text = re.sub(r'<p class=".*?">', '', text)
    text = re.sub(r'<!--\?xml.*?>', '', text)
    text = re.sub(r'<link .*?/>', '', text)
    text = re.sub(r'<meta .*?/>', '', text)
    text = re.sub(r'<h1 .*?>', '', text)
    text = re.sub(r'<br/>', '', text)
    text = re.sub(r'<!DOCTYPE html .*?>', '', text)
    text = re.sub(r'<span .*?>', '', text)
    text = re.sub(r'<html .*?>', '', text)
    return text


def get_fanqie(url, user_agent):
    headers = {
        "User-Agent": user_agent
    }

    # 获取网页源码

    try:
        response = requests.get(url, headers=headers, timeout=7)
    except requests.exceptions.Timeout:
        raise Exception("请求超时")

    if response.status_code == 404:
        raise Exception(f"请求失败，404")
    html = response.text

    # 解析网页源码
    soup = BeautifulSoup(html, "html.parser")

    # 获取小说标题
    title = soup.find("h1").get_text()
    # , class_ = "info-name"
    # 替换非法字符
    title = rename(title)

    # 获取小说信息
    info = soup.find("div", class_="page-header-info").get_text()

    # 获取小说简介
    intro = soup.find("div", class_="page-abstract-content").get_text()

    # 拼接小说内容字符串
    content = f"""如果需要小说更新，请勿修改文件名
使用 @星隅(xing-yv) 所作开源工具下载
开源仓库地址:https://github.com/xing-yv/fanqie-novel-download
Gitee:https://gitee.com/xingyv1024/fanqie-novel-download/
任何人无权限制您访问本工具，如果有向您提供代下载服务者未事先告知您工具的获取方式，请向作者举报:xing_yv@outlook.com

{title}
{info}
{intro}
"""

    # 获取所有章节链接
    chapters = soup.find_all("div", class_="chapter-item")

    # 通过标签得到完结信息
    finished_text = soup.find("span", class_="info-label-yellow").get_text()
    finished = 1 if finished_text == "已完结" else 0

    return headers, title, content, chapters, finished


def get_api(chapter, headers):
    # 获取章节标题
    chapter_title = chapter.find("a").get_text()

    # 获取章节网址
    chapter_url = chapter.find("a")["href"]

    # 获取章节 id
    chapter_id = re.search(r"/reader/(\d+)", chapter_url).group(1)

    # 构造 api 网址
    api_url = (f"https://novel.snssdk.com/api/novel/book/reader/full/v1/?device_platform=android&"
               f"parent_enterfrom=novel_channel_search.tab.&aid=2329&platform_id=1&group_id="
               f"{chapter_id}&item_id={chapter_id}")
    # 尝试获取章节内容
    chapter_content = None
    retry_count = 1
    while retry_count < 6:  # 设置最大重试次数
        try:
            # 获取 api 响应
            api_response = requests.get(api_url, headers=headers, timeout=5)

            # 解析 api 响应为 json 数据
            api_data = api_response.json()
        except Exception as e:
            if retry_count == 1:
                logger.warning(f"发生异常: {e}")
                logger.warning(f"{chapter_title} 获取失败，正在尝试重试...")
            logger.warning(f"第 ({retry_count}/5) 次重试获取章节内容")
            retry_count += 1  # 否则重试
            continue

        if "data" in api_data and "content" in api_data["data"]:
            chapter_content = api_data["data"]["content"]
            break  # 如果成功获取章节内容，跳出重试循环
        else:
            if retry_count == 1:
                logger.warning(f"{chapter_title} 获取失败，正在尝试重试...")
            logger.warning(f"第 ({retry_count}/5) 次重试获取章节内容")
            retry_count += 1  # 否则重试

    if retry_count == 6:
        logger.error(f"{chapter_title} 获取失败，已达到最大重试次数")
        return  # 重试次数过多后，跳过当前章节

    # 提取文章标签中的文本
    chapter_text = re.search(r"<article>([\s\S]*?)</article>", chapter_content).group(1)

    # 将 <p> 标签替换为换行符
    chapter_text = re.sub(r"<p>", "\n", chapter_text)

    # 去除其他 html 标签
    chapter_text = re.sub(r"</?\w+>", "", chapter_text)

    chapter_text = fix_publisher(chapter_text)

    return chapter_title, chapter_text, chapter_id
