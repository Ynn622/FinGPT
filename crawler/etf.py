import requests
from bs4 import BeautifulSoup as bs


def fetchETFIngredients(ETF_name: str) -> str:
    """查詢 ETF 的成分股。"""
    url = f"https://tw.stock.yahoo.com/quote/{ETF_name}/holding"
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=header, timeout=10)
    soup = bs(response.text, "html.parser")
    table = soup.find_all(
        "ul", class_="Bxz(bb) Bgc($c-light-gray) Bdrs(8px) P(20px)"
    )[1].find_all("li")[1:]
    return "".join(item.text.strip() + "\n" for item in table)
