# N-System Mini-CRM

Лёгкая CRM-система для приёма и обработки заявок сервисного центра с уведомлениями и сменой статусов через Telegram-бота.

## Интерфейс и работа сервиса

### Веб-интерфейс (FastAPI + форма заявки)
<img width="907" height="569" alt="image" src="https://github.com/user-attachments/assets/8362b761-202d-43a6-88c4-f037e543cdf9" />
<img width="1061" height="431" alt="image" src="https://github.com/user-attachments/assets/3438b85f-8b5b-4b68-b5cc-952d21555f76" />

### Уведомления в Telegram и CI/CD-деплой
<img width="1230" height="943" alt="image" src="https://github.com/user-attachments/assets/018c42f1-76ff-4e1a-b398-c4a89ccecac8" />

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
