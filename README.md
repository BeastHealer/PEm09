# Prompt Engineering Assistant

> Мультимодальный AI-ассистент для студентов курса по промпт-инжинирингу: RAG, голос, Vision, веб + Telegram.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green)](https://flask.palletsprojects.com/)
[![ProxyAPI](https://img.shields.io/badge/API-ProxyAPI-orange)](https://proxyapi.ru)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## О проекте

Личный гибридный помощник для обучения промпт-инжинирингу. Помогает студентам с домашними заданиями, используя персональную базу знаний и мультимодальные возможности.

**Два интерфейса:**
- Веб-приложение (Flask) — основной, современный UI
- Telegram-бот — дублирующий интерфейс

**Целевая аудитория:** студенты курса по промпт-инжинирингу.

---

## Возможности

| Функция | Описание |
|---------|----------|
| **RAG** | Ответы из базы знаний (FAQ.pdf, course.txt, RTFM.docx) |
| **Голос** | Whisper STT + TTS, голосовой ввод с сайта |
| **Vision** | Анализ скриншотов (ошибки Cursor, код, интерфейсы) |
| **Контекст** | История диалога для каждого пользователя |
| **Загрузка документов** | Добавление файлов в базу знаний через веб |

---

## Стек технологий

- **Backend:** Python 3.12, Flask, asyncio
- **AI:** GPT-4o, Whisper, TTS, Vision через [ProxyAPI](https://proxyapi.ru)
- **RAG:** LangChain, ChromaDB, OpenAI Embeddings
- **Frontend:** HTML, CSS, JavaScript (vanilla)
- **Bot:** pyTelegramBotAPI (опционально)
- **Deploy:** Docker, Gunicorn, GitHub Actions

---

## Быстрый старт

```bash
git clone https://github.com/YOUR_USERNAME/prompt-engineering-assistant.git
cd prompt-engineering-assistant

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
cp .env.example .env
# Заполните PROXYAPI_KEY в .env

python main.py
```

Откройте: **http://127.0.0.1:5000**

Подробнее: [START_HERE.md](START_HERE.md) | [DEPLOY.md](DEPLOY.md)

---

## Структура проекта

```
├── main.py              # Точка входа (dev)
├── wsgi.py              # Точка входа (production)
├── bot.py               # Flask-приложение
├── telegram_bot.py      # Telegram (опционально)
├── handlers/            # Web + Telegram routes
├── services/            # OpenAI, роутер, STT, TTS, Vision
├── rag/                 # Загрузка, индекс, запросы
├── utils/               # Логи, сессии, промпты
├── templates/           # HTML
├── static/              # CSS, JS
├── data/documents/      # База знаний
├── tests/               # pytest
├── Dockerfile
└── docker-compose.yml
```

---

## Конфигурация (.env)

```env
PROXYAPI_KEY=ваш_ключ
SECRET_KEY=случайная_строка_32_символа
TELEGRAM_BOT_TOKEN=          # опционально
TELEGRAM_ENABLED=true        # false — только веб
FLASK_DEBUG=false            # true — только для разработки
BOT_MODE=rag
```

Сгенерировать SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Деплой

### Docker (рекомендуется)

```bash
cp .env.example .env
# заполните .env
docker compose up -d --build
```

### VPS / российский хостинг

```bash
pip install -r requirements.txt
gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 wsgi:app
```

Полная инструкция: **[DEPLOY.md](DEPLOY.md)**

---

## Тесты

```bash
pytest
```

CI запускается автоматически через GitHub Actions.

---

## Для портфолио

### Задача
Создать ассистента для студентов курса, который отвечает на вопросы по материалам, принимает голос и изображения, работает через веб и Telegram.

### Решение
- RAG-пайплайн с ChromaDB для поиска по учебным материалам
- Единый роутер запросов (text / voice / vision / rag)
- ProxyAPI для доступа к OpenAI из РФ без VPN
- Graceful degradation: веб работает даже если Telegram недоступен

### Что сделано
- Разработал мультимодальный AI-ассистент (RAG + Whisper + Vision)
- Интегрировал ProxyAPI, ChromaDB, LangChain
- Реализовал веб-интерфейс и Telegram-бот с общей бизнес-логикой
- Настроил Docker-деплой и CI/CD

### Демо
- Live: `https://your-domain.ru` _(добавьте ссылку после деплоя)_
- Repo: `https://github.com/BeastHealer/prompt-engineering-assistant`

---

## Лицензия

MIT — см. [LICENSE](LICENSE)

---

## Автор

Ľudmila Maklákova — [GitHub](https://github.com/BeastHealer) | [Telegram](https://t.me/@BeastMaster77)

_Проект выполнен в рамках курса «Промпт-инжиниринг»._
