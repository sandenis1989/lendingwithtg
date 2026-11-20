import asyncio
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "crm.db"))
TEMPLATES_DIR = BASE_DIR / "templates"

STATUS_LABELS = {
    "new": "🆕 Новая",
    "in_progress": "⚙️ В работе",
    "closed": "✅ Закрыта",
}

security = HTTPBasic()


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                device TEXT NOT NULL,
                problem TEXT,
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL,
                tg_chat_id TEXT,
                tg_message_id INTEGER
            )
        """)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
        if "tg_chat_id" not in cols:
            conn.execute("ALTER TABLE leads ADD COLUMN tg_chat_id TEXT")
        if "tg_message_id" not in cols:
            conn.execute("ALTER TABLE leads ADD COLUMN tg_message_id INTEGER")
        conn.commit()


def get_lead(lead_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None


def save_tg_message_meta(lead_id: int, tg_chat_id: str, tg_message_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE leads SET tg_chat_id = ?, tg_message_id = ? WHERE id = ?",
            (str(tg_chat_id), tg_message_id, lead_id),
        )
        conn.commit()


def update_lead_status(lead_id: int, new_status: str) -> bool:
    if new_status not in STATUS_LABELS:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
        conn.commit()
        return cur.rowcount > 0


def format_lead_message(lead: dict) -> str:
    status_text = STATUS_LABELS.get(lead["status"], lead["status"])
    return (
        f"🛠 <b>Заявка #{lead['id']}</b> — <b>{status_text}</b>\n\n"
        f"👤 <b>Клиент:</b> {lead['client_name']}\n"
        f"📞 <b>Телефон:</b> {lead['phone']}\n"
        f"💻 <b>Устройство:</b> {lead['device']}\n"
        f"📝 <b>Проблема:</b> {lead['problem']}\n"
        f"🕒 <b>Создана:</b> {lead['created_at']}"
    )


def build_keyboard(lead_id: int, current_status: str) -> dict:
    buttons = []
    if current_status != "in_progress":
        buttons.append({"text": "⚙️ Взять в работу", "callback_data": f"status:{lead_id}:in_progress"})
    if current_status != "closed":
        buttons.append({"text": "✅ Закрыть", "callback_data": f"status:{lead_id}:closed"})
    return {"inline_keyboard": [buttons]} if buttons else {"inline_keyboard": []}


async def send_telegram_alert(lead: dict):
    if not BOT_TOKEN or not CHAT_ID or CHAT_ID == "000000000":
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": format_lead_message(lead),
        "parse_mode": "HTML",
        "reply_markup": build_keyboard(lead["id"], lead["status"]),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("result") or {}
        msg_id = msg.get("message_id")
        chat_id = (msg.get("chat") or {}).get("id")
        if msg_id and chat_id:
            save_tg_message_meta(lead["id"], chat_id, msg_id)


async def sync_telegram_message(lead: dict):
    if not BOT_TOKEN or not lead.get("tg_chat_id") or not lead.get("tg_message_id"):
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": lead["tg_chat_id"],
        "message_id": lead["tg_message_id"],
        "text": format_lead_message(lead),
        "parse_mode": "HTML",
        "reply_markup": build_keyboard(lead["id"], lead["status"]),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        except Exception:
            pass


async def poll_telegram_updates(stop_event: asyncio.Event):
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        return
    offset = 0
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    async with httpx.AsyncClient(timeout=35.0) as client:
        while not stop_event.is_set():
            try:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 25},
                )
                resp.raise_for_status()
                data = resp.json()
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    cq = upd.get("callback_query")
                    if not cq:
                        continue

                    data_str = cq.get("data", "")
                    cq_id = cq["id"]
                    msg = cq.get("message") or {}
                    chat_id = msg.get("chat", {}).get("id")
                    message_id = msg.get("message_id")

                    if data_str.startswith("status:"):
                        _, lead_str, new_status = data_str.split(":", 2)
                        lead_id = int(lead_str)
                        if new_status in STATUS_LABELS and update_lead_status(lead_id, new_status):
                            if chat_id and message_id:
                                save_tg_message_meta(lead_id, chat_id, message_id)
                            lead = get_lead(lead_id)
                            if lead and chat_id and message_id:
                                await client.post(
                                    f"{base_url}/editMessageText",
                                    json={
                                        "chat_id": chat_id,
                                        "message_id": message_id,
                                        "text": format_lead_message(lead),
                                        "parse_mode": "HTML",
                                        "reply_markup": build_keyboard(lead_id, new_status),
                                    },
                                )
                            await client.post(
                                f"{base_url}/answerCallbackQuery",
                                json={
                                    "callback_query_id": cq_id,
                                    "text": f"Статус: {STATUS_LABELS[new_status]}",
                                },
                            )
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop_event = asyncio.Event()
    poller_task = asyncio.create_task(poll_telegram_updates(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="N-System Mini-CRM", lifespan=lifespan)


class LeadIn(BaseModel):
    client_name: str
    phone: str
    device: str
    problem: str = "Не указана"


class StatusUpdateIn(BaseModel):
    status: str


@app.post("/api/leads")
async def create_lead(lead: LeadIn):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO leads (client_name, phone, device, problem, created_at) VALUES (?, ?, ?, ?, ?)",
            (lead.client_name, lead.phone, lead.device, lead.problem, now),
        )
        lead_id = cursor.lastrowid
        conn.commit()

    created = get_lead(lead_id)
    try:
        await send_telegram_alert(created)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Заявка сохранена (#{lead_id}), но ошибка Telegram: {e}")

    return {"status": "ok", "lead_id": lead_id}


@app.get("/api/leads", dependencies=[Depends(verify_admin)])
def list_leads():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


@app.patch("/api/leads/{lead_id}/status", dependencies=[Depends(verify_admin)])
async def set_lead_status(lead_id: int, payload: StatusUpdateIn):
    if not update_lead_status(lead_id, payload.status):
        raise HTTPException(status_code=404, detail="Заявка не найдена или неверный статус")
    lead = get_lead(lead_id)
    if lead:
        await sync_telegram_message(lead)
    return {"status": "ok", "lead_id": lead_id, "new_status": payload.status}


@app.get("/")
def landing():
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/admin", dependencies=[Depends(verify_admin)])
def admin_page():
    return FileResponse(TEMPLATES_DIR / "admin.html")
