from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dataclasses import dataclass, asdict
from typing import Optional, List
import psycopg2
import requests
import os, time, logging, threading
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import uvicorn
from logging.handlers import RotatingFileHandler

load_dotenv()

# =========================================================
# APP
# =========================================================
app = FastAPI(title="OSM Scheduler")

BASE_PATH = "/osmmicroservices"

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =========================================================
# LOGGING
# =========================================================
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "scheduler.log")
os.makedirs(LOG_DIR, exist_ok=True)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
stream_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[file_handler, stream_handler],
)

logger = logging.getLogger(__name__)

# =========================================================
# STATE
# =========================================================
sessions = {}
db_config = {}

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")

csharp_api_base = os.environ.get("CSHARP_API_BASE")

# =========================================================
# AUTH
# =========================================================
def get_session(request: Request):
    token = request.cookies.get("session_token")
    return sessions.get(token)

# =========================================================
# ROUTES
# =========================================================

@app.get(BASE_PATH)
@app.get(BASE_PATH + "/")
async def root(request: Request):
    if get_session(request):
        return RedirectResponse(BASE_PATH + "/dashboard")
    return RedirectResponse(BASE_PATH + "/login")


@app.get(BASE_PATH + "/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post(BASE_PATH + "/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        import secrets
        token = secrets.token_hex(32)

        sessions[token] = {"username": username}

        response = RedirectResponse(BASE_PATH + "/dashboard", status_code=302)
        response.set_cookie("session_token", token, httponly=True)
        return response

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Invalid credentials"
    })


@app.get(BASE_PATH + "/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        sessions.pop(token, None)

    response = RedirectResponse(BASE_PATH + "/login")
    response.delete_cookie("session_token")
    return response


@app.get(BASE_PATH + "/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not get_session(request):
        return RedirectResponse(BASE_PATH + "/login")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": get_session(request)["username"]
    })

# =========================================================
# DB TEST API
# =========================================================
@app.post("/api/test-db")
async def test_db(request: Request):
    global db_config

    db_config = {
        "dbname": os.environ.get("DB_NAME"),
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
        "host": os.environ.get("DB_HOST"),
        "port": os.environ.get("DB_PORT"),
    }

    try:
        conn = psycopg2.connect(**db_config)
        conn.close()
        return JSONResponse({"success": True, "message": "DB connected"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})

# =========================================================
# SIMPLE API EXAMPLE
# =========================================================
@app.get("/api/status")
async def status():
    return {
        "service": "OSM Scheduler",
        "status": "running"
    }

# =========================================================
# STARTUP
# =========================================================
@app.on_event("startup")
async def startup():
    logger.info("OSM Scheduler started")

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)