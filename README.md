# FinGPT 📈

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python版本">
 
  <img src="https://img.shields.io/badge/LineBot-SDK-brightgreen.svg" alt="LINE Bot">
  <img src="https://img.shields.io/badge/OpenAI-GPT--4.1-orange.svg" alt="OpenAI">
</p>

歡迎使用 FinGPT！一個結合 ChatGPT 與台股分析的智慧投資助手 🤖

FinGPT 是一個基於 LINE Bot 的台股分析工具，結合了 OpenAI GPT-4.1 的強大語言理解能力和豐富的股市數據源，為投資者提供即時、準確的股票分析和投資建議。

## ✨ 主要特色

- 🤖 **AI 智慧分析**：採用 GPT-4.1 進行股票技術面與基本面分析
- 📊 **即時股價資料**：整合 Yahoo Finance 提供最新股價資訊
- 📰 **新聞資訊整合**：自動抓取相關股票新聞進行分析
- 💹 **籌碼面分析**：提供三大法人買賣超資料
- 🔍 **智慧股票查詢**：支援股票名稱自動轉換為代號
- 📱 **LINE Bot 介面**：簡單易用的對話式操作

## 🚀 功能特點

### 核心功能
- **股價查詢與分析**：支援多種時間區間的歷史股價資料
- **技術指標分析**：包含開盤、收盤、最高、最低價及成交量
- **籌碼面資料**：外資、投信、自營商買賣超統計
- **新聞情報分析**：即時抓取並分析股票相關新聞
- **大盤指數追蹤**：支援加權指數、櫃買指數查詢

### 支援範圍
- 🏢 台灣上市、上櫃股票  
- 📈 台灣加權指數、櫃買指數 (^TWOII)

## 📋 系統需求

- Python 3.8 或以上版本
- LINE Developers 帳號
- OpenAI API 金鑰

## 📦 相依套件

```
openai                # OpenAI GPT API
openai-agents         # OpenAI Agents 框架
line-bot-sdk          # LINE Bot SDK
yfinance              # Yahoo Finance
beautifulsoup4        # 網頁爬蟲
lxml                  # XML 解析器
cloudscraper          # 雲端防護爬蟲
```

## 💬 使用方式

![FinGPT](https://github.com/user-attachments/assets/16ca59b9-68ba-4f75-9bc6-1936351accbc)

### 基本操作
1. 📱 掃描上方 QR Code 並加入好友
2. 💬 輸入您想詢問的股票問題
3. 📤 按下傳送
4. ⏳ 等待分析（約1分鐘，請耐心等候）
5. 📊 查看詳細的股市分析結果！

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
├── code/
│   ├── main.py           # 主程式 - LINE Bot 處理
│   ├── funcTool.py       # 工具函數 - 股價、新聞爬取
│   └── requirements.txt  # 套件需求
└── README.md             # 專案說明
```

### 主要模組說明

#### `main.py`
- LINE Bot 訊息處理
- OpenAI Agent 整合
- 錯誤處理機制

#### `funcTool.py`
- `get_current_time()`: 取得當前時間
- `fetch_stockID()`: 股票名稱轉代號
- `get_stock_price()`: 股價資料爬取
- `fetch_stock_news()`: 新聞資料爬取
- `fetch_twii_news()`: 大盤新聞爬取

## 🔔 使用提醒

- 📈 選單列可查看指數行情
- 🏢 目前僅提供台股「上市、上櫃」查詢
- ⏰ 分析時間預設為一個月，可指定其他期間
- 🔄 若查無資料，系統會自動嘗試查詢股票代號

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
  <b>⭐ 如果這個專案對您有幫助，請給我們一個星星！</b><br>
  Made with ❤️ for Taiwan Stock Market
</p>
