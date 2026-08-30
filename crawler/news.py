import html
import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from util.taiwan_time import TaiwanTime


def FetchStockNews(stock_name: str) -> pd.DataFrame:
    """爬取指定股票最近 30 天的新聞資料。"""
    from crawler.stock_list import StockList

    def fetch_single_news(item):
        """抓取並解析單篇聯合新聞網文章。"""
        try:
            title = item["title"]
            news_time = datetime.strptime(item["time"]["date"], "%Y-%m-%d %H:%M")
            if time.mktime(time.gmtime()) - 30 * 24 * 3600 > news_time.timestamp():
                return None
            news_url = item["titleLink"]
            if not news_url.startswith("https://udn.com/news/story"):
                return None

            news = requests.get(news_url, timeout=10).text
            paragraphs = bs(news, "html.parser").find("section", class_="article-content__editor").find_all("p")[:-1]
            content = "\n".join(paragraph.text.strip() for paragraph in paragraphs)
            content = content.replace("\n\n", "\n").strip()
            return [news_time, news_url, title, content]
        except Exception as e:
            print(f"抓取新聞錯誤：{e}", end="\r")
            return None

    stock_id, _ = StockList.query_from_yahoo(stock_name)
    stock_id = stock_id.split(".")[0]
    stock_name = re.sub(r"[-*].*$", "", stock_name)
    url = f"https://udn.com/api/more?page=1&id=search:{stock_name}%20{stock_id}&channelId=2&type=searchword&last_page=100"
    json_news = requests.get(url, timeout=10).json().get("lists", [])[:10]

    data = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_single_news, item) for item in json_news]
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                data.append(result)

    frame = pd.DataFrame(data, columns=["Date", "URL", "Title", "Content"])
    frame = frame[["Date", "Title", "Content"]]
    return frame.sort_values(by="Date", ascending=False).reset_index(drop=True)


def FetchTwiiNews() -> pd.DataFrame:
    """爬取台灣加權指數與櫃買市場的最新新聞。"""
    end = TaiwanTime.now() - timedelta(days=1)
    start = end - timedelta(days=20)
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_quo?page=1&limit=15&startAt={int(start.timestamp())}&endAt={int(end.timestamp())}"
    web = requests.get(url, timeout=10).json()["items"]
    data = []
    for item in web["data"][: web["to"] - web["from"] + 1]:
        content = re.sub(r"<.*?>", "", html.unescape(item["content"]))
        if "http" in content:
            content = content[: content.find("http")]
        title = re.sub(r"^〈.*?〉", "", item["title"])
        news_time = time.strftime("%Y/%m/%d %H:%M", time.gmtime(item["publishAt"] + 28800))
        data.append([news_time, title, content])
    return pd.DataFrame(data, columns=["Date", "Title", "Content"])
