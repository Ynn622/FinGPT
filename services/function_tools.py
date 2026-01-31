from agents import Agent, Runner, function_tool
from agents.tool import WebSearchTool, UserLocation
import uuid

from services.function_util import *  # 引入 util.py 中的所有輔助函數

from util.logger import log_print
from util.nowtime import TaiwanTime
from util.ai_session import trim_session
from util.config import Env

class FinAgent(Agent):
    '''金融分析師 Agent'''
    def __init__(self, model: str):
        instructions = (
            "你是一名台灣股票分析師，請使用提供的工具，分析股票各面向並給予操作方向＆價位建議。首次詢問時,先詢問使用者的風險偏好再進行分析。"
            "（1.如果查無資料，可嘗試使用工具查詢代碼\n"
            f"2.若未提及需要分析的時間&技術指標時，預設為一個月且使用5&10MA，今天是{TaiwanTime.string()}\n"
            "3.若無特別提及分析面向，請查詢股價&新聞\n"
            "4.若非股市問題，請禮貌拒絕並告知使用者"
            "5.用簡潔重點的方式 500字內回答問題 ）"
        )
        super().__init__(
            name="Finance Agent",
            model=model,
            instructions=instructions,
            tools=[toolQueryStock, toolGetStockPrice, toolFetchStockNews, toolFetchTwiiNews, toolFetchETFIngredients],
            handoffs=[WebAgent(model=model)],
            handoff_description="當使用者的問題是金融相關，且無法從金融分析師 Agent 解決時，才交由 Web Agent 處理。非股票相關問題請直接回覆使用者，不要交給 Web Agent。"
        )

class WebAgent(Agent):
    '''Web 搜尋助理 Agent'''
    def __init__(self, model: str):
        instructions = "你是一名金融網路搜尋助理，將以禮貌、簡潔的方式整理回應。"
        super().__init__(
            name="Web Agent",
            model=model,
            instructions=instructions,
            tools=[WebSearchTool(UserLocation(type="approximate", country="TW"), search_context_size='low')]
        )

async def ask_AI_Agent(question: str, model: str = Env.AI_MODEL, session_id: str = str(uuid.uuid4()) ) -> str:
    """
    詢問 AI 並獲得回應。
    Args:
        question (str): 使用者的問題。
        model (str): 使用的 AI 模型名稱。
        session_id (str): 對話會話的唯一識別碼。
    Returns:
        str: AI 的回應內容。
    """
    session = await trim_session(session_id)
    result = await Runner.run(FinAgent(model=model), 
                              input= question+"(回答時，請簡潔重點即可)", 
                              session= session, 
                              max_turns= 10)
    return result.final_output.replace("#","").replace("**","*").strip()

@function_tool
@log_print
async def toolQueryStock(keyword: str) -> str:
    """
    股票代號&名稱查詢。
    Args:
        keyword (str): 股票名稱或代碼，例如 "鴻海" 或 "2317"。
    Returns:
        str: 包含股票代號與名稱的字串。
    Example:
        toolQueryStock("鴻海") -> ('2317.TW','鴻海')
    """
    from util.stock_list import StockList
    try:
        stockID, stockName = StockList.query(keyword)
        return stockID, stockName
    except Exception as e:
        return f"Error query stock info: {keyword}!"

@function_tool
@log_print
async def toolGetStockPrice(symbol: str, start: str, sdf_indicator_list: list[str]=[] ) -> str:
    """
    抓取 Yahoo Finance 的歷史股價資料與籌碼面資料。
    指數代號：（成交量單位為「億元」）
        - 加權指數：使用 "^TWII"
        - 櫃買指數：使用 "^TWOII"
    週線=5MA、月線=20MA、季線=60MA、半年線=120MA、年線=240MA
    Args:
        symbol (str): 股票代號，例如 "2330.TW" 或 "2317.TW"。
        start (str): 開始日期（格式："YYYY-MM-DD"），將只返回此日期之後的資料。
        sdf_indicator_list (list[str]): 欲計算的技術指標清單，stockstats - StockDataFrame 的指標名稱。
    Returns:
        str: 資料表格的字串，內含股價＆籌碼面＆技術指標資料。
    Example:
        toolGetStockPrice("2330.TW", "1mo")
        toolGetStockPrice("2330.TW", "2024-01-01", sdf_indicator_list=["close_5_sma", "close_10_ema", "macd", "kdjk", "kdjd", "rsi_5", "rsi_10"])
    """
    try:
        data = getStockPrice(symbol, start, sdf_indicator_list)
        return data.to_string()
    except Exception as e:
        return f"Error fetching data for {symbol}!"

@function_tool
@log_print
async def toolFetchStockNews(stock_name: str) -> str:
    """
    爬取指定股票的最新新聞資料。
    Args:
        stock_name (str): 股票名稱，例如 "台積電" 或 "鴻海"。
    Returns:
        str: 包含新聞日期、標題與內文的表格字串。
    Example:
        toolFetchStockNews("台積電")
    """
    try:
        data = FetchStockNews(stock_name)
        return data.to_string()
    except Exception as e:
        return f"Error fetching news for {stock_name}"

@function_tool
@log_print
async def toolFetchTwiiNews() -> str:
    """
    爬取台灣加權指數(^TWII)與櫃買市場(^TWOII)的最新新聞。
    Returns:
        str: 包含新聞時間、標題與內容的表格字串。
    Example:
        toolFetchTwiiNews()
    """
    try:
        data = FetchTwiiNews()
        return data.to_string()
    except Exception as e:
        return f"Error fetching TWII news"

@function_tool
@log_print
async def toolFetchETFIngredients(ETF_name: str) -> str:
    """
    查詢 ETF 的成分股。
    Args:
        ETF_name (str): ETF 名稱，例如 "0050" 或 "00878"。
    Returns:
        pd.DataFrame: 包含成分股的 DataFrame，包含股票代號、名稱、權重等資訊。
    Example:
        toolFetchETFIngredients("0050")
    """
    try:
        data = fetchETFIngredients(ETF_name)
        return data
    except Exception as e:
        return f"Error fetching ETF ingredients for {ETF_name}"