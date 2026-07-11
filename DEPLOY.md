# Деплой на сервер

Инструкция для публикации ассистента на VPS или российском хостинге (Timeweb, Selectel, REG.RU, Beget и др.).

---

## 1. Подготовка сервера

**Минимальные требования:**
- Ubuntu 22.04+ / Debian 12+
- 1 GB RAM (рекомендуется 2 GB для ChromaDB)
- Python 3.12

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv git nginx
```

---

## 2. Клонирование и настройка

```bash
git clone https://github.com/YOUR_USERNAME/prompt-engineering-assistant.git
cd prompt-engineering-assistant

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env
```

**Обязательно в `.env` для production:**

```env
PROXYAPI_KEY=ваш_ключ
SECRET_KEY=<сгенерируйте: python -c "import secrets; print(secrets.token_hex(32))">
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
TELEGRAM_ENABLED=false
LOG_LEVEL=INFO
```

> Для production рекомендуется `TELEGRAM_ENABLED=false` на веб-сервере. Telegram-бот можно запустить отдельно.

---

## 3. Запуск через Gunicorn

```bash
source venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:5000 --timeout 120 wsgi:app
```

Проверка: `curl http://127.0.0.1:5000/api/health`

---

## 4. Systemd (автозапуск)

```bash
sudo nano /etc/systemd/system/pe-assistant.service
```

```ini
[Unit]
Description=Prompt Engineering Assistant
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/prompt-engineering-assistant
Environment=PATH=/var/www/prompt-engineering-assistant/venv/bin
ExecStart=/var/www/prompt-engineering-assistant/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 --timeout 120 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pe-assistant
sudo systemctl start pe-assistant
```

---

## 5. Nginx (reverse proxy + HTTPS)

```bash
sudo nano /etc/nginx/sites-available/pe-assistant
```

```nginx
server {
    listen 80;
    server_name your-domain.ru;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        client_max_body_size 20M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/pe-assistant /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

SSL через Certbot:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.ru
```

---

## 6. Docker

```bash
cp .env.example .env
# заполните .env

docker compose up -d --build
docker compose logs -f
```

Проверка: `curl http://localhost:5000/api/health`

---

## 7. Данные и персистентность

| Путь | Назначение |
|------|------------|
| `data/documents/` | База знаний (PDF, TXT, DOCX) |
| `data/chroma_db/` | Векторный индекс (создаётся автоматически) |
| `data/uploads/` | Временные файлы (голос, изображения) |

При Docker эти папки монтируются как volumes (см. `docker-compose.yml`).

---

## 8. Публикация на GitHub

```bash
git init
git add .
git status   # убедитесь, что .env НЕ в списке
git commit -m "Initial commit: Prompt Engineering Assistant"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/prompt-engineering-assistant.git
git push -u origin main
```

**Перед push проверьте:**
- `.env` в `.gitignore`
- Нет API-ключей в коде
- `README.md` обновлён (ссылки, имя автора)

---

## 9. Чеклист перед публикацией в портфолио

- [ ] Приложение задеплоено и доступно по URL
- [ ] `/api/health` возвращает `{"status": "ok"}`
- [ ] RAG отвечает на вопросы по course.txt
- [ ] Голосовой ввод работает
- [ ] README содержит ссылку на live demo
- [ ] Скриншот интерфейса добавлен в README _(опционально)_
- [ ] GitHub repo публичный

---

## Устранение проблем

| Проблема | Решение |
|----------|---------|
| 502 Bad Gateway | Проверьте `systemctl status pe-assistant` |
| RAG пустой | Положите файлы в `data/documents/`, перезапустите |
| Голос не работает | Проверьте PROXYAPI_KEY и баланс |
| Telegram таймаут | `TELEGRAM_ENABLED=false`, используйте только веб |
