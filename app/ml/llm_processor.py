# filename: app/ml/llm_processor.py
"""LLM post-processing engine for extracting executive summaries and conversation analytics."""

import asyncio
import json
import math
import re
from collections import Counter
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.domain.entities import ActionItem, ConversationAnalysis
from app.domain.exceptions import LLMServiceError


RU_STOP_WORDS: set[str] = {
    "и",
    "в",
    "во",
    "не",
    "что",
    "он",
    "на",
    "я",
    "с",
    "со",
    "как",
    "а",
    "то",
    "все",
    "она",
    "так",
    "его",
    "но",
    "да",
    "ты",
    "к",
    "у",
    "же",
    "вы",
    "за",
    "бы",
    "по",
    "только",
    "ее",
    "мне",
    "было",
    "вот",
    "от",
    "меня",
    "еще",
    "нет",
    "о",
    "из",
    "ему",
    "теперь",
    "когда",
    "даже",
    "ну",
    "вдруг",
    "ли",
    "если",
    "уже",
    "или",
    "ни",
    "быть",
    "был",
    "него",
    "до",
    "вас",
    "нибудь",
    "опять",
    "уж",
    "вам",
    "ведь",
    "там",
    "потом",
    "себя",
    "ничего",
    "ей",
    "может",
    "они",
    "тут",
    "где",
    "есть",
    "надо",
    "ней",
    "для",
    "мы",
    "тебя",
    "их",
    "при",
    "эти",
    "чем",
    "после",
    "этого",
    "также",
    "сказал",
    "говорит",
    "очень",
    "просто",
    "это",
}

EN_STOP_WORDS: set[str] = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "up",
    "about",
    "into",
    "over",
    "after",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "shall",
    "should",
    "may",
    "might",
    "must",
    "can",
    "could",
    "this",
    "that",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "their",
    "our",
    "its",
    "just",
    "like",
    "also",
    "know",
    "think",
}


class LocalDynamicSummarizer:
    """Dynamic local extractive summarizer operating on raw transcript text."""

    @staticmethod
    def split_into_sentences(text: str) -> list[str]:
        """Splits transcript text into clean, non-empty sentences."""
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        cleaned: list[str] = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) > 5 and len(s_clean.split()) >= 2:
                cleaned.append(s_clean)
        return cleaned

    @classmethod
    def extract_title(cls, sentences: list[str], is_russian: bool) -> str:
        """Extracts a concise auto-generated topic/title for the conversation."""
        if not sentences:
            return "Обсуждение встречи" if is_russian else "Meeting Discussion"

        stop_words = RU_STOP_WORDS if is_russian else EN_STOP_WORDS
        spk_regex = r"^[\[\(]?(SPEAKER_\d+|[A-ZА-Я][a-zа-я]+)[\]\)]?:\s*"
        clean_first = re.sub(spk_regex, "", sentences[0], flags=re.IGNORECASE).strip()

        words = [
            w for w in re.findall(r"\w+", clean_first) if w.lower() not in stop_words and len(w) > 2
        ]
        if len(words) >= 2:
            title_words = words[:6]
            raw_title = " ".join(title_words).capitalize()
            return f"Обсуждение: {raw_title}" if is_russian else f"Discussion: {raw_title}"

        if len(clean_first) > 40:
            return clean_first[:40].strip() + "..."
        return clean_first or ("Обсуждение встречи" if is_russian else "Meeting Discussion")

    @classmethod
    def extract_summary(cls, sentences: list[str], is_russian: bool, max_sentences: int = 3) -> str:
        """Extracts top representative sentences as an executive summary."""
        if not sentences:
            return (
                "Разговорная речь не содержит достаточно ключевых тезисов."
                if is_russian
                else "Transcript does not contain enough key statements."
            )

        if len(sentences) <= max_sentences:
            return " ".join(sentences)

        stop_words = RU_STOP_WORDS if is_russian else EN_STOP_WORDS
        words = re.findall(r"\w+", " ".join(sentences).lower())
        meaningful_words = [w for w in words if len(w) > 3 and w not in stop_words]

        if not meaningful_words:
            return " ".join(sentences[:max_sentences])

        word_counts = Counter(meaningful_words)
        scored_sentences: list[tuple[float, int, str]] = []

        for idx, sentence in enumerate(sentences):
            s_words = re.findall(r"\w+", sentence.lower())
            score = sum(word_counts[w] for w in s_words if w in word_counts)
            position_mult = 1.2 if idx < 2 or idx >= len(sentences) - 2 else 1.0
            length_penalty = 1.0 if 5 <= len(s_words) <= 30 else 0.8
            denom = math.sqrt(len(s_words) + 1)
            final_score = (score / denom) * position_mult * length_penalty
            scored_sentences.append((final_score, idx, sentence))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentences = sorted(scored_sentences[:max_sentences], key=lambda x: x[1])

        return " ".join([s[2] for s in top_sentences])

    @classmethod
    def extract_decisions(cls, sentences: list[str], is_russian: bool) -> list[str]:
        """Identifies decision-like statements from transcript sentences."""
        ru_patterns = [
            r"\b(решил|решили|согласовал|согласовали|утвердил|утвердили|постановили)\b",
            r"\b(договорились|принято решение|согласен|планируем|будем использовать)\b",
        ]
        en_patterns = [
            r"\b(decided|agreed|approved|resolved|concluded|confirmed)\b",
            r"\b(will proceed|moving forward with|settled on)\b",
        ]

        patterns = ru_patterns if is_russian else en_patterns
        decisions: list[str] = []

        spk_regex = r"^[\[\(]?SPEAKER_\d+[\]\)]?:\s*"
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(re.search(pat, sentence_lower) for pat in patterns):
                cleaned = re.sub(spk_regex, "", sentence, flags=re.IGNORECASE)
                if cleaned not in decisions:
                    decisions.append(cleaned)

        if not decisions and sentences:
            for sentence in sentences:
                cleaned = re.sub(spk_regex, "", sentence, flags=re.IGNORECASE)
                if len(cleaned.split()) >= 4:
                    prefix = "Обсуждение: " if is_russian else "Discussed: "
                    decisions.append(f"{prefix}{cleaned}")
                    if len(decisions) >= 2:
                        break

        if not decisions:
            decisions = [
                "Основные решения согласованы в ходе обсуждения."
                if is_russian
                else "Core decisions agreed during discussion."
            ]

        return decisions[:4]

    @classmethod
    def extract_action_items(cls, sentences: list[str], is_russian: bool) -> list[ActionItem]:
        """Extracts actionable tasks, owners, priorities, and deadlines."""
        ru_action_patterns = [
            r"\b(нужно|необходимо|следует|задача|надо|сделать|подготовить|проверить|разработать)\b"
        ]
        en_action_patterns = [
            r"\b(need to|must|should|action item|todo|will create|will implement|take care of)\b"
        ]

        patterns = ru_action_patterns if is_russian else en_action_patterns
        action_items: list[ActionItem] = []
        spk_regex = r"^[\[\(]?SPEAKER_\d+[\]\)]?:\s*"

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(re.search(pat, sentence_lower) for pat in patterns):
                spk_match = re.search(
                    r"^[\[\(]?(SPEAKER_\d+|[A-ZА-Я][a-zа-я]+)[\]\)]?:\s*", sentence
                )
                owner = spk_match.group(1) if spk_match else None
                task_text = re.sub(spk_regex, "", sentence, flags=re.IGNORECASE).strip()

                priority = "MEDIUM"
                if re.search(r"\b(срочно|критично|важно|high|urgent|asap)\b", sentence_lower):
                    priority = "HIGH"
                elif re.search(r"\b(по возможности|низкий|low|minor)\b", sentence_lower):
                    priority = "LOW"

                date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", sentence)
                due_date = date_match.group(1) if date_match else None

                action_items.append(
                    ActionItem(
                        task=task_text[:200],
                        owner=owner,
                        due_date=due_date,
                        priority=priority,
                    )
                )

        if not action_items and sentences:
            action_items = [
                ActionItem(
                    task="Провести дополнительную проверку вопросов встречи"
                    if is_russian
                    else "Review meeting key follow-up points",
                    owner=None,
                    due_date=None,
                    priority="MEDIUM",
                )
            ]

        return action_items[:5]

    @classmethod
    def analyze_sentiment(cls, text: str, is_russian: bool) -> str:
        """Determines overall conversation sentiment based on keyword density."""
        ru_pos = {
            "отлично",
            "успешно",
            "хорошо",
            "замечательно",
            "согласен",
            "плюс",
            "успех",
            "готово",
        }
        ru_neg = {
            "проблема",
            "ошибка",
            "сбой",
            "задержка",
            "риск",
            "плохо",
            "неудача",
            "минус",
            "сложно",
        }

        en_pos = {
            "great",
            "good",
            "excellent",
            "success",
            "approved",
            "positive",
            "awesome",
            "done",
        }
        en_neg = {
            "issue",
            "error",
            "failed",
            "risk",
            "problem",
            "delay",
            "bad",
            "difficult",
            "blocker",
        }

        pos_set = ru_pos if is_russian else en_pos
        neg_set = ru_neg if is_russian else en_neg

        words = set(re.findall(r"\w+", text.lower()))
        pos_count = len(words.intersection(pos_set))
        neg_count = len(words.intersection(neg_set))

        if pos_count > neg_count:
            return "POSITIVE"
        if neg_count > pos_count:
            return "NEGATIVE"
        return "NEUTRAL"


class LLMIntelligenceEngine:
    """Production-ready AI summarization and executive intelligence extraction engine."""

    MAX_CHUNK_CHARS: int = 8000

    async def extract_intelligence(
        self, full_transcript_text: str, language: str = "auto"
    ) -> ConversationAnalysis:
        """Processes raw transcript text and returns structured executive intelligence."""
        if not full_transcript_text or not full_transcript_text.strip():
            logger.info("Received empty transcript text. Returning minimal default analysis.")
            return ConversationAnalysis(
                title="Пустая запись" if language == "ru" else "Empty Record",
                executive_summary=(
                    "Разговорная речь отсутствует или аудиозапись не содержит текста."
                    if language == "ru"
                    else "No speech transcript content available to summarize."
                ),
                key_decisions=[],
                action_items=[],
                overall_sentiment="NEUTRAL",
            )

        cleaned_text = full_transcript_text.strip()
        is_russian = language == "ru" or bool(re.search(r"[\u0400-\u04FF]", cleaned_text))

        if len(cleaned_text.split()) < 10:
            logger.info("Short transcript provided. Generating lightweight summary.")
            return self._run_local_dynamic_summarizer(cleaned_text, is_russian)

        processed_text = await self._prepare_transcript_text(cleaned_text)

        if settings.LLM_API_KEY and settings.LLM_API_KEY.lower() not in ("mock-key", "", "none"):
            try:
                analysis = await self._call_llm_api(processed_text, is_russian)
                if analysis:
                    return analysis
            except Exception as e:
                logger.warning(
                    f"External LLM API call failed ({e!s}). "
                    "Falling back to dynamic local summarizer."
                )

        return self._run_local_dynamic_summarizer(processed_text, is_russian)

    async def _prepare_transcript_text(self, text: str) -> str:
        """Chunks long transcripts asynchronously to fit context windows."""
        if len(text) <= self.MAX_CHUNK_CHARS:
            return text

        logger.info(f"Transcript length ({len(text)} chars) exceeds threshold. Chunking...")
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        sentences = LocalDynamicSummarizer.split_into_sentences(text)
        for sentence in sentences:
            if current_len + len(sentence) > self.MAX_CHUNK_CHARS:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_len = len(sentence)
            else:
                current_chunk.append(sentence)
                current_len += len(sentence)
            await asyncio.sleep(0)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        condensed_parts: list[str] = []
        is_russian = bool(re.search(r"[\u0400-\u04FF]", text))
        for chunk in chunks:
            sentences_in_chunk = LocalDynamicSummarizer.split_into_sentences(chunk)
            summary_part = LocalDynamicSummarizer.extract_summary(
                sentences_in_chunk, is_russian, max_sentences=2
            )
            condensed_parts.append(summary_part)
            await asyncio.sleep(0)

        return " ".join(condensed_parts)

    async def _call_llm_api(self, text: str, is_russian: bool) -> ConversationAnalysis | None:
        """Calls external OpenAI-compatible API to generate structured meeting intelligence."""
        import httpx

        system_prompt = (
            "You are an executive meeting analyst. Analyze the meeting transcript "
            "and output strictly a valid JSON object matching this schema:\n"
            "{\n"
            '  "title": "Concise descriptive topic/title for the transcript (3-7 words)",\n'
            '  "executive_summary": "Concise summary (2-4 sentences)",\n'
            '  "key_decisions": ["Decision 1", "Decision 2"],\n'
            '  "action_items": [\n'
            '    {"task": "Task", "owner": "Name/null", "due_date": "YYYY-MM-DD/null", '
            '"priority": "HIGH|MEDIUM|LOW"}\n'
            "  ],\n"
            '  "overall_sentiment": "POSITIVE|NEUTRAL|NEGATIVE"\n'
            "}\n"
            "Do not include any text outside the JSON object."
        )

        user_prompt = (
            f"Язык ответа: {'Русский' if is_russian else 'English'}\n\nСтенограмма встречи:\n{text}"
        )

        headers = {
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": settings.LLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code != 200:
                    payload.pop("response_format", None)
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )

                if response.status_code != 200:
                    raise LLMServiceError(f"HTTP error {response.status_code}: {response.text}")

                data = response.json()
                raw_content = data["choices"][0]["message"]["content"]
                return self._parse_json_response(raw_content, is_russian)

            except httpx.HTTPError as err:
                raise LLMServiceError(f"Network error during LLM request: {err!s}") from err

    def _parse_json_response(self, content: str, is_russian: bool) -> ConversationAnalysis:
        """Parses and validates LLM raw response content into structured ConversationAnalysis."""
        clean_json = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
        clean_json = re.sub(r"\s*```$", "", clean_json)

        try:
            data: dict[str, Any] = json.loads(clean_json)
        except json.JSONDecodeError:
            logger.warning("Failed to decode JSON from LLM output. Returning fallback parser.")
            return self._run_local_dynamic_summarizer(content, is_russian)

        raw_title = data.get("title")
        if raw_title and str(raw_title).strip():
            title = str(raw_title).strip()
        else:
            sentences = LocalDynamicSummarizer.split_into_sentences(content)
            title = LocalDynamicSummarizer.extract_title(sentences, is_russian)

        summary = data.get("executive_summary") or (
            "Резюме встречи сформировано." if is_russian else "Meeting summary generated."
        )
        raw_decisions = data.get("key_decisions")
        decisions_list: list[Any] = raw_decisions if isinstance(raw_decisions, list) else []
        sentiment = str(data.get("overall_sentiment", "NEUTRAL")).upper()
        if sentiment not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
            sentiment = "NEUTRAL"

        action_items: list[ActionItem] = []
        raw_items = data.get("action_items")
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict) and "task" in item:
                    prio = str(item.get("priority", "MEDIUM")).upper()
                    if prio not in ("HIGH", "MEDIUM", "LOW"):
                        prio = "MEDIUM"
                    action_items.append(
                        ActionItem(
                            task=str(item["task"]),
                            owner=str(item["owner"]) if item.get("owner") else None,
                            due_date=str(item["due_date"]) if item.get("due_date") else None,
                            priority=prio,
                        )
                    )

        return ConversationAnalysis(
            title=title,
            executive_summary=str(summary),
            key_decisions=[str(d) for d in decisions_list],
            action_items=action_items,
            overall_sentiment=sentiment,
        )

    def _run_local_dynamic_summarizer(self, text: str, is_russian: bool) -> ConversationAnalysis:
        """Runs the dynamic local extractive summarizer on actual transcript content."""
        sentences = LocalDynamicSummarizer.split_into_sentences(text)
        title = LocalDynamicSummarizer.extract_title(sentences, is_russian)
        summary = LocalDynamicSummarizer.extract_summary(sentences, is_russian)
        decisions = LocalDynamicSummarizer.extract_decisions(sentences, is_russian)
        action_items = LocalDynamicSummarizer.extract_action_items(sentences, is_russian)
        sentiment = LocalDynamicSummarizer.analyze_sentiment(text, is_russian)

        return ConversationAnalysis(
            title=title,
            executive_summary=summary,
            key_decisions=decisions,
            action_items=action_items,
            overall_sentiment=sentiment,
        )
