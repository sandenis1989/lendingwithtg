# N-System Mini-CRM

Лёгкая CRM-система для приёма и обработки заявок сервисного центра с уведомлениями и сменой статусов через Telegram-бота.

## Стек

- Python 3.11, FastAPI, Uvicorn, SQLite, httpx, python-dotenv
- Vanilla HTML/CSS/JS (лендинг и админ-панель `/admin` с Basic Auth, фильтрами и счётчиками)
- Docker, Docker Compose, Nginx (reverse proxy)
- GitHub Actions (CI/CD: проверка синтаксиса, тестовая сборка образа и автодеплой по SSH)

## Файлы

- `main.py` — API, работа с SQLite и фоновый long-polling Telegram-бота
- `templates/index.html` — лендинг с формой заявки
- `templates/admin.html` — админ-панель со списком заявок и сменой статусов
- `Dockerfile` и `docker-compose.yml` — контейнеризация сервиса с пробросом порта `127.0.0.1:8085:8000` и volume `./data` для SQLite
- `.github/workflows/deploy.yml` — CI/CD пайплайн проверки и деплоя на VPS
- `requirements.txt` — зависимости Python
- `.env.example` — шаблон переменных окружения
- `.gitignore` / `.dockerignore` — исключения для Git и Docker

## Запуск в Docker

1. `cp .env.example .env && chmod 600 .env` (заполнить `BOT_TOKEN`, `CHAT_ID`, `ADMIN_USER`, `ADMIN_PASS`)
2. `docker-compose up -d --build`
3. Приложение доступно локально на `127.0.0.1:8085` (проксируется наружу через Nginx). При пуше в `main` обновление выкатывается автоматически через GitHub Actions.
