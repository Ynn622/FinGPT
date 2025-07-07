# FinGPT 📈

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python版本">
  <img src="https://img.shields.io/badge/LineBot-SDK-brightgreen.svg" alt="LINE Bot">
  <img src="https://img.shields.io/badge/OpenAI-GPT--4.1-orange.svg" alt="OpenAI">
</p>

<p align="center">
  <strong>🚀 智慧台股分析助手 | 結合 AI 的投資決策工具</strong>
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

- Python 3.8 或以上版本
- LINE Developers 帳號
- OpenAI API 金鑰

## 📦 相依套件

| 套件名稱 | 版本 | 用途說明 |
|---------|------|----------|
| `openai` | latest | OpenAI GPT API 介接 |
| `openai-agents` | latest | OpenAI Agents 框架 |
| `line-bot-sdk` | latest | LINE Bot SDK |
| `yfinance` | latest | Yahoo Finance 資料源 |
| `beautifulsoup4` | latest | 網頁爬蟲解析 |
| `lxml` | latest | XML 解析器 |
| `cloudscraper` | latest | 雲端防護爬蟲 |
| `pandas` | latest | 資料處理 |
| `requests` | latest | HTTP 請求 |

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
├── code/
│   ├── main.py           # 主程式 - LINE Bot 處理與 AI 整合
│   ├── funcTool.py       # 工具函數 - 資料抓取與處理
│   ├── TA.py             # 技術指標函數
│   └── requirements.txt  # 套件需求清單
└── README.md             # 專案說明文件
```

### 🔍 主要模組說明

#### 📄 `main.py` - 核心處理模組
- **LINE Bot 訊息處理**：接收並解析用戶訊息
- **OpenAI Agent 整合**：調用 AI 進行股票分析
- **錯誤處理機制**：完善的異常處理與用戶反饋
- **回應機制**：格式化分析結果並回傳用戶

#### 🔧 `funcTool.py` - 資料工具模組
- **`get_current_time()`**：取得當前時間資訊
- **`fetch_stockID()`**：股票名稱轉換為代號
- **`get_stock_price()`**：抓取股價與籌碼資料
- **`get_live_price()`**：即時股價資料更新
- **`get_chip_data()`**：三大法人買賣超資料
- **`fetch_stock_news()`**：個股新聞資料抓取
- **`fetch_twii_news()`**：大盤新聞資料抓取

### 🔄 資料流程圖
```
用戶輸入 → LINE Bot → AI Agent → 資料抓取 → 分析處理 → 回應用戶
    ↓           ↓         ↓         ↓          ↓         ↓
  自然語言    訊息解析   智慧分析   多源資料    AI整合    格式化回應
```

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
