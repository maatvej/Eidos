# FAQ по пересборке проекта и скриптам жизненного цикла (Rebuild & Lifecycle Guide)

Данный документ содержит полное руководство по назначению скриптов пересборки ([`rebuild.sh`](rebuild.sh) и [`rebuild.py`](rebuild.py)), матрицы сценариев их применения, а также подробный разбор архитектурных нюансов гибридного стека платформы **Eidos**.

---

## 1. Архитектурный контекст и назначение скриптов

Платформа **Eidos** построена на базе гибридной серверной архитектуры:
- **FastAPI Core ([`app/main.py:app`](app/main.py:36))**: обеспечивает высокопроизводительные REST API, SSE-потоки событий транскрибации, фоновую обработку ML-задач и раздачу скомпилированного React SPA приложения.
- **Django ORM & Admin ([`app/core/django_settings.py`](app/core/django_settings.py), [`app/db/models.py`](app/db/models.py))**: управляет схемой реляционной базы данных, миграциями, аутентификацией пользователей (Django Allauth) и административной панелью `/admin/`.
- **React 19 + TypeScript + Tailwind CSS ([`frontend/`](frontend/))**: современный Single Page Application (SPA), компилируемый сборщиком Vite в директорию `frontend/dist/`.
- **Пакетный менеджер uv ([`pyproject.toml`](pyproject.toml))**: обеспечивает сверхбыструю синхронизацию Python-зависимостей и изоляцию виртуального окружения `.venv/`.

### Сравнение доступных скриптов запуска и обслуживания

| Скрипт / Команда | Тип операции | Очищает БД? | Пересобирает фронтенд? | Обновляет зависимости? | Когда использовать? |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`./rebuild.sh`** (или `bash rebuild.sh`) | **Zero-Touch Rebuild (macOS / Linux)** | **Да** | **Да** | **Да** | Первичная настройка, переключение веток, сбои кэша, ломающие изменения БД. |
| **`uv run python rebuild.py`** | **Zero-Touch Rebuild (Cross-platform)** | **Да** | **Да** | **Да** | Кроссплатформенный запуск полной чистой пересборки проекта через Python. |
| **`uv run python run_local.py`** | **Local Development Launcher** | **Нет** | **Нет** | **Нет** | Повседневная разработка бэкенда с автоперезагрузкой сервера (Hot-reload). |
| **`cd frontend && npm run dev`** | **Vite HMR Dev Server** | **Нет** | **В памяти (HMR)** | **Нет** | Активная верстка и разработка React/Tailwind интерфейса на порту 5173. |

---

## 2. Что именно делает скрипт пересборки ([`rebuild.py:main()`](rebuild.py:307))

Скрипт пересборки [`rebuild.py`](rebuild.py) выполняет 5 последовательных изолированных шагов:

1. **Глубокая очистка (Deep Clean) ([`rebuild.py:clean_caches_and_database()`](rebuild.py:154)):**
   - Удаляет локальные базы данных SQLite ([`db.sqlite3`](app/core/django_settings.py:126), `test_db.sqlite3`).
   - Очищает директорию локальных загрузок `local_storage/` и сохраненные профили спикеров `voice_profiles/`.
   - Рекурсивно удаляет кэши байткода Python (`__pycache__`, `*.pyc`, `*.pyo`), кэши тестов и линтеров (`.pytest_cache`, `.ruff_cache`, `.mypy_cache`), а также артефакты сборки Python (`dist/`, `build/`, `*.egg-info`).
   - Удаляет скомпилированный бандл фронтенда `frontend/dist/`.
2. **Синхронизация окружения Python ([`rebuild.py:sync_python_dependencies()`](rebuild.py:169)):**
   - Выполняет `uv sync --all-extras`, гарантируя установку всех основных и `dev`-зависимостей без ручного создания `.venv`.
3. **Сборка фронтенда React SPA ([`rebuild.py:rebuild_frontend()`](rebuild.py:194)):**
   - Выполняет `npm install` для синхронизации пакетов `node_modules`.
   - Запускает `npm run build` (`tsc && vite build`), компилируя чистый оптимизированный бандл в директорию `frontend/dist/`.
4. **Инициализация Django ORM и статики ([`rebuild.py:run_database_migrations_and_static()`](rebuild.py:229)):**
   - Автоматически создает миграции `makemigrations db` и накатывает их командой `migrate`.
   - Выполняет `collectstatic --no-input` для сбора статики админки и Allauth в `django_static/`.
5. **Создание суперпользователя ([`rebuild.py:create_or_reset_superuser()`](rebuild.py:253)):**
   - Программно инициализирует суперпользователя `admin` с паролем `admin` и почтой `admin@example.com`.
   - Создает и верифицирует запись `EmailAddress` в Django Allauth для бесшовного входа через сессии и API токенов.

---

## 3. Матрица сценариев: когда и какой скрипт запускать

### Сценарий А. Вы переключились на другую Git-ветку (`git checkout` / `git pull` / `git merge`)
- **Почему это важно:** В другой ветке могли измениться зависимости в [`pyproject.toml`](pyproject.toml) или [`frontend/package.json`](frontend/package.json), добавлены новые Django-модели в [`app/db/models.py`](app/db/models.py), изменен UI, или остались невалидные скомпилированные `.pyc` файлы в `__pycache__`.
- **Что запускать:**
  ```bash
  ./rebuild.sh
  # или: uv run python rebuild.py
  ```
- **Результат:** Проект полностью сброшен, зависимости синхронизированы, база создана заново, фронтенд пересобран.

---

### Сценарий Б. Изменился фронтенд-код (`frontend/src/**/*`, `index.html`, `tailwind.config.js`)
- **Почему это важно:** Сервер FastAPI ([`app/main.py:serve_spa_app()`](app/main.py:132)) на порту 8000 отдает клиенту **статические скомпилированные файлы из директории `frontend/dist/`**. Если вы изменили React-компонент, но не пересобрали фронтенд, браузер продолжит загружать старый скомпилированный бандл!
- **Варианты действий:**
  1. **Быстрая пересборка фронтенда (без сброса базы данных):**
     ```bash
     cd frontend && npm run build && cd ..
     ```
  2. **Режим интерактивной разработки фронтенда (с Hot-Module-Replacement):**
     - В первом терминале запустить бэкенд: `uv run python run_local.py`
     - Во втором терминале запустить Vite: `cd frontend && npm run dev` (открыть http://localhost:5173).
  3. **Полная пересборка:** `./rebuild.sh`.

---

### Сценарий В. Добавлены или изменены зависимости (`pyproject.toml` или `frontend/package.json`)
- **Почему это важно:** Без установки новых пакетов запуск завершится ошибкой `ModuleNotFoundError` в Python или ошибкой резолвинга модулей в TypeScript.
- **Что запускать:**
  ```bash
  ./rebuild.sh
  ```

---

### Сценарий Г. Изменились модели базы данных ([`app/db/models.py`](app/db/models.py)) или миграции
- **Почему это важно:** Несоответствие между Python-классами моделей и таблицами SQLite приводит к фатальным ошибкам `sqlite3.OperationalError: no such column`.
- **Что запускать:**
  - Если изменения обратно-совместимы и нужно сохранить имеющиеся данные:
    ```bash
    uv run python manage.py makemigrations db
    uv run python manage.py migrate
    ```
    *(Либо просто запустить [`run_local.py:main()`](run_local.py:34), который накатит миграции автоматически).*
  - Если внесены ломающие изменения в схему БД или возник конфликт миграций:
    ```bash
    ./rebuild.sh
    ```

---

### Сценарий Д. Повседневная разработка бэкенда ([`app/api/v1/endpoints/`](app/api/v1/endpoints/), [`app/services/`](app/services/), [`app/ml/`](app/ml/))
- **Почему это важно:** При правках Python-файлов нет необходимости каждый раз сбрасывать БД и пересобирать фронтенд.
- **Что запускать:**
  ```bash
  uv run python run_local.py
  ```
  *(Uvicorn подхватит изменения налету благодаря включенному флагу `reload=True`).*

---

### Сценарий Е. Появились странные ошибки импортов или "фантомные" баги линтера/тестов
- **Почему это важно:** Устаревшие файлы кэша `.pytest_cache`, `.ruff_cache`, `.mypy_cache` или скомпилированный байткод `__pycache__` могут использовать старые версии удаленных модулей.
- **Что запускать:**
  ```bash
  ./rebuild.sh
  ```

---

## 4. Архитектурные нюансы технологического стека

### 1. Как работает раздача статики и Single Page Application (SPA)
В [`app/main.py:get_spa_index_path()`](app/main.py:86) и [`app/main.py:spa_catch_all()`](app/main.py:153) реализован SPA-маршрутизатор:
- Любые не-API запросы направляются на `frontend/dist/index.html`.
- Директория `frontend/dist/assets/` монтируется через `StaticFiles`.
- Если директория `frontend/dist/` отсутствует (или не была собрана), сервер переключается в режим заглушки, сообщая о необходимости сборки фронтенда.

### 2. Гибридная аутентификация
В проекте сосуществуют две системы аутентификации:
- **FastAPI JWT / OAuth2 ([`app/api/v1/endpoints/auth.py:login_for_access_token()`](app/api/v1/endpoints/auth.py:20))**: выдает токены Bearer для SPA фронтенда.
- **Django Session Auth ([`app/core/django_settings.py:MIDDLEWARE`](app/core/django_settings.py:65))**: обеспечивает доступ к админке `/admin/`.

Скрипт пересборки создает учетную запись `admin` / `admin` с привязкой проверенного email-адреса через `allauth.account.models.EmailAddress`, что гарантирует бесперебойную работу обоих механизмов входа.

### 3. Автономность скрипта на macOS
Скрипт [`rebuild.sh`](rebuild.sh) специально спроектирован для разработчиков, использующих macOS:
- Не требует предварительной установки `uv` (скачивает и запускает установщик Astral `uv` автоматически).
- Проверяет наличие `node` и `npm`, выводя подсказку по установке через `brew install node`.
- Определяет абсолютный путь к корню репозитория независимо от того, из какой папки был вызван скрипт.

---

## 5. Сводная шпаргалка разработчика (Quick Cheat Sheet)

```bash
# 1. Полная чистая пересборка (БД в 0, чистка кэша, сборка фронтенда, admin/admin):
./rebuild.sh                      # на macOS / Linux
uv run python rebuild.py          # на Windows / кроссплатформенно

# 2. Обычный запуск сервера разработки (с сохранением данных в БД):
uv run python run_local.py

# 3. Запуск полного набора проверок качества кода:
uv run pytest                     # юнит- и интеграционные тесты бэкенда
uv run ruff check .               # проверка стиля и линтинг Python
uv run mypy app tests             # строгая проверка типов Python
cd frontend && npm test           # тесты React SPA (Vitest)
cd frontend && npx tsc --noEmit   # проверка типов TypeScript
```
