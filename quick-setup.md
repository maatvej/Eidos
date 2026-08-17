Инструкция по первичному развертыванию и локальному запуску проекта **Eidos**.

---

### 1. Системные требования и зависимости

1. **Python 3.11+** (проверьте версию командой `python --version` или `python3.11 --version`).
2. **uv** (современный быстрый менеджер пакетов и сборщик Python):
   - **Windows** (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` или `winget install astral-sh.uv`
   - **Linux / macOS**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Pip / универсально**: `pip install uv`
3. **Node.js (18+) и npm** (необходимы для установки зависимостей, сборки и разработки React 19 + TypeScript SPA в директории [`frontend/`](frontend/package.json)):
   - **Windows**: `winget install OpenJS.NodeJS` или скачайте с [nodejs.org](https://nodejs.org)
   - **Ubuntu / Debian**: `sudo apt update && sudo apt install -y nodejs npm`
   - **macOS**: `brew install node`
4. **FFmpeg** (рекомендуется для нормализации и обработки аудиопотоков):
   - **Windows** (winget / choco): `winget install Gyan.FFmpeg` или `choco install ffmpeg`
   - **Ubuntu / Debian**: `sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1`
   - **macOS**: `brew install ffmpeg`
5. **Git** с настроенным доступом к репозиторию.

---

### 2. Автоматическая полная пересборка проекта одной командой (Zero-Touch Rebuild)

Если вы хотите выполнить чистую пересборку «с нуля» (очистка всех кэшей, сброс SQLite БД, установка uv/npm зависимостей, компиляция React SPA, накат миграций и создание суперпользователя `admin`/`admin`):

- **macOS / Linux**:
  ```bash
  chmod +x rebuild.sh
  ./rebuild.sh
  ```
- **Windows / Кроссплатформенно**:
  ```bash
  uv run python rebuild.py
  ```

---

### 3. Ручное клонирование репозитория и установка зависимостей

Выполните в терминале:

```bash
# Клонирование репозитория и переход в директорию проекта
git clone https://github.com/maatvej/Eidos.git
cd Eidos

# 1. Создание виртуального окружения и установка бэкенд-зависимостей через uv
uv sync

# 2. Установка зависимостей фронтенда React SPA
npm --prefix frontend install
```

При необходимости активировать изолированное виртуальное окружение Python вручную:
```bash
# Linux / macOS:
source .venv/bin/activate

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```

---

### 3. Сборка проекта (Build)

Для работы веб-интерфейса через объединенный сервер FastAPI скомпилируйте продакшн-бандл React SPA:

```bash
# Сборка React 19 + TypeScript фронтенда в frontend/dist/
npm --prefix frontend run build

# Сборка дистрибутива Python пакета (wheel и sdist) через uv (опционально)
uv build
```

---

### 4. Конфигурация переменных окружения (`.env`)

Создайте файл `.env` в корневой директории проекта (если требуются кастомные ключи и настройки). В режиме локальной разработки класс конфигурации [`app.core.config.Settings`](app/core/config.py) и настройки Django в [`app/core/django_settings.py`](app/core/django_settings.py) используют безопасные значения по умолчанию:

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

### 5. Режимы локального запуска

Платформа поддерживает два удобных сценария локальной разработки:

#### Вариант A. Единый полнофункциональный сервер (Production-like)
FastAPI автоматически раздает скомпилированный бандл React SPA из `frontend/dist/` (через [`app.main.get_spa_index_path()`](app/main.py)) и обслуживает все REST API, SSE, Django Allauth и Django Admin на порту `8000`:

```bash
# 1. Собрать фронтенд (если еще не собран)
npm --prefix frontend run build

# 2. Запустить единый ASGI-сервер через run_local.py
uv run python run_local.py
```

Скрипт [`run_local.main()`](run_local.py) автоматически:
- Проверяет наличие FFmpeg через [`run_local.check_ffmpeg()`](run_local.py).
- Создает локальное хранилище файлов [`local_storage/`](local_storage/.gitkeep).
- Собирает статические файлы Django Admin в [`django_static/`](django_static/admin/img/README.md).
- Применяет миграции базы данных SQLite (`dev_app.db`).
- Запускает единый ASGI-сервер [`app.asgi.UnifiedASGIApplication`](app/asgi.py) через Uvicorn на порту `8000`.

> Сервер доступен по адресу: **[http://localhost:8000/](http://localhost:8000/)**

#### Вариант B. Разработка фронтенда с Hot Module Replacement (HMR)
Для мгновенного применения изменений в компонентах React / Tailwind без перезапуска бэкенда запустите серверы в двух параллельных терминалах:

- **Терминал 1 (Бэкенд FastAPI + Django):**
  ```bash
  uv run python run_local.py
  ```
- **Терминал 2 (Vite Dev Server с HMR):**
  ```bash
  npm --prefix frontend run dev
  ```

> Откройте в браузере **[http://localhost:5173/](http://localhost:5173/)**. Vite dev-сервер в [`frontend/vite.config.ts`](frontend/vite.config.ts) автоматически настроен на проксирование запросов `/api`, `/accounts`, `/admin`, `/static` и `/media` на бэкенд-порт `8000`.

---

### 6. Создание суперпользователя (Администратор Django)

В терминале выполните команду через [`manage.py.main()`](manage.py):

```bash
uv run python manage.py createsuperuser
```

---

### 7. Доступные эндпоинты и веб-интерфейсы

- **Основной Web UI (React 19 SPA)**: [http://localhost:8000/](http://localhost:8000/) (или `http://localhost:5173/` при HMR)
  - Студия транскрипции и аналитики: `http://localhost:8000/studio`
  - Детальный просмотр задачи: `http://localhost:8000/job/<job_id>`
  - Личный кабинет и история: `http://localhost:8000/account` (профиль `/account/profile`, безопасность `/account/security`, история `/account/history`)
- **Интерактивная документация Swagger (FastAPI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Альтернативная документация ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Панель управления Django Admin**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
- **Авторизация / Регистрация Django Allauth**: [http://localhost:8000/accounts/login/](http://localhost:8000/accounts/login/)

---

### 8. Проверка качества кода и запуск тестов

```bash
# Запуск полного набора unit- и integration-тестов с анализом покрытия
uv run pytest

# Статическая проверка типов Python (Strict MyPy)
uv run mypy app

# Проверка линтером и форматирование кода Python
uv run ruff check app tests

# Проверка типов TypeScript и сборка React фронтенда
npm --prefix frontend run build
```
