"""Клиент LLM: OpenAI API или демо-режим без ключа."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.guardrails.policies import SYSTEM_PROMPT

load_dotenv()


@dataclass
class LLMResponse:
    text: str
    model: str
    mode: str  # "openai" | "demo"


class LLMClient:
    """Обёртка над OpenAI Chat Completions с fallback на демо-ответы."""

    def __init__(self, model: str | None = None):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client = None

        if self.api_key and not self.api_key.startswith("sk-your"):
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except Exception:
                self._client = None

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def generate(self, messages: list[dict[str, str]], temperature: float = 0.3) -> LLMResponse:
        if self._client:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=800,
            )
            text = response.choices[0].message.content or ""
            return LLMResponse(text=text.strip(), model=self.model, mode="openai")

        return LLMResponse(
            text=self._demo_reply(messages),
            model="demo-assistant",
            mode="demo",
        )

    def _demo_reply(self, messages: list[dict[str, str]]) -> str:
        """Демо-режим для скринкаста без API-ключа."""
        user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                user_msg = m["content"].lower()
                break

        if "tf-idf" in user_msg or "tfidf" in user_msg:
            return (
                "TF-IDF (Term Frequency — Inverse Document Frequency) взвешивает слова: "
                "частые в документе, но редкие в корпусе получают больший вес. "
                "Формула: tf(t,d) × idf(t), где idf(t) = log(N / df(t)). "
                "Это помогает отличать значимые термины от шумовых стоп-слов."
            )
        if "guardrails" in user_msg or "гардрейл" in user_msg:
            return (
                "Guardrails — слой проверок до и после LLM: фильтрация ввода "
                "(injection, PII, токсичность), валидация вывода и политики домена. "
                "В этом проекте реализованы InputGuard и OutputGuard с логированием каждого этапа."
            )
        if "python" in user_msg or "питон" in user_msg:
            return (
                "Python — популярный язык для ML и data science. "
                "Для NLP часто используют NLTK, spaCy, scikit-learn. "
                "Уточните задачу: синтаксис, библиотеки или пример кода?"
            )
        if "привет" in user_msg or "здравств" in user_msg:
            return (
                "Здравствуйте! Я учебный ассистент по AI и программированию. "
                "Спросите про ML, Python, guardrails или ваш курсовой проект."
            )

        return (
            "Это демо-режим без API-ключа OpenAI. "
            "Я могу ответить на вопросы про Python, ML, TF-IDF и guardrails. "
            "Для полноценных ответов добавьте OPENAI_API_KEY в файл .env."
        )

    def build_messages(self, history: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
        return [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_text}]
