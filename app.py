
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import asyncio
import secrets

from services.line_api import router as linebot_router
from services.morning.pipeline import run_morning_pipeline
from services.morning.scheduler import start_scheduler, stop_scheduler
from services.morning.subscribers import morning_alert_user_ids
from util.config import Env

# 初始化 HTTPBasic 認證
security = HTTPBasic()

# 從環境變數讀取 /docs 帳密
DOCS_USERNAME = Env.DOCS_USERNAME
DOCS_PASSWORD = Env.DOCS_PASSWORD
_morning_push_lock = asyncio.Lock()

# 驗證函數
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    credentials_configured = bool(DOCS_USERNAME and DOCS_PASSWORD)
    correct_username = secrets.compare_digest(credentials.username, DOCS_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    if not (credentials_configured and correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="無效的憑證",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

@asynccontextmanager
async def lifespan(application: FastAPI):
    """管理應用程式啟動與關閉期間的排程器生命週期。"""
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="FinGPT API",
    docs_url=None,  # 停用預設的 docs
    redoc_url=None,  # 停用預設的 redoc
    openapi_url=None,  # 停用預設的 openapi.json
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 引入 lineAPI 路由
app.include_router(linebot_router)

# 受保護的 OpenAPI schema
@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_openapi(title="FinGPT API", version="1.0.0", routes=app.routes)

# 受保護的 Swagger UI
@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="FinGPT API")

# 受保護的 ReDoc
@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_redoc_html(openapi_url="/openapi.json", title="FinGPT API")

# 根路由
@app.get("/")
def root():
    return {"message": "Welcome to FinGPT API!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/morning/push", tags=["Morning"])
async def push_morning_report(
    force: bool = True,
    credentials: HTTPBasicCredentials = Depends(verify_credentials),
):
    """手動執行完整早盤流程，完成後 multicast 給訂閱白名單。"""
    if not Env.MORNING_PUSH_ENABLED:
        raise HTTPException(status_code=503, detail="MORNING_PUSH_ENABLED 尚未啟用")
    recipients = morning_alert_user_ids()
    if not recipients:
        raise HTTPException(status_code=409, detail="早盤推播白名單目前為空")
    if _morning_push_lock.locked():
        raise HTTPException(status_code=409, detail="已有一個手動早盤推播正在執行")

    async with _morning_push_lock:
        report = await run_morning_pipeline(push=True, force=force)
    if report is None:
        return {
            "status": "skipped",
            "message": "未執行推播；可能是非交易日、今日已推播或資料來源無法產生報告",
        }
    return {
        "status": "completed",
        "report_date": report.report_date,
        "recipients": len(recipients),
        "force": force,
    }

# FastAPI 初始化
if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=Env.PORT, reload=Env.RELOAD)
    # uvicorn app:app --port 7860 --reload
    # ngrok http 7860