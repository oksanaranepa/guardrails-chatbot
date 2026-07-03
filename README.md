# Чат-бот с Guardrails

Учебный ассистент курса по AI с многоуровневой защитой диалога: проверка ввода, генерация ответа LLM, валидация вывода и структурированное логирование.

## Цель проекта

Разработать чат-бота, способного вести диалог в учебной тематике и обеспечивать **безопасность и этичность** взаимодействия за счёт guardrails на входе и выходе.

## Задачи

1. Реализовать **Input Guard** — фильтрация prompt injection, вредоносных запросов, PII и off-topic.
2. Реализовать **Output Guard** — маскирование PII, блокировка утечки системного промпта и вредоносного контента.
3. Интегрировать LLM (OpenAI API) с **демо-режимом** без ключа.
4. Вести **логи** всех этапов пайплайна в JSONL.
5. Создать **интерактивную демонстрацию** на Streamlit.
6. Провести **эксперименты** и зафиксировать выводы.

## Архитектура

```
Пользователь
    │
    ▼
┌─────────────┐
│ Input Guard │  injection / harmful / PII / off-topic
└──────┬──────┘
       │ OK
       ▼
┌─────────────┐
│     LLM     │  OpenAI API или demo-режим
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ Output Guard │  PII mask / prompt leak / harmful
└──────┬───────┘
       │
       ▼
   Ответ + логи
```

## Структура репозитория

```
├── src/
│   ├── guardrails/     # InputGuard, OutputGuard, политики
│   ├── bot/            # GuardedChatbot, LLMClient
│   ├── logging/        # SessionLogger (JSONL)
│   └── app/            # Streamlit UI
├── experiments/
│   └── test_guardrails.py
├── docs/
│   └── ANALYSIS.md     # Анализ результатов
├── logs/
│   └── sessions.jsonl  # создаётся при запуске
├── requirements.txt
└── .env.example
```

## Установка

```bash
# 1. Клонировать репозиторий и перейти в папку
cd guardrails-chatbot

# 2. Создать виртуальное окружение 
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. (Опционально) Настроить OpenAI API
copy .env.example .env
# Укажите OPENAI_API_KEY в .env
```

## Запуск

### Интерактивная демонстрация (Streamlit)

```bash
streamlit run src/app/streamlit_app.py
```

Откроется браузер с чатом. В боковой панели:
- переключатели политик guardrails;
- кнопки тестовых запросов (injection, PII, off-topic);
- ID сессии и путь к логам.

### Эксперименты (автотесты guardrails)

```bash
python experiments/test_guardrails.py
```

Скрипт прогоняет тест-кейсы Input/Output Guard и E2E-пайплайн, выводит отчёт в консоль и пишет логи в `logs/sessions.jsonl`.

## Логирование

Каждое событие записывается в `logs/sessions.jsonl` (формат JSON Lines):

| Событие | Описание |
|---------|----------|
| `session_created` | Новая сессия, снимок политики |
| `user_message_received` | Входящее сообщение |
| `input_guard` | Результат проверки ввода |
| `llm_response` | Модель и режим генерации |
| `output_guard` | Результат проверки вывода |
| `turn_completed` | Итог хода диалога |

Пример записи:

```json
{"timestamp": "2026-07-03T12:00:00+00:00", "session_id": "a1b2c3d4", "event": "input_guard", "payload": {"allowed": false, "violations": ["prompt_injection"], "details": ["..."]}}
```

## Guardrails

### Input Guard
- **Prompt injection** — паттерны вроде «игнорируй инструкции», «ты теперь», jailbreak.
- **Harmful requests** — взлом, вредоносный софт, незаконные действия.
- **PII** — email, телефон, карта, паспорт.
- **Off-topic** — фильтр по ключевым словам учебной тематики.
- **Длина** — ограничение размера ввода.

### Output Guard
- Маскирование PII в ответе (`[СКРЫТО]`).
- Блокировка утечки системного промпта.
- Отсечение вредоносного контента.
- Ограничение длины ответа.

## Анализ результатов

Подробный разбор экспериментов, метрик и выводов — в [docs/ANALYSIS.md](docs/ANALYSIS.md).

## Технологии

- Python 3.10+
- Streamlit
- OpenAI API (опционально)
- regex-эвристики для guardrails


