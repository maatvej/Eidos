Инструкция по первичному развертыванию и локальному запуску проекта **Eidos**.

---

### 1. Системные требования и зависимости

1. **Python 3.11+** (проверьте версию командой `python --version` или `python3.11 --version`).
2. **uv** (современный быстрый менеджер пакетов и сборщик Python):
   - **Windows** (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` или `winget install astral-sh.uv`
   - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Pip / универсально**: `pip install uv`
3. **FFmpeg** (рекомендуется для нормализации и обработки аудиопотоков):
   - **Windows** (winget / choco): `winget install Gyan.FFmpeg` или `choco install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1`
   - **macOS**: `brew install ffmpeg`
4. **Git** с настроенным доступом к репозиторию.

---

### 2. Клонирование и настройка виртуального окружения через `uv`

Выполните в терминале:

```bash
# Клонирование репозитория и переход в директорию проекта
git clone https://github.com/maatvej/Eidos.git
cd Eidos

# Создание виртуального окружения и синхронизация всех зависимостей проекта по uv.lock
uv sync
```

При необходимости активировать изолированное окружение вручную:
```bash
# Linux / macOS:
source .venv/bin/activate

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```

---

### 3. Сборка проекта (Build)

Сборка дистрибутива пакета (`wheel` и `sdist`) через `uv`:

```bash
uv build
```

---

### 4. Конфигурация переменных окружения (`.env`)

Создайте файл `.env` в корневой директории проекта (если требуются кастомные ключи и настройки). В режиме локальной разработки класс конфигурации [`app.core.config.Settings`](app/core/config.py:9) и настройки Django в [`app/core/django_settings.py`](app/core/django_settings.py:1) используют безопасные значения по умолчанию:

```env
# Режим разработки и базы данных
DEV_MODE=True
USE_REDIS=False
DATABASE_URL=sqlite+aiosqlite:///./dev_app.db

# Настройки Django
DJANGO_SECRET_KEY=django-insecure-eidos-local-development-key
DJANGO_DEBUG=True

# Настройки моделей ML (Whisper / PyAnnote / LLM)
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
PYANNOTE_AUTH_TOKEN=hf_dummy_token
LLM_API_KEY=mock-key
LLM_MODEL_NAME=gpt-4o
```

---

### 5. Запуск локального сервера (FastAPI + Django)

Для быстрого запуска без внешних сервисов (Docker, Redis, PostgreSQL) предусмотрен скрипт [`run_local.py`](run_local.py:1). Функция [`run_local.main()`](run_local.py:34) автоматически:
- Проверяет наличие утилиты через [`run_local.check_ffmpeg()`](run_local.py:21).
- Создает локальное хранилище файлов [`local_storage/`](local_storage/.gitkeep:1).
- Собирает статические файлы Django Admin в [`django_static/`](django_static/admin/img/README.md:1).
- Применяет миграции базы данных SQLite (`dev_app.db`).
- Запускает единый ASGI-сервер [`app.asgi.UnifiedASGIApplication`](app/asgi.py:26) через Uvicorn на порту `8000`.

```bash
uv run python run_local.py
```

---

### 6. Создание суперпользователя (Администратор Django)

В терминале выполните команду через [`manage.py.main()`](manage.py:8):

```bash
uv run python manage.py createsuperuser
```

---

### 7. Доступные эндпоинты и веб-интерфейсы

- **Основной Web UI**: [http://localhost:8000/](http://localhost:8000/)
- **Интерактивная документация Swagger (FastAPI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Альтернативная документация ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Панель управления Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **Авторизация / Регистрация Django Allauth**: [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/)

---

### 8. Проверка качества кода и запуск тестов

```bash
# Запуск полного набора unit- и integration-тестов с анализом покрытия
uv run pytest

# Статическая проверка типов (Strict MyPy)
uv run mypy app

# Проверка линтером и форматирование кода
uv run ruff check app tests
```
