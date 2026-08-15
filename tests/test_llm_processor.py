# filename: tests/test_llm_processor.py
"""Unit tests for the LLM intelligence engine, dynamic summarizer, and fallback logic."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.domain.entities import ConversationAnalysis
from app.domain.exceptions import LLMServiceError
from app.ml.llm_processor import LLMIntelligenceEngine, LocalDynamicSummarizer


@pytest.fixture
def engine() -> LLMIntelligenceEngine:
    return LLMIntelligenceEngine()


@pytest.mark.asyncio
async def test_extract_intelligence_empty_transcript(engine: LLMIntelligenceEngine) -> None:
    """Validates empty and whitespace-only transcript input handling."""
    res1 = await engine.extract_intelligence("", language="ru")
    assert isinstance(res1, ConversationAnalysis)
    assert res1.title == "Пустая запись"
    assert "отсутствует" in res1.executive_summary or "No speech" in res1.executive_summary
    assert res1.key_decisions == []
    assert res1.action_items == []

    res2 = await engine.extract_intelligence("   \n\t  ", language="en")
    assert isinstance(res2, ConversationAnalysis)
    assert res2.action_items == []


@pytest.mark.asyncio
async def test_extract_intelligence_short_transcript(engine: LLMIntelligenceEngine) -> None:
    """Validates lightweight processing for very short transcripts."""
    short_text = "SPEAKER_01: Hello team."
    res = await engine.extract_intelligence(short_text, language="en")
    assert isinstance(res, ConversationAnalysis)
    assert res.executive_summary != ""
    assert res.overall_sentiment in ("POSITIVE", "NEUTRAL", "NEGATIVE")


@pytest.mark.asyncio
async def test_extract_intelligence_local_fallback_ru(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates dynamic local summarization for Russian transcripts when API key is mock."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "mock-key")

    transcript = (
        "SPEAKER_00: Мы собрались, чтобы обсудить разработку модуля выжимки встречами. "
        "SPEAKER_01: Отлично. Согласовали выгрузку в PDF, DOCX, SRT и VTT. "
        "SPEAKER_00: Иван должен завершить юнит-тестирование до 2026-08-20. Это срочно."
    )

    result = await engine.extract_intelligence(transcript, language="ru")

    assert isinstance(result, ConversationAnalysis)
    assert "модуля" in result.executive_summary or "собрались" in result.executive_summary
    assert len(result.key_decisions) > 0
    assert any(
        "Согласовали" in d or "выгрузку" in d or "Обсуждение" in d for d in result.key_decisions
    )
    assert len(result.action_items) > 0
    assert result.action_items[0].priority in ("HIGH", "MEDIUM", "LOW")
    assert result.overall_sentiment == "POSITIVE"


@pytest.mark.asyncio
async def test_extract_intelligence_local_fallback_en(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates dynamic local extractive summarization for English transcripts."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "mock-key")

    transcript = (
        "SPEAKER_00: We agreed to migrate our database to PostgreSQL next week. "
        "SPEAKER_01: Sarah need to verify the schema backup by 2026-08-15. "
        "SPEAKER_00: Great progress, all performance benchmarks are excellent."
    )

    result = await engine.extract_intelligence(transcript, language="en")

    assert isinstance(result, ConversationAnalysis)
    assert result.overall_sentiment == "POSITIVE"
    assert len(result.key_decisions) > 0
    assert len(result.action_items) > 0


@pytest.mark.asyncio
async def test_extract_intelligence_long_transcript_chunking(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates chunking and map-reduce condensation for large transcripts."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "mock-key")

    sentence = "Участники команды обсудили текущие аспекты архитектурного решения. "
    long_transcript = sentence * 300  # Creates ~18,000 character string

    result = await engine.extract_intelligence(long_transcript, language="ru")
    assert isinstance(result, ConversationAnalysis)
    assert len(result.executive_summary) > 0


@pytest.mark.asyncio
async def test_extract_intelligence_external_llm_api_success(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates successful integration with external LLM API."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-valid-test-key")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "gpt-4o")

    mock_llm_response = {
        "executive_summary": "The team agreed on PostgreSQL migration.",
        "key_decisions": ["Migrate database to PostgreSQL"],
        "action_items": [
            {
                "task": "Prepare database migration scripts",
                "owner": "Sarah",
                "due_date": "2026-08-15",
                "priority": "HIGH",
            }
        ],
        "overall_sentiment": "POSITIVE",
    }

    fake_http_data = {"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]}

    mock_post = AsyncMock()
    mock_post.return_value = httpx.Response(200, json=fake_http_data)

    with patch("httpx.AsyncClient.post", new=mock_post):
        transcript = (
            "SPEAKER_00: Let's finalize the database migration tasks for core cluster "
            "today before EOD so we can begin performance benchmarking."
        )
        result = await engine.extract_intelligence(transcript, language="en")

        assert result.executive_summary == "The team agreed on PostgreSQL migration."
        assert result.key_decisions == ["Migrate database to PostgreSQL"]
        assert len(result.action_items) == 1
        assert result.action_items[0].task == "Prepare database migration scripts"
        assert result.action_items[0].owner == "Sarah"
        assert result.action_items[0].priority == "HIGH"
        assert result.overall_sentiment == "POSITIVE"


@pytest.mark.asyncio
async def test_extract_intelligence_llm_api_retry_and_error_handling(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates retry without response_format when HTTP 400 is returned, and final failure raising LLMServiceError."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-valid-test-key")

    # 1. First call 400, second retry 200 success
    valid_resp = {
        "title": "Успешный повтор",
        "executive_summary": "Ответ получен со второй попытки.",
        "key_decisions": [],
        "action_items": [],
        "overall_sentiment": "NEUTRAL",
    }
    resp_400 = httpx.Response(400, text="Bad Request: json_object unsupported")
    resp_200 = httpx.Response(
        200, json={"choices": [{"message": {"content": json.dumps(valid_resp)}}]}
    )

    with patch("httpx.AsyncClient.post", side_effect=[resp_400, resp_200]):
        res = await engine._call_llm_api("Текст стенограммы", is_russian=True)
        assert res is not None
        assert res.title == "Успешный повтор"

    # 2. Both calls fail -> raises LLMServiceError
    resp_500 = httpx.Response(500, text="Internal Server Error")
    with patch("httpx.AsyncClient.post", side_effect=[resp_400, resp_500]):
        with pytest.raises(LLMServiceError) as exc_info:
            await engine._call_llm_api("Текст стенограммы", is_russian=True)
        assert "HTTP error 500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_extract_intelligence_llm_api_failure_fallback(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates graceful fallback to local dynamic summarizer when LLM API call fails."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-valid-test-key")

    mock_post = AsyncMock(side_effect=httpx.HTTPError("Service Unavailable"))

    with patch("httpx.AsyncClient.post", new=mock_post):
        transcript = (
            "SPEAKER_00: Мы должны запустить новый релиз сегодня вечером. "
            "SPEAKER_01: Согласовали график деплоя. Анна должна проверить логи локально."
        )
        result = await engine.extract_intelligence(transcript, language="ru")

        assert isinstance(result, ConversationAnalysis)
        assert len(result.executive_summary) > 0
        assert len(result.key_decisions) > 0


@pytest.mark.asyncio
async def test_extract_intelligence_malformed_json_fallback(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates fallback when LLM API returns invalid JSON formatting."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "sk-valid-test-key")

    fake_http_data = {
        "choices": [
            {
                "message": {
                    "content": "This is raw non-json plain text response from faulty LLM model."
                }
            }
        ]
    }

    mock_post = AsyncMock()
    mock_post.return_value = httpx.Response(200, json=fake_http_data)

    with patch("httpx.AsyncClient.post", new=mock_post):
        transcript = (
            "SPEAKER_00: We decided to proceed with sprint planning for "
            "the upcoming quarter right after end-to-end testing."
        )
        result = await engine.extract_intelligence(transcript, language="en")

        assert isinstance(result, ConversationAnalysis)
        assert len(result.executive_summary) > 0


def test_local_dynamic_summarizer_helper_functions() -> None:
    """Directly tests LocalDynamicSummarizer helper methods."""
    # Empty sentences handling
    assert LocalDynamicSummarizer.extract_title([], is_russian=True) == "Обсуждение встречи"
    assert LocalDynamicSummarizer.extract_title([], is_russian=False) == "Meeting Discussion"
    assert "не содержит" in LocalDynamicSummarizer.extract_summary([], is_russian=True)
    assert "does not contain" in LocalDynamicSummarizer.extract_summary([], is_russian=False)

    # Short clean first sentence
    short_title_ru = LocalDynamicSummarizer.extract_title(["Да."], is_russian=True)
    assert short_title_ru == "Да."

    # Long clean sentence with stop words only (len > 40, words < 2) -> triggers line 248
    long_stop_words = "Это все было только для него и для нее и еще потом."
    title_stop = LocalDynamicSummarizer.extract_title([long_stop_words], is_russian=True)
    assert title_stop.endswith("...")

    # Action items priorities: HIGH and LOW -> triggers lines 376 and 378
    actions_high = LocalDynamicSummarizer.extract_action_items(
        ["Нужно срочно проверить базу данных."], is_russian=True
    )
    assert len(actions_high) > 0
    assert actions_high[0].priority == "HIGH"

    actions_low = LocalDynamicSummarizer.extract_action_items(
        ["Нужно по возможности обновить документацию к релизу."], is_russian=True
    )
    assert len(actions_low) > 0
    assert actions_low[0].priority == "LOW"

    # Negative sentiment analysis -> triggers line 463
    sent_neg_ru = LocalDynamicSummarizer.analyze_sentiment(
        "Возникла проблема, ошибка и критический сбой в системе.", is_russian=True
    )
    assert sent_neg_ru == "NEGATIVE"

    sent_neg_en = LocalDynamicSummarizer.analyze_sentiment(
        "We have a critical blocker, error and severe issue.", is_russian=False
    )
    assert sent_neg_en == "NEGATIVE"

    # Decisions fallback
    decisions = LocalDynamicSummarizer.extract_decisions(
        ["We decided to ship feature A."], is_russian=False
    )
    assert len(decisions) > 0
    assert "ship feature A" in decisions[0]


def test_parse_json_response_edge_cases(engine: LLMIntelligenceEngine) -> None:
    """Validates parsing JSON payloads with invalid sentiment, priority, or missing title."""
    payload = {
        "title": "",
        "executive_summary": "Test summary",
        "key_decisions": ["D1"],
        "action_items": [
            {"task": "Task 1", "priority": "UNKNOWN_PRIORITY", "owner": None, "due_date": None}
        ],
        "overall_sentiment": "INVALID_SENTIMENT",
    }
    raw_content = json.dumps(payload)
    parsed = engine._parse_json_response(raw_content, is_russian=True)
    assert parsed.overall_sentiment == "NEUTRAL"
    assert parsed.action_items[0].priority == "MEDIUM"


def test_local_dynamic_summarizer_vector_and_cosine_similarity() -> None:
    """Validates TF-IDF vector generation and cosine similarity calculation."""
    sentences = [
        "Архитектура микросервисов на Python FastAPI.",
        "Разработка серверных приложений на FastAPI и PostgreSQL.",
        "Кулинарные рецепты итальянской кухни.",
    ]
    vectors = LocalDynamicSummarizer._compute_sentence_vectors(sentences, stop_words={"на", "и"})
    assert len(vectors) == 3

    sim_tech = LocalDynamicSummarizer._cosine_similarity(vectors[0], vectors[1])
    sim_diff = LocalDynamicSummarizer._cosine_similarity(vectors[0], vectors[2])
    assert sim_tech > sim_diff


@pytest.mark.asyncio
async def test_extract_intelligence_custom_base_url_and_options(
    engine: LLMIntelligenceEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates that custom LLM_BASE_URL, temperature, and max_tokens are correctly sent in payload."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "custom-api-token")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "LLM_MODEL_NAME", "llama3.1")
    monkeypatch.setattr(settings, "LLM_TEMPERATURE", 0.3)
    monkeypatch.setattr(settings, "LLM_MAX_TOKENS", 2048)

    mock_llm_response = {
        "title": "Интеграция с Ollama",
        "executive_summary": "Успешная проверка локальной модели LLaMA.",
        "key_decisions": ["Использовать локальный инференс"],
        "action_items": [],
        "overall_sentiment": "POSITIVE",
    }

    mock_post = AsyncMock()
    mock_post.return_value = httpx.Response(
        200, json={"choices": [{"message": {"content": json.dumps(mock_llm_response)}}]}
    )

    with patch("httpx.AsyncClient.post", new=mock_post):
        result = await engine.extract_intelligence(
            "SPEAKER_01: Мы подробно обсудили развертывание локальной модели LLaMA на собственном сервере компании для конфиденциальности.",
            language="ru",
        )
        assert result.title == "Интеграция с Ollama"
        assert result.overall_sentiment == "POSITIVE"

        mock_post.assert_called_once()
        url_called, kwargs_called = mock_post.call_args[0][0], mock_post.call_args[1]
        assert url_called == "http://localhost:11434/v1/chat/completions"
        assert kwargs_called["json"]["temperature"] == 0.3
        assert kwargs_called["json"]["max_tokens"] == 2048
        assert kwargs_called["json"]["model"] == "llama3.1"
