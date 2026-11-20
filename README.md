# N-System Mini-CRM

Лёгкая CRM-система для приёма и обработки заявок сервисного центра с уведомлениями и сменой статусов через Telegram-бота.

## Стек
- Python 3.11, FastAPI, Uvicorn, SQLite, httpx, python-dotenv
- Vanilla HTML/CSS/JS (лендинг и админ-панель /admin с Basic Auth, фильтрами и счётчиками)
- systemd + Nginx (reverse proxy)

## Файлы
- main.py — API, работа с SQLite и фоновый long-polling Telegram-бота
- templates/index.html — лендинг с формой заявки
- templates/admin.html — админ-панель со списком заявок и сменой статусов
- requirements.txt — зависимости Python
- .env.example — шаблон переменных окружения
- .gitignore — исключения для Git

## Запуск
1. python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
2. cp .env.example .env && chmod 600 .env (заполнить BOT_TOKEN, CHAT_ID, ADMIN_USER, ADMIN_PASS)
3. uvicorn main:app --host 127.0.0.1 --port 8085
