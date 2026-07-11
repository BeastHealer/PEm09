# ProxyAPI Setup

Проект использует [ProxyAPI](https://proxyapi.ru/docs/overview) для всех AI-запросов.

## Зачем ProxyAPI

- Доступ к OpenAI API из России без VPN
- Оплата в рублях через личный кабинет
- Единый ключ для GPT, Whisper, TTS, Vision, DALL-E и Embeddings

## Настройка

1. Зарегистрируйтесь на [proxyapi.ru](https://proxyapi.ru)
2. Создайте ключ в разделе **Ключи API**
3. Добавьте в `.env`:

```env
PROXYAPI_KEY=ваш_ключ
```

4. Запустите приложение: `python main.py`

## Технические детали

| Параметр | Значение |
|----------|----------|
| Базовый URL | `https://api.proxyapi.ru` |
| OpenAI API | `https://api.proxyapi.ru/openai/v1` |
| Авторизация | `Authorization: Bearer <PROXYAPI_KEY>` |

Все сервисы проекта настроены на этот endpoint:

- `services/openai_client.py` — GPT, Whisper, TTS, Vision, DALL-E
- `rag/index.py` — Embeddings для ChromaDB

## Документация ProxyAPI

- [Начало работы](https://proxyapi.ru/docs/overview)
- [OpenAI-совместимый API](https://proxyapi.ru/docs/openai-compatible-api)

## Устранение проблем

| Ошибка | Решение |
|--------|---------|
| `PROXYAPI_KEY is not set` | Добавьте ключ в `.env` |
| 401 Unauthorized | Проверьте ключ, создайте новый в кабинете |
| 402 / billing | Пополните баланс на proxyapi.ru |
| 429 Rate limit | Подождите или проверьте лимиты в кабинете |
