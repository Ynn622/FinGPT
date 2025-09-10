from agents import function_tool
from agents import Agent, Runner, function_tool
import asyncio

from util import *  # 引入 util.py 中的所有輔助函數

async def askAI(question):
    agent = Agent(
        name="Finance Agent",
        model="gpt-4.1-mini",
        instructions="你是一名台灣股票分析師，請使用提供的工具，分析股票各面向並給予操作方向＆價位建議。（1.如果查無資料，可嘗試使用工具查詢代碼\n 2.若未提及需要分析的時間&技術指標時，預設為一個月且使用5&10MA，請先查詢今日日期\n 3.若無特別提及分析面向，請查詢股價&新聞）\n4.用簡單、完整又有禮貌的方式回答問題",
        tools=[toolGetCurrentTime, toolFetchStockInfo, toolGetStockPrice, toolFetchStockNews, toolFetchTwiiNews, toolFetchETFIngredients],
    )
    result = await Runner.run(agent, question)
    #print("Agent:",result.final_output)
    return result.final_output

@function_tool
async def toolGetCurrentTime() -> str:
    """
    取得目前的時間。
    Returns: 
        str: 當前時間的字串，格式為 "YYYY-MM-DD HH:MM:SS"。
    """
    print("🔵 [FunctionCall] toolGetCurrentTime()")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@function_tool
async def toolFetchStockInfo(stockName: str) -> str:
    """
    股票代號&名稱查詢。
    Args:
        stockName (str): 股票名稱或代碼，例如 "鴻海" 或 "2317"。
    Returns:
        str: 包含股票代號與名稱的字串。
    Example:
        toolFetchStockInfo("鴻海") -> ('2317.TW','鴻海')
    """
    print(f"🔵 [FunctionCall] toolFetchStockInfo({stockName})")
    try:
        stockID, stockName = fetchStockInfo(stockName)
        return stockID, stockName
    except Exception as e:
        print(f"🔴 [Error] toolFetchStockInfo({stockName}): {str(e)}")
        return f"Error fetching stock info: {stockName}!"


@function_tool
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
        str: 資料表格的字串格式。
    Example:
        toolGetStockPrice("2330.TW", "1mo")
        toolGetStockPrice("2330.TW", "2024-01-01", sdf_indicator_list=["close_5_sma", "close_10_ema", "macd", "kdjk", "kdjd", "rsi_5", "rsi_10"])
    """
    print(f"🔵 [FunctionCall] toolGetStockPrice({symbol}, {start}, sdf_indicator_list: {sdf_indicator_list}")
    try:
        data = getStockPrice(symbol, start, sdf_indicator_list)
        return data.to_string()
    except Exception as e:
        print(f"🔴 [Error] toolGetStockPrice({symbol}, {start}, sdf_indicator_list: {sdf_indicator_list}): {str(e)}")
        return f"Error fetching data for {symbol}!"
        
@function_tool
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
    print(f"🔵 [FunctionCall] toolFetchStockNews({stock_name})")
    try:
        data = FetchStockNews(stock_name)
        return data.to_string()
    except Exception as e:
        print(f"🔴 [Error] toolFetchStockNews({stock_name}): {str(e)}")
        return f"Error fetching news for {stock_name}"

@function_tool
async def toolFetchTwiiNews() -> str:
    """
    爬取台灣加權指數(^TWII)與櫃買市場(^TWOII)的最新新聞。
    Returns:
        str: 包含新聞時間、標題與內容的表格字串。
    Example:
        toolFetchTwiiNews()
    """
    print("🔵 [FunctionCall] toolFetchTwiiNews()")
    try:
        data = FetchTwiiNews()
        return data.to_string()
    except Exception as e:
        print(f"🔴 [Error] toolFetchTwiiNews(): {str(e)}")
        return f"Error fetching TWII news"

@function_tool
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
    print(f"🔵 [FunctionCall] toolFetchETFIngredients({ETF_name})")
    try:
        data = fetchETFIngredients(ETF_name)
        return data
    except Exception as e:
        print(f"🔴 [Error] toolFetchETFIngredients({ETF_name}): {str(e)}")
        return f"Error fetching ETF ingredients for {ETF_name}"