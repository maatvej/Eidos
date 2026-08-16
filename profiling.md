# Руководство по профилированию и анализу производительности (cProfile & SnakeViz)

В платформу Eidos интегрирована высокопроизводительная, модульная подсистема профилирования на базе стандартных библиотек Python `cProfile` и `pstats`, дополненная автоматическим анализатором узких мест [`ProfileAnalyzer`](app/core/profiler_analyzer.py), консольным интерфейсом [`profiler_cli`](app/core/profiler_cli.py) и интерактивной визуализацией через `SnakeViz`.

---

## 1. Архитектура и возможности

- **Zero Overhead в выключенном состоянии:** При `PROFILING_ENABLED=False` все декораторы, контекстные менеджеры и middleware работают через быстрые Guard Clauses с нулевыми накладными расходами на вызов.
- **Поддержка синхронного и асинхронного кода:** Единый контекстный менеджер [`ProfileContext`](app/core/profiler.py) поддерживает как `with`, так и `async with`.
- **Автоматическая структуризация дампов:** Профили сохраняются в двоичном формате `.prof` (для `pstats` и `SnakeViz`) и текстовом виде `.txt` с группировкой по подкаталогам:
  - `profiles/fastapi/` — сквозное профилирование HTTP-запросов FastAPI;
  - `profiles/django/` — профилирование запросов Django Allauth и ORM;
  - `profiles/ml_inference/` — распознавание речи (Faster-Whisper), диаризация и эмбеддинги голосов;
  - `profiles/audio/` — нормализация и предобработка аудио через FFmpeg;
  - `profiles/transcription/` — загрузка, потоковая запись и манипуляции со стенограммами;
  - `profiles/account/` — управление профилем, выборка истории и удаление записей;
  - `profiles/auth/` — аутентификация Django ORM и генерация JWT-токенов;
  - `profiles/exports/` — компиляция документов (TXT, SRT, VTT, DOCX, PDF);
  - `profiles/llm/` — извлечение сущностей, саммаризация и алгоритм LexRank;
  - `profiles/workers/` — фоновые конвейеры задач обработки.
- **Диагностический движок эвристик:** Автоматически выявляет доминирование ORM/N+1 запросов, задержки инференса нейросетей, процессорное время регулярных выражений, задержки компиляции отчетов и дисковый ввод-вывод аудио.

---

## 2. Конфигурация через переменные окружения (.env)

Настройки профилирования задаются в файле `.env` или через переменные окружения (класс [`Settings`](app/core/config.py)):

```env
# Включение/отключение профилирования (True / False)
PROFILING_ENABLED=True

# Корневой каталог для сохранения дампов
PROFILING_OUTPUT_DIR=profiles

# Критерий сортировки pstats (cumulative, time, calls, tottime)
PROFILING_SORT_BY=cumulative

# Количество функций в генерируемом текстовом отчете
PROFILING_RESTRICTION_LIMIT=30

# Префиксы URL-путей, исключаемые из профилирования (статические ресурсы, healthcheck, SSE)
PROFILING_EXCLUDE_PATHS=["/health", "/static", "/django-static", "/django_static", "/assets", "/frontend", "/api/v1/events", "/sse"]
```

---

## 3. Способы профилирования

### Вариант A. Автоматическое Middleware-профилирование (FastAPI & Django)

При установке `PROFILING_ENABLED=True` в `.env`, каждый входящий HTTP-запрос автоматически профилируется. В ответ сервера внедряются информационные HTTP-заголовки:
- `X-Profile-Enabled: true`
- `X-Profile-Time: 0.0421s`
- `X-Profile-File: fastapi_POST_api_v1_transcription_upload_a1b2c3.prof`

Дампы автоматически сохраняются в каталогах `profiles/fastapi/` и `profiles/django/`.

### Вариант B. Профилирование функций через декораторы

В модуле [`app/core/profiler.py`](app/core/profiler.py) доступны готовые декораторы:

```python
from app.core.profiler import profile_async, profile_sync, profile_callable, profile_worker_task

# 1. Асинхронные корутины
@profile_async(name="custom_audio_pipeline", subfolder="custom")
async def run_pipeline(audio_path: Path):
    ...

# 2. Синхронные функции и методы
@profile_sync(name="custom_feature_calc", subfolder="custom")
def calculate_features(data: list[float]) -> list[float]:
    ...

# 3. Универсальный декоратор для sync и async
@profile_callable(name="universal_task", subfolder="custom")
def universal_step():
    ...

# 4. Фоновые задачи воркеров
@profile_worker_task(name="background_batch_pipeline", subfolder="workers")
async def process_batch(ctx: dict, batch_id: str):
    ...
```

### Вариант C. Точечное профилирование через контекстные менеджеры

Для изолированного замера произвольного блока кода используйте [`ProfileContext`](app/core/profiler.py):

```python
from app.core.profiler import ProfileContext

# Синхронный блок
with ProfileContext(name="matrix_multiplication", subfolder="benchmarks") as prof:
    result = heavy_computation()

if prof.result:
    print(f"Затрачено времени: {prof.result.total_time:.4f}s")
    print(f"Дамп сохранен в: {prof.result.prof_path}")

# Асинхронный блок
async with ProfileContext(name="async_io_block", subfolder="benchmarks") as prof:
    await fetch_remote_data()
```

---

## 4. Консольная утилита анализа (CLI Profiler)

Для работы с сохраненными профилями используется модуль [`app/core/profiler_cli.py`](app/core/profiler_cli.py):

### 4.1. Анализ последнего сгенерированного профиля
```bash
python -m app.core.profiler_cli --latest
```

### 4.2. Анализ конкретного файла профиля
```bash
python -m app.core.profiler_cli profiles/ml_inference/speech_transcription_and_diarization_1a2b3c.prof
```

### 4.3. Вывод только горячих точек (Hotspots) с сортировкой
```bash
# Сортировка по суммарному времени (cumulative)
python -m app.core.profiler_cli --latest --hotspots-only --sort-by cumulative --limit 20

# Сортировка по чистому процессорному времени (time)
python -m app.core.profiler_cli --latest --hotspots-only --sort-by time --limit 15
```

### 4.4. Экспорт отчета в формате Markdown
```bash
python -m app.core.profiler_cli --latest --markdown
```

### 4.5. Экспорт отчета в формате JSON
```bash
python -m app.core.profiler_cli --latest --json
```

### 4.6. Сравнение двух профилей (поиск регрессий и оценка ускорения)
```bash
python -m app.core.profiler_cli --compare profiles/base_transcribe.prof --target profiles/optimized_transcribe.prof
```
*Вывод покажет процент изменения времени, коэффициент ускорения (speedup factor) и флаг улучшения.*

### 4.7. Очистка устаревших дампов
```bash
# Удалить профили старше 7 дней (по умолчанию)
python -m app.core.profiler_cli --clean

# Удалить профили старше 3 дней
python -m app.core.profiler_cli --clean --max-age-days 3
```

---

## 5. Интерактивная визуализация с помощью SnakeViz (Flame Graphs)

`SnakeViz` позволяет просматривать интерактивные круговые диаграммы (Sunburst) и диаграммы стека вызовов (Flame Graph / Icicle Graph) прямо в браузере.

### Запуск визуализации через CLI:
```bash
# Открыть последний профиль в браузере на порту 8080:
python -m app.core.profiler_cli --latest --snakeviz --port 8080

# Открыть конкретный файл профиля:
python -m app.core.profiler_cli profiles/ml_inference/whisper_speech_transcription_abc123.prof --snakeviz --port 8080

# Запуск напрямую через модуль snakeviz:
python -m snakeviz profiles/transcription/transcription_upload_endpoint_xyz789.prof --port 8080
```

### Режимы интерфейса SnakeViz:
- **Style: Icicle (Flame Graph):** Наглядное дерево вызовов сверху вниз. Ширина блока пропорциональна времени выполнения. Позволяет мгновенно находить самые "тяжелые" функции.
- **Style: Sunburst:** Радиальная визуализация вложенности вызовов.
- **Таблица вызовов:** Сортировка по `ncalls`, `tottime`, `percall`, `cumtime`, фильтрация по имени модуля и функции.

---

## 6. Пошаговый сценарий: Замер реальной рабочей нагрузки

1. **Активация:** Откройте `.env` и установите:
   ```env
   PROFILING_ENABLED=True
   ```
2. **Запуск сервера:**
   ```bash
   python run_local.py
   ```
3. **Генерация нагрузки:**
   - Откройте веб-интерфейс `http://localhost:8000/` в браузере.
   - Загрузите тестовый аудиофайл для расшифровки.
   - Дождитесь завершения обработки (нормализация, Faster-Whisper, PyAnnote/акустическая кластеризация, LLM-саммаризация).
4. **Просмотр результатов:**
   В каталоге `profiles/` появятся детальные дампы по подсистемам:
   - `profiles/transcription/` — замеры загрузки и стриминга;
   - `profiles/audio/` — замеры работы FFmpeg;
   - `profiles/ml_inference/` — замеры инференса нейросетей и кластеризации;
   - `profiles/llm/` — замеры языкового анализа;
   - `profiles/workers/` — общий замер конвейера воркера.
5. **Анализ узких мест в консоли:**
   ```bash
   python -m app.core.profiler_cli --latest
   ```
6. **Запуск интерактивного Flame Graph:**
   ```bash
   python -m app.core.profiler_cli --latest --snakeviz --port 8080
   ```

---

## 7. Автоматические эвристики и диагностика

Анализатор [`ProfileAnalyzer`](app/core/profiler_analyzer.py) оценивает соотношение времени выполнения компонентов и автоматически выводит рекомендации:

| Паттерн задержки | Порог срабатывания | Диагностическое заключение |
| :--- | :--- | :--- |
| **База данных / ORM** | `> 40%` общего времени | *High Database/ORM latency detected. Check for N+1 queries.* |
| **Инференс ML / Torch** | `> 60%` общего времени | *ML / Torch compute dominates session. Ensure GPU acceleration is enabled.* |
| **Регулярные выражения** | `> 15%` self-time | *High Regex self-time detected. Consider precompiling regex patterns.* |
| **Экспорт документов** | `> 35%` общего времени | *High Document Export latency detected. Consider async report buffering.* |
| **Аудио I/O и FFmpeg** | `> 35%` общего времени | *High Audio Processing & I/O latency detected. Check disk I/O and FFmpeg.* |
