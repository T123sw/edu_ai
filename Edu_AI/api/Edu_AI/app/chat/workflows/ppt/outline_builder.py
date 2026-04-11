from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable

from app.chat.domain.ppt_outline import PptOutline, PptOutlineChapter, PptOutlineSlide


class PptOutlineBuilder:
    _SUPPORTED_THEME_IDS = {"heu_academic_elegant", "heu_academic_basic"}
    _DEFAULT_THEME_ID = "heu_academic_elegant"
    _SOFT_TARGET_SLIDE_COUNT = 18
    _MAX_FALLBACK_TOTAL_SLIDES = 15

    def __init__(self, llm=None):
        self.llm = llm

    @staticmethod
    def _clean(value: object, default: str = "") -> str:
        text = str(value or "").strip()
        return text or default

    @staticmethod
    def _normalize_text(value: object) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[\s\u3000]+", "", text)
        text = re.sub(r"[，。、“”‘’：:；;,.!?！？（）()\-\[\]【】{}]", "", text)
        return text

    @classmethod
    def _normalize_key_points(cls, values: Iterable[object], *, fallback: str) -> list[str]:
        points: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = cls._clean(item)
            key = cls._normalize_text(text)
            if text and key and key not in seen:
                points.append(text)
                seen.add(key)
        if not points:
            return [fallback]
        return points

    @classmethod
    def _normalize_theme_id(cls, value: object) -> str:
        text = str(value or "").strip()
        if text in cls._SUPPORTED_THEME_IDS:
            return text
        return cls._DEFAULT_THEME_ID

    @staticmethod
    def _parse_int(value: object) -> int | None:
        try:
            text = str(value or "").strip()
            return int(text) if text else None
        except Exception:
            return None

    @classmethod
    def _explicit_slide_count(cls, preparation) -> int | None:
        return cls._parse_int(getattr(preparation, "slide_count", None))

    @classmethod
    def _preferred_slide_count(cls, preparation) -> int:
        return cls._explicit_slide_count(preparation) or cls._SOFT_TARGET_SLIDE_COUNT

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        raw_text = getattr(response, "content", response)
        if isinstance(raw_text, str):
            return raw_text.strip()
        if isinstance(raw_text, list):
            parts: list[str] = []
            for item in raw_text:
                if isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                else:
                    text = str(item or "").strip()
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        return str(raw_text or "").strip()

    @staticmethod
    def _extract_json_object(text: str) -> str:
        normalized = str(text or "").strip()
        normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.I)
        normalized = re.sub(r"\s*```$", "", normalized)
        match = re.search(r"\{.*\}", normalized, re.S)
        return match.group(0) if match else normalized

    @classmethod
    def _parse_llm_outline(cls, response: Any) -> PptOutline | None:
        text = cls._extract_response_text(response)
        if not text:
            return None
        try:
            payload = json.loads(cls._extract_json_object(text))
        except Exception:
            return None
        try:
            return PptOutline.model_validate(payload)
        except Exception:
            return None

    @staticmethod
    def _chunk_slides(slides: list[PptOutlineSlide]) -> list[list[PptOutlineSlide]]:
        if len(slides) <= 3:
            return [slides]
        if len(slides) <= 8:
            midpoint = math.ceil(len(slides) / 2)
            return [slides[:midpoint], slides[midpoint:]]
        if len(slides) <= 12:
            chunk_size = math.ceil(len(slides) / 3)
        else:
            chunk_size = math.ceil(len(slides) / 4)
        groups: list[list[PptOutlineSlide]] = []
        for index in range(0, len(slides), chunk_size):
            groups.append(slides[index:index + chunk_size])
        return groups

    @staticmethod
    def _build_default_goal(*, deck_topic: str, point: str) -> str:
        return f"Explain {point} clearly and connect it to the overall topic {deck_topic}."

    @classmethod
    def _build_fallback_content_slide(cls, *, slide_index: int, deck_topic: str, point: str) -> PptOutlineSlide:
        return PptOutlineSlide(
            slide_index=slide_index,
            role="content",
            title=point,
            goal=cls._build_default_goal(deck_topic=deck_topic, point=point),
            key_points=cls._normalize_key_points([point], fallback=point),
        )

    @classmethod
    def _fallback_total_slides(cls, *, key_points: list[str]) -> int:
        return min(len(list(key_points or [])) + 3, cls._MAX_FALLBACK_TOTAL_SLIDES)

    @classmethod
    def _build_generated_chapter_title(
        cls,
        *,
        slides: list[PptOutlineSlide],
        used_title_keys: set[str],
    ) -> str:
        if not slides:
            return "Section"
        base = slides[0].title if len(slides) == 1 else f"{slides[0].title} to {slides[-1].title}"
        title = base
        suffix = 2
        while cls._normalize_text(title) in used_title_keys:
            title = f"{base} ({suffix})"
            suffix += 1
        return title

    @classmethod
    def _build_generated_chapters_from_slides(
        cls,
        *,
        content_slides: list[PptOutlineSlide],
        deck_topic: str,
        start_index: int = 1,
        used_title_keys: set[str] | None = None,
    ) -> list[PptOutlineChapter]:
        groups = [group for group in cls._chunk_slides(content_slides) if group]
        seen = set(used_title_keys or set())
        chapters: list[PptOutlineChapter] = []
        for offset, group in enumerate(groups, start=start_index):
            chapter_title = cls._build_generated_chapter_title(slides=group, used_title_keys=seen)
            seen.add(cls._normalize_text(chapter_title))
            chapter_goal = (
                f"Use this section to deepen understanding of {deck_topic} through "
                f"{group[0].title.lower()} and related teaching points."
            )
            chapters.append(
                PptOutlineChapter(
                    chapter_index=offset,
                    chapter_title=chapter_title,
                    chapter_goal=chapter_goal,
                    slides=group,
                )
            )
        return chapters

    @classmethod
    def _build_fallback_outline(
        cls,
        *,
        preparation,
        deck_topic: str,
        audience: str,
        objective: str,
        key_points: list[str],
    ) -> PptOutline:
        fallback_points = list(key_points[: max(cls._fallback_total_slides(key_points=key_points) - 3, 1)])
        content_slides = [
            cls._build_fallback_content_slide(
                slide_index=index,
                deck_topic=deck_topic,
                point=point,
            )
            for index, point in enumerate(fallback_points, start=3)
        ]
        chapters = cls._build_generated_chapters_from_slides(
            content_slides=content_slides,
            deck_topic=deck_topic,
        )
        slides: list[PptOutlineSlide] = [
            PptOutlineSlide(
                slide_index=1,
                role="cover",
                title=deck_topic,
                goal=objective,
                key_points=cls._normalize_key_points([objective, audience], fallback=objective),
            ),
            PptOutlineSlide(
                slide_index=2,
                role="toc",
                title="Agenda",
                goal="Show the teaching structure and progression of the deck.",
                key_points=[chapter.chapter_title for chapter in chapters],
            ),
            *content_slides,
            PptOutlineSlide(
                slide_index=len(content_slides) + 3,
                role="thanks",
                title="Q&A",
                goal="Wrap up the lesson and invite questions.",
                key_points=cls._normalize_key_points(["Questions", audience], fallback="Questions"),
            ),
        ]
        return PptOutline(
            deck_title=deck_topic,
            deck_subtitle=f"For {audience}",
            theme_id=cls._normalize_theme_id(getattr(preparation, "theme_id", None)),
            confirmation_status="pending",
            chapters=chapters,
            slides=slides,
        )

    def _build_llm_prompt(self, *, preparation, key_points: list[str]) -> str:
        deck_topic = self._clean(getattr(preparation, "deck_topic", None), "PPT")
        audience = self._clean(getattr(preparation, "audience", None), "general learners")
        objective = self._clean(getattr(preparation, "objective", None), "classroom teaching")
        preferred_slide_count = self._preferred_slide_count(preparation)
        has_explicit_count = self._explicit_slide_count(preparation) is not None
        source_basis = " | ".join(self._normalize_key_points(getattr(preparation, "source_basis", []) or [], fallback="conversation")) or "conversation"
        source_excerpts = " | ".join(
            self._normalize_key_points(getattr(preparation, "source_excerpts", []) or [], fallback="not provided")
        )

        return (
            "You are an expert instructional designer for Chinese teaching decks.\n"
            "Generate a complete PPT outline and return JSON only that matches the PptOutline schema.\n"
            "The outline should contain deck_title, deck_subtitle, theme_id, confirmation_status, chapters, and slides.\n"
            "Each slide must include slide_index, role, title, goal, and key_points.\n"
            "Allowed roles are: cover, toc, content, thanks.\n"
            "This is not a short summary. Build a substantial teaching deck rather than a brief recap.\n"
            "You may extend the provided context with essential background, mechanisms, examples, misconceptions, comparisons, boundaries, applications, and teaching takeaways when they help learners understand the topic.\n"
            "Any extension must stay faithful to the topic and grounded source material. Do not invent fake citations or overly specific unsupported facts.\n"
            "Every chapter_title must be unique. Every content slide title must be unique.\n"
            "Do not pad the deck with repetitive rephrasings of the same point.\n"
            "Prefer a teaching progression such as orientation -> concepts -> mechanisms -> examples/applications -> misconceptions/boundaries -> synthesis.\n"
            "Each content slide should have a clear teaching purpose and 2-4 concrete key points.\n"
            + (
                f"Treat {preferred_slide_count} slides as a strong user preference.\n"
                if has_explicit_count
                else "When the topic supports it, aim for a full deck that usually lands around 15-20+ slides overall, not a 5-slide summary.\n"
            )
            + f"Topic: {deck_topic}\n"
            + f"Audience: {audience}\n"
            + f"Objective: {objective}\n"
            + f"Preferred total slides: {preferred_slide_count}\n"
            + f"Seed key points: {' | '.join(key_points)}\n"
            + f"Source basis: {source_basis}\n"
            + f"Grounded source excerpts: {source_excerpts}\n"
        )

    @classmethod
    def _flatten_candidate_content_slides(cls, parsed: PptOutline) -> list[PptOutlineSlide]:
        slides = [slide for slide in list(parsed.slides or []) if cls._clean(slide.role).lower() == "content"]
        if slides:
            return slides
        flattened: list[PptOutlineSlide] = []
        for chapter in list(parsed.chapters or []):
            for slide in list(chapter.slides or []):
                if cls._clean(slide.role).lower() == "content":
                    flattened.append(slide)
        return flattened

    @classmethod
    def _sanitize_content_slides(
        cls,
        *,
        parsed: PptOutline,
        deck_topic: str,
        seed_key_points: list[str],
    ) -> list[PptOutlineSlide]:
        content_slides: list[PptOutlineSlide] = []
        seen_titles: set[str] = set()
        for raw_slide in cls._flatten_candidate_content_slides(parsed):
            title = cls._clean(raw_slide.title)
            goal = cls._clean(raw_slide.goal)
            normalized_title = cls._normalize_text(title)
            if not title or not goal or not normalized_title:
                continue
            if normalized_title == cls._normalize_text(deck_topic):
                continue
            if normalized_title in seen_titles:
                continue
            slide = PptOutlineSlide(
                slide_index=0,
                role="content",
                title=title,
                goal=goal,
                key_points=cls._normalize_key_points(raw_slide.key_points or [], fallback=title)[:4],
                presenter_notes=cls._clean(raw_slide.presenter_notes) or None,
            )
            content_slides.append(slide)
            seen_titles.add(normalized_title)

        minimum_expected = max(3, min(4, len(seed_key_points or [])))
        if len(content_slides) < minimum_expected:
            return []
        return content_slides

    @classmethod
    def _pick_first_slide_by_role(cls, slides: list[PptOutlineSlide], role: str) -> PptOutlineSlide | None:
        for slide in slides:
            if cls._clean(slide.role).lower() == role:
                return slide
        return None

    @classmethod
    def _build_chapters_from_parsed_outline(
        cls,
        *,
        parsed: PptOutline,
        ordered_content_slides: list[PptOutlineSlide],
        deck_topic: str,
    ) -> list[PptOutlineChapter]:
        lookup = {cls._normalize_text(slide.title): slide for slide in ordered_content_slides}
        assigned: set[str] = set()
        used_chapter_titles: set[str] = set()
        chapters: list[PptOutlineChapter] = []

        for raw_chapter in list(parsed.chapters or []):
            chapter_title = cls._clean(raw_chapter.chapter_title)
            chapter_goal = cls._clean(raw_chapter.chapter_goal)
            chapter_key = cls._normalize_text(chapter_title)
            if not chapter_title or not chapter_key or chapter_key in used_chapter_titles:
                continue
            matched_slides: list[PptOutlineSlide] = []
            for raw_slide in list(raw_chapter.slides or []):
                slide_key = cls._normalize_text(raw_slide.title)
                slide = lookup.get(slide_key)
                if slide is None or slide_key in assigned:
                    continue
                matched_slides.append(slide)
                assigned.add(slide_key)
            if not matched_slides:
                continue
            used_chapter_titles.add(chapter_key)
            chapters.append(
                PptOutlineChapter(
                    chapter_index=len(chapters) + 1,
                    chapter_title=chapter_title,
                    chapter_goal=chapter_goal or f"Deepen understanding of {deck_topic} in this section.",
                    slides=matched_slides,
                )
            )

        remaining_slides = [
            slide for slide in ordered_content_slides
            if cls._normalize_text(slide.title) not in assigned
        ]
        if remaining_slides:
            chapters.extend(
                cls._build_generated_chapters_from_slides(
                    content_slides=remaining_slides,
                    deck_topic=deck_topic,
                    start_index=len(chapters) + 1,
                    used_title_keys=used_chapter_titles,
                )
            )

        return chapters or cls._build_generated_chapters_from_slides(
            content_slides=ordered_content_slides,
            deck_topic=deck_topic,
        )

    def _sanitize_outline(
        self,
        *,
        parsed: PptOutline,
        preparation,
        deck_topic: str,
        audience: str,
        objective: str,
        key_points: list[str],
    ) -> PptOutline | None:
        content_slides = self._sanitize_content_slides(
            parsed=parsed,
            deck_topic=deck_topic,
            seed_key_points=key_points,
        )
        if not content_slides:
            return None

        chapters = self._build_chapters_from_parsed_outline(
            parsed=parsed,
            ordered_content_slides=content_slides,
            deck_topic=deck_topic,
        )

        reindexed_content_lookup: dict[str, PptOutlineSlide] = {}
        reindexed_content_slides: list[PptOutlineSlide] = []
        for index, slide in enumerate(content_slides, start=3):
            normalized = slide.model_copy(update={"slide_index": index})
            reindexed_content_slides.append(normalized)
            reindexed_content_lookup[self._normalize_text(slide.title)] = normalized

        reindexed_chapters: list[PptOutlineChapter] = []
        for chapter_index, chapter in enumerate(chapters, start=1):
            chapter_slides = [
                reindexed_content_lookup[self._normalize_text(slide.title)]
                for slide in list(chapter.slides or [])
                if self._normalize_text(slide.title) in reindexed_content_lookup
            ]
            if not chapter_slides:
                continue
            reindexed_chapters.append(
                PptOutlineChapter(
                    chapter_index=chapter_index,
                    chapter_title=self._clean(chapter.chapter_title, chapter_slides[0].title),
                    chapter_goal=self._clean(
                        chapter.chapter_goal,
                        f"Deepen understanding of {deck_topic} in this section.",
                    ),
                    slides=chapter_slides,
                )
            )

        raw_slides = list(parsed.slides or [])
        cover = self._pick_first_slide_by_role(raw_slides, "cover") or PptOutlineSlide(
            slide_index=1,
            role="cover",
            title=deck_topic,
            goal=objective,
            key_points=[objective, audience],
        )
        toc = self._pick_first_slide_by_role(raw_slides, "toc") or PptOutlineSlide(
            slide_index=2,
            role="toc",
            title="Agenda",
            goal="Show the teaching structure and progression of the deck.",
            key_points=[],
        )
        thanks = self._pick_first_slide_by_role(raw_slides, "thanks") or PptOutlineSlide(
            slide_index=len(reindexed_content_slides) + 3,
            role="thanks",
            title="Q&A",
            goal="Wrap up the lesson and invite questions.",
            key_points=["Questions", audience],
        )

        slides: list[PptOutlineSlide] = [
            PptOutlineSlide(
                slide_index=1,
                role="cover",
                title=self._clean(cover.title, deck_topic),
                goal=self._clean(cover.goal, objective),
                key_points=self._normalize_key_points(cover.key_points or [objective, audience], fallback=objective),
                presenter_notes=self._clean(cover.presenter_notes) or None,
            ),
            PptOutlineSlide(
                slide_index=2,
                role="toc",
                title=self._clean(toc.title, "Agenda"),
                goal=self._clean(toc.goal, "Show the teaching structure and progression of the deck."),
                key_points=[chapter.chapter_title for chapter in reindexed_chapters],
                presenter_notes=self._clean(toc.presenter_notes) or None,
            ),
            *reindexed_content_slides,
            PptOutlineSlide(
                slide_index=len(reindexed_content_slides) + 3,
                role="thanks",
                title=self._clean(thanks.title, "Q&A"),
                goal=self._clean(thanks.goal, "Wrap up the lesson and invite questions."),
                key_points=self._normalize_key_points(thanks.key_points or ["Questions", audience], fallback="Questions"),
                presenter_notes=self._clean(thanks.presenter_notes) or None,
            ),
        ]

        return PptOutline(
            deck_title=self._clean(parsed.deck_title, deck_topic),
            deck_subtitle=self._clean(parsed.deck_subtitle, f"For {audience}"),
            theme_id=self._normalize_theme_id(parsed.theme_id or getattr(preparation, "theme_id", None)),
            confirmation_status=self._clean(parsed.confirmation_status, "pending"),
            chapters=reindexed_chapters,
            slides=slides,
        )

    def build(self, *, preparation) -> PptOutline:
        deck_topic = self._clean(getattr(preparation, "deck_topic", None), "PPT")
        audience = self._clean(getattr(preparation, "audience", None), "general learners")
        objective = self._clean(getattr(preparation, "objective", None), "classroom teaching")
        key_points = self._normalize_key_points(
            list(getattr(preparation, "key_points", []) or []),
            fallback=deck_topic,
        )

        if self.llm is not None:
            prompt = self._build_llm_prompt(preparation=preparation, key_points=key_points)
            try:
                response = self.llm.invoke(prompt)
            except Exception:
                response = None
            parsed = self._parse_llm_outline(response)
            if parsed is not None:
                sanitized = self._sanitize_outline(
                    parsed=parsed,
                    preparation=preparation,
                    deck_topic=deck_topic,
                    audience=audience,
                    objective=objective,
                    key_points=key_points,
                )
                if sanitized is not None:
                    return sanitized

        return self._build_fallback_outline(
            preparation=preparation,
            deck_topic=deck_topic,
            audience=audience,
            objective=objective,
            key_points=key_points,
        )
