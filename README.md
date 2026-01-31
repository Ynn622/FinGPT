# FinGPT 📈

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python版本">
  <img src="https://img.shields.io/badge/FastAPI-Framework-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/LineBot-SDK-brightgreen.svg" alt="LINE Bot">
  <img src="https://img.shields.io/badge/OpenAI-GPT--5.1-orange.svg" alt="OpenAI">
</p>

<p align="center">
  <strong>🚀 智慧台股分析助手 | 結合 AI 的投資決策工具</strong>
</p>

歡迎使用 FinGPT！一個結合 ChatGPT 與台股分析的智慧投資助手 🤖

FinGPT 是一個基於 LINE Bot 的台股分析工具，結合了 OpenAI GPT 的強大語言理解能力和豐富的股市數據源，為投資者提供即時、準確的股票分析和投資建議。

## ✨ 主要特色

- 🤖 **AI 智慧分析**：採用 GPT 進行股票技術面與基本面分析
- 📊 **即時股價資料**：整合 Yahoo Finance 提供最新股價資訊
- 📰 **新聞資訊整合**：自動抓取相關股票新聞進行分析
- 💹 **籌碼面分析**：提供三大法人買賣超資料
- 🔍 **智慧股票查詢**：支援股票名稱自動轉換為代號
- 📱 **LINE Bot 介面**：簡單易用的對話式操作
- ⚡ **快速回應**：平均分析時間少於 1 分鐘

## 🚀 功能特點

### 📈 核心功能
- **股價查詢與分析**：支援多種時間區間的歷史股價資料
- **技術指標分析**：包含開盤、收盤、最高、最低價及成交量分析
- **籌碼面資料**：外資、投信、自營商買賣超統計與趨勢分析
- **新聞情報分析**：即時抓取並分析股票相關新聞，提供市場情緒判斷
- **大盤指數追蹤**：支援加權指數、櫃買指數查詢與趨勢分析
- **智慧問答**：自然語言理解，支援多樣化的投資問題

### 支援範圍
- 🏢 台灣上市、上櫃股票  
- 📈 台灣加權指數、櫃買指數 (^TWOII)

## 📋 系統需求

- Python 3.9 或以上版本
- LINE Developers 帳號 並取得 Channel Access Token
- OpenAI API 金鑰
- Docker (可選，用於容器化部署)

## 📦 相依套件

| 套件名稱 | 版本 | 用途說明 |
|---------|------|----------|
| `fastapi` | latest | 高效能 Web 框架 |
| `uvicorn` | latest | ASGI 伺服器 |
| `openai` | latest | OpenAI GPT API 介接 |
| `openai-agents` | latest | OpenAI Agents 框架 |
| `line-bot-sdk` | latest | LINE Bot SDK |
| `yfinance` | latest | Yahoo Finance 資料源 |
| `beautifulsoup4` | latest | 網頁爬蟲解析 |
| `lxml` | latest | XML 解析器 |
| `cloudscraper` | latest | 雲端防護爬蟲 |
| `stockstats` | latest | 股票技術指標計算 |
| `pandas` | latest | 資料處理分析 |
| `numpy` | latest | 數值計算 |
| `requests` | latest | HTTP 請求處理 |
| `python-dotenv` | latest | 環境變數管理 |
| `python-multipart` | latest | 多部分表單處理 |

## 💬 使用方式

![FinGPT](https://github.com/user-attachments/assets/16ca59b9-68ba-4f75-9bc6-1936351accbc)

### 📱 基本操作
1. **加入好友**：掃描上方 QR Code 並加入 FinGPT 好友
2. **提出問題**：輸入您想詢問的股票相關問題
3. **傳送訊息**：按下傳送按鈕
4. **等待分析**：系統會在約 1 分鐘內完成分析
5. **查看結果**：獲得詳細的股市分析報告

### 查詢範例
```
台積電最近一個月的走勢如何？
鴻海的籌碼面分析
大盤今天的表現
聯發科有什麼新聞嗎？
```

## 🔧 程式架構

```
FinGPT/
├── app.py                     # FastAPI 主應用程式
├── requirements.txt           # 套件需求清單
├── Dockerfile                 # Docker 容器配置
├── README.md                  # 專案說明文件
├── services/                  # 服務層模組
│   ├── line_api.py           # LINE Bot API 處理
│   ├── function_tools.py     # AI Agent 工具函數
│   └── function_util.py      # 資料抓取與處理工具
└── util/                     # 公用工具模組
    └── logger.py             # 日誌記錄工具
```

### 🔍 主要模組說明

#### 📄 `app.py` - FastAPI 主應用程式
- **Web 框架**：基於 FastAPI 的高效能 Web 服務
- **路由管理**：統一管理 API 路由與中介軟體
- **認證機制**：保護 API 文件的基本認證
- **CORS 支援**：跨域請求處理

#### 📱 `services/line_api.py` - LINE Bot 服務
- **Webhook 處理**：接收並處理 LINE 平台訊息
- **訊息回覆**：格式化並回傳分析結果
- **錯誤處理**：完善的異常處理與用戶反饋

#### 🤖 `services/function_tools.py` - AI Agent 工具模組
- **AI Agent 整合**：整合 OpenAI Agents 框架進行智慧分析
- **工具函數管理**：提供股票分析所需的各種工具函數
- **時間處理**：取得當前時間資訊
- **股票查詢**：股票代號與名稱轉換
- **新聞抓取**：個股與大盤新聞資料整合

#### 🔧 `services/function_util.py` - 資料處理工具模組
- **股價資料抓取**：整合 Yahoo Finance 取得歷史股價
- **技術指標計算**：使用 StockStats 計算各種技術指標
- **籌碼面資料**：三大法人買賣超資料處理
- **新聞爬蟲**：多來源新聞資料抓取與解析
- **ETF 成分股**：ETF 持股明細查詢

#### 🛠️ `util/logger.py` - 日誌工具模組
- **函數裝飾器**：提供函數調用日誌記錄
- **錯誤追蹤**：自動記錄函數執行狀態與錯誤資訊
- **同步/異步支援**：支援一般函數與異步函數的日誌記錄

### 🔄 系統架構流程
```
用戶輸入 → LINE Bot API → AI Agent → 工具函數調用 → 資料處理 → 分析結果 → 回應用戶
   ↓           ↓            ↓           ↓           ↓         ↓         ↓ 
自然語言   FastAPI接收   GPT 分析   多源資料抓取  技術指標計算  AI整合分析  格式化回傳
```

### 📊 主要工具函數列表

#### 🤖 AI 核心函數
- **`askAI(question)`**：主要 AI 分析入口，整合所有工具進行股票分析

#### FunctionTool 工具
- **`toolGetCurrentTime()`**：取得台灣當前時間資訊
- **`toolFetchStockInfo()`**：股票名稱與代號查詢轉換
- **`toolGetStockPrice()`**：歷史股價與技術指標資料抓取
- **`toolFetchStockNews()`**：個股相關新聞資料抓取與分析
- **`toolFetchTwiiNews()`**：台股大盤新聞資料抓取
- **`toolFetchETFIngredients()`**：ETF 成分股持股明細查詢

#### 📈 資料處理函數
- **`fetchStockInfo(stockName)`**：股票基本資訊查詢
- **`getStockPrice(symbol, start, indicators)`**：股價資料與技術指標計算
- **`fetchStockNews(stockName)`**：個股新聞爬蟲處理
- **`fetchTwiiNews()`**：大盤指數新聞抓取

## 使用提醒

### 🔔 功能提醒
- **選單功能**：使用 LINE Bot 選單可快速查看大盤指數
- **查詢範圍**：目前支援台股上市、上櫃股票查詢
- **時間設定**：未指定分析期間時，預設為一個月資料
- **智慧查詢**：系統會自動嘗試股票代號查詢，提高查詢成功率

### 💡 使用技巧
- **明確的問題**：提出具體的股票名稱和分析需求
- **時間範圍**：可指定「最近一週」、「三個月」等時間範圍
- **多角度分析**：可同時要求技術面、基本面、籌碼面分析
- **比較分析**：可要求多檔股票的比較分析

## ⚠️ 注意事項

> ‼️ **重要提醒**：本系統提供的投資分析僅供參考，不構成投資建議。投資有風險，請謹慎評估自身財務狀況後進行投資決策。

### 免責聲明
- 📊 所有分析結果僅供參考
- 💰 投資決策請自行承擔風險
- 🔍 建議搭配其他資訊來源進行綜合判斷
- ⏰ 股價資料可能存在延遲

## 🤝 貢獻指南

歡迎提交 Issue 和 Pull Request 來改善這個專案！

---

<p align="center">
  <b>⭐ 如果這個專案對您有幫助，請給我們一個星星！ ⭐</b><br>
  Yn | @copyright 2025
</p>
