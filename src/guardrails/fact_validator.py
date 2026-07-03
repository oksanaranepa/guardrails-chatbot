"""Валидация фактов ответа через TF-IDF + cosine similarity."""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# База эталонных фактов курса (ground truth для проверки галлюцинаций)
KNOWLEDGE_BASE: list[dict[str, str]] = [
    {
        "topic": "tfidf",
        "text": (
            "TF-IDF взвешивает слова: term frequency умножается на inverse document frequency. "
            "IDF снижает вес частых слов корпуса. Применяется в NLP и классификации текстов."
        ),
    },
    {
        "topic": "guardrails",
        "text": (
            "Guardrails — слой проверок до и после LLM: input guard, output guard, "
            "политики безопасности, блокировка prompt injection и PII."
        ),
    },
    {
        "topic": "bow",
        "text": (
            "Bag of Words представляет документ как вектор частот слов без учёта порядка. "
            "Простая векторизация, но игнорирует семантику и редкость терминов."
        ),
    },
    {
        "topic": "python",
        "text": (
            "Python — язык программирования для data science, ML и автоматизации. "
            "Популярные библиотеки: numpy, pandas, scikit-learn, nltk."
        ),
    },
    {
        "topic": "logistic_regression",
        "text": (
            "Логистическая регрессия — линейный классификатор для бинарных меток. "
            "Использует сигмоиду, обучается по функции потерь log-loss."
        ),
    },
]


@dataclass
class FactValidationResult:
    grounded: bool
    best_topic: str | None
    similarity: float
    threshold: float
    details: str


class FactValidator:
    """
    Проверяет, насколько ответ согласуется с базой знаний.

    Использует sklearn TfidfVectorizer (с IDF) и cosine similarity —
    в отличие от наивного TF+cosine без IDF.
    """

    def __init__(self, threshold: float = 0.12, knowledge_base: list[dict[str, str]] | None = None):
        self.threshold = threshold
        self.knowledge_base = knowledge_base or KNOWLEDGE_BASE
        self._topics = [item["topic"] for item in self.knowledge_base]
        self._texts = [item["text"] for item in self.knowledge_base]
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
        )
        self._kb_matrix = self._vectorizer.fit_transform(self._texts)

    def validate(self, user_question: str, answer: str) -> FactValidationResult:
        """Сравнивает пару (вопрос+ответ) с каждым фрагментом базы знаний."""
        combined = f"{user_question} {answer}".strip()
        if len(combined) < 20:
            return FactValidationResult(
                grounded=True,
                best_topic=None,
                similarity=1.0,
                threshold=self.threshold,
                details="Короткий ответ — проверка пропущена",
            )

        query_vec = self._vectorizer.transform([combined])
        scores = cosine_similarity(query_vec, self._kb_matrix)[0]
        best_idx = int(scores.argmax())
        best_score = float(scores[best_idx])
        best_topic = self._topics[best_idx]

        grounded = best_score >= self.threshold
        details = (
            f"max cosine(TF-IDF)={best_score:.3f} с темой '{best_topic}' "
            f"(порог {self.threshold})"
        )
        return FactValidationResult(
            grounded=grounded,
            best_topic=best_topic,
            similarity=best_score,
            threshold=self.threshold,
            details=details,
        )
