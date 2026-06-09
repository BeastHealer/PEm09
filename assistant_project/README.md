# Мультимодальный личный ассистент по обучению промпт-инжинирингу

Production-ready проект для курсовой работы: Telegram-бот и Web UI с единой бизнес-логикой (RAG, текст, голос, изображения).

## Стек

| Компонент | Технология |
|-----------|------------|
| Telegram | python-telegram-bot v20+ (asyncio) |
| Web UI | FastAPI + Jinja2 + TailwindCSS |
| RAG | LangChain + ChromaDB + OpenAI Embeddings |
| LLM / STT / TTS / Vision | OpenAI API (gpt-4o-mini, whisper-1, tts-1, gpt-4o) |
| Контекст | SQLite (aiosqlite) |

## Структура

```
assistant_project/
├── data/                  # FAQ.pdf, cource.txt, RTFM.docx (в ../data)
├── db/                    # context.db, metadata.json, chroma/
├── handlers/              # text, rag, voice, image
├── services/              # router, rag_service, context_store
├── utils/                 # config, logger
├── web/                   # FastAPI + templates
├── bot.py                 # Telegram entry point
├── main.py                # Web entry point
├── requirements.txt
└── .env.example
```

## Быстрый старт

### 1. Установка

```bash
cd assistant_project
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

> **Windows:** если `chromadb` не устанавливается из-за `chroma-hnswlib`, выполните сначала:
> `pip install chromadb==1.5.9 --only-binary=:all:`
> затем `pip install -r requirements.txt`

### 2. Конфигурация

```bash
copy .env.example .env
```

Заполните в `.env`:

- `OPENAI_API_KEY` — ключ OpenAI
- `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)

По умолчанию `DATA_DIR` указывает на `../data` (FAQ.pdf, cource.txt, RTFM.docx).

### 3. Индексация базы знаний

Запустите бота или Web UI и выполните команду `/index`, либо через Web-кнопку **/index**.

### 4. Запуск

**Telegram-бот:**

```bash
python bot.py
# или
python -m bot
```

**Web UI:**

```bash
uvicorn web.app:app --reload
# или
python main.py
```

Откройте http://localhost:8000

## Команды

| Команда | Описание |
|---------|----------|
| `/mode text` | Обычный диалог с GPT |
| `/mode rag` | Ответы на основе Chroma RAG |
| `/mode voice` | Голосовые сообщения (Whisper + TTS) |
| `/mode image` | Анализ изображений (Vision) |
| `/reset` | Очистка истории диалога |
| `/index` | Переиндексация файлов из data/ |
| `/stats` | Статистика RAG и SQLite |
| `/help` | Справка |

## RAG Pipeline

1. Загрузка PDF, TXT, DOCX из `data/`
2. Чанкинг: 400 токенов (300–500), overlap 15%
3. Эмбеддинг: `text-embedding-3-small`
4. Хранение: ChromaDB, коллекция `prompt_knowledge`
5. Метаданные индексации: `db/metadata.json`

## Контекст диалога

- SQLite таблица `messages`: user_id, role, content, timestamp, truncated_to_8k
- Автообрезка при превышении 8000 токенов или 30 сообщений
- История передаётся в системный промпт каждого запроса

## API (Web)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | UI |
| `/api/chat` | POST | Текстовый чат |
| `/api/voice` | POST | Голосовой ввод |
| `/api/image` | POST | Анализ изображения |
| `/api/command` | POST | Команды (/index, /stats, …) |
| `/health` | GET | Health check |

## Переменные окружения

См. `.env.example` — все параметры документированы.

## Лицензия

Учебный проект для курсовой работы.
