# AG-Avito-bot

Telegram-бот для генерации файла автозагрузки Авито.

## Стек

- Python 3.12+ / uv
- aiogram 3.25+ (FSM, Dispatcher DI)
- aiosqlite (ProjectDB)
- Anthropic Claude API (LLM-анализ)
- fpdf2 (PDF-отчёты)
- pytest + pytest-asyncio

## Структура

```
src/avito_autoload/
  bot/
    handlers/    — start, collect (7 вопросов), callbacks, analysis (4 этапа)
    services/    — ca_analyzer, template_builder, category_fetcher, competitor_analyzer, pipeline_runner
    storage/     — database.py (ProjectDB), files.py (FileStorage)
    utils/       — pdf.py
    states.py    — FSM-стейты (ProjectStates)
    keyboards.py — инлайн-клавиатуры
    config.py    — BotConfig
    main.py      — точка входа
  parsers/       — xlsx_parser
  describer/     — llm_describer
  categorizers/  — llm_categorizer
  exporters/     — xlsx_exporter
tests/
  conftest.py       — фикстуры, моки (make_message, make_state, make_callback)
  test_bot.py       — unit-тесты (config, states, keyboards, DB, services)
  test_handlers.py  — интеграция хендлеров
  test_flow.py      — полный диалог /start → complete
```

## Команды

```bash
uv run pytest tests/ -v            # Все тесты
uv run pytest tests/ -x -q         # Быстро, до первой ошибки
uv run ruff check src/             # Линтер
```

## Правила

- **Никогда не вызывать реальный Anthropic API в тестах** — всегда мокать `_call_anthropic` или сервисные функции
- После изменения хендлера — запустить `uv run pytest tests/test_handlers.py -v`
- Локальные импорты в хендлерах (analysis.py, callbacks.py) — патчить в модуле-источнике:
  - `markdown_to_pdf` → `avito_autoload.bot.utils.pdf.markdown_to_pdf`
  - `run_ca_analysis` → `avito_autoload.bot.handlers.analysis.run_ca_analysis`
- FSM-стейты добавлять в `states.py` и в `test_bot.py::test_states_exist`

## VPS

- IP: 144.31.75.151, user: root
- Путь: `/root/project/AG-Avito-bot`
- Сервис: `ag-avito-bot.service`
- Перезапуск: `ssh -i ~/.ssh/deploy_avito root@144.31.75.151 'systemctl restart ag-avito-bot'`
