
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import os
from dotenv import load_dotenv
import secrets

from services.line_api import router as linebot_router

load_dotenv()  # 讀取 .env 檔案

# 初始化 HTTPBasic 認證
security = HTTPBasic()

# 從環境變數讀取 /docs 帳密
DOCS_USERNAME = os.getenv("DOCS_USERNAME", "")
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "")

# 驗證函數
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, DOCS_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="無效的憑證",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

app = FastAPI(
    title="FinGPT API",
    docs_url=None,  # 停用預設的 docs
    redoc_url=None,  # 停用預設的 redoc
    openapi_url=None  # 停用預設的 openapi.json
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

# FastAPI 初始化
if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get("PORT", 7860))  # Hugging Face Spaces 預設使用 7860 port
    reload_mode = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn.run("app:app", host='0.0.0.0', port=port, reload=reload_mode)
    # uvicorn app:app --port 7860 --reload
    # ngrok http 7860