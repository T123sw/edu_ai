"""Bounded, structure-aware Markdown chunking for the shared RAG pipeline.

The implementation intentionally depends only on ``markdown-it-py`` and a
small token counter. It does not load document vision/OCR models. PDF, DOCX,
web and user-upload flows all reach this chunker after their format adapter has
produced Markdown-like content.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from typing import Iterable, Sequence

from markdown_it import MarkdownIt

try:
    import tiktoken
except ImportError:  # pragma: no cover - production requirements include it
    tiktoken = None


CHUNKER_VERSION = "structural-parent-child-v1"
_SPECIAL_KINDS = {"code", "formula", "table", "image", "video", "callout"}
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;])|\n{2,}")
_IMAGE_ONLY = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$", re.DOTALL)
_VIDEO_MARKDOWN = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\.(?:mp4|webm|mov)(?:\?[^)]*)?\)\s*$", re.I | re.DOTALL)
_CALLOUT = re.compile(r"^\s*!!!\s+", re.MULTILINE)


class ApproximateTokenCounter:
    """Conservative local token counter used for deterministic chunk limits.

    Gemini does not expose a local tokenizer through the OpenAI-compatible
    gateway. ``cl100k_base`` is used as a stable estimator; when unavailable,
    the fallback intentionally overestimates CJK text instead of risking an
    oversized request. The actual embedding request is never truncated.
    """

    def __init__(self) -> None:
        self._encoding = tiktoken.get_encoding("cl100k_base") if tiktoken else None

    def count(self, text: str) -> int:
        value = str(text or "")
        if not value:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(value, disallowed_special=()))
        cjk = len(re.findall(r"[\u3400-\u9fff]", value))
        non_cjk = len(value) - cjk
        return cjk + max(1, (non_cjk + 2) // 3)


@dataclass(frozen=True)
class ContentBlock:
    kind: str
    markdown: str
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ParentChunk:
    parent_id: str
    display_content: str
    heading_path: tuple[str, ...]
    child_ids: tuple[str, ...]
    token_count: int


@dataclass(frozen=True)
class StructuralChunk:
    chunk_id: str
    parent_id: str
    kind: str
    display_content: str
    embedding_text: str
    heading_path: tuple[str, ...]
    token_count: int
    start_line: int
    end_line: int
    previous_id: str | None = None
    next_id: str | None = None


@dataclass(frozen=True)
class ChunkingResult:
    parents: tuple[ParentChunk, ...] = field(default_factory=tuple)
    children: tuple[StructuralChunk, ...] = field(default_factory=tuple)
    chunker_version: str = CHUNKER_VERSION


class StructuralChunker:
    def __init__(
        self,
        *,
        child_target_tokens: int = 500,
        child_max_tokens: int = 800,
        parent_target_tokens: int = 1600,
        parent_max_tokens: int = 2400,
        minimum_child_tokens: int = 80,
        token_counter: ApproximateTokenCounter | None = None,
    ) -> None:
        if not 0 < child_target_tokens <= child_max_tokens:
            raise ValueError("child token limits are invalid")
        if not child_max_tokens <= parent_max_tokens:
            raise ValueError("parent_max_tokens must be >= child_max_tokens")
        self.child_target_tokens = int(child_target_tokens)
        self.child_max_tokens = int(child_max_tokens)
        self.parent_target_tokens = max(int(parent_target_tokens), self.child_max_tokens)
        self.parent_max_tokens = max(int(parent_max_tokens), self.parent_target_tokens)
        self.minimum_child_tokens = max(1, int(minimum_child_tokens))
        self.counter = token_counter or ApproximateTokenCounter()
        self._markdown = MarkdownIt("commonmark", {"html": False}).enable("table")

    def chunk_markdown(
        self,
        markdown: str,
        *,
        document_id: str,
        document_title: str,
    ) -> ChunkingResult:
        blocks = self._parse_blocks(str(markdown or ""))
        if not blocks:
            return ChunkingResult()

        drafts: list[StructuralChunk] = []
        for heading_path, section_blocks in self._group_sections(blocks):
            drafts.extend(
                self._chunk_section(
                    section_blocks,
                    heading_path=heading_path,
                    document_id=document_id,
                    document_title=document_title,
                )
            )

        drafts = self._merge_tiny_neighbors(
            drafts,
            document_id=document_id,
            document_title=document_title,
        )
        parents, children = self._build_parents(
            drafts,
            document_id=document_id,
        )
        linked = tuple(
            replace(
                chunk,
                previous_id=children[index - 1].chunk_id if index else None,
                next_id=children[index + 1].chunk_id if index + 1 < len(children) else None,
            )
            for index, chunk in enumerate(children)
        )
        return ChunkingResult(parents=parents, children=linked)

    def _parse_blocks(self, markdown: str) -> list[ContentBlock]:
        lines = markdown.splitlines()
        tokens = self._markdown.parse(markdown)
        headings: list[str] = []
        blocks: list[ContentBlock] = []
        used_spans: set[tuple[int, int]] = set()

        for index, token in enumerate(tokens):
            if token.level != 0 or token.map is None:
                continue
            start, end = int(token.map[0]), int(token.map[1])
            if token.type == "heading_open":
                level = int(token.tag[1:]) if token.tag.startswith("h") else 1
                title = ""
                if index + 1 < len(tokens) and tokens[index + 1].type == "inline":
                    title = str(tokens[index + 1].content or "").strip()
                headings = headings[: level - 1]
                headings.append(title or f"未命名标题 {level}")
                continue

            if (start, end) in used_spans:
                continue
            kind = self._token_kind(token.type, "\n".join(lines[start:end]))
            if kind is None:
                continue
            raw = "\n".join(lines[start:end]).strip()
            if not raw:
                continue
            used_spans.add((start, end))
            blocks.append(
                ContentBlock(
                    kind=kind,
                    markdown=raw,
                    heading_path=tuple(headings),
                    start_line=start + 1,
                    end_line=max(start + 1, end),
                )
            )

        if not blocks and markdown.strip():
            blocks.append(
                ContentBlock(
                    kind="text",
                    markdown=markdown.strip(),
                    heading_path=tuple(headings),
                    start_line=1,
                    end_line=max(1, len(lines)),
                )
            )
        return blocks

    @staticmethod
    def _token_kind(token_type: str, raw: str) -> str | None:
        if token_type in {"fence", "code_block"}:
            return "code"
        if token_type == "table_open":
            return "table"
        if token_type in {"bullet_list_open", "ordered_list_open"}:
            return "list"
        if token_type == "blockquote_open":
            return "callout"
        if token_type == "html_block":
            return "text"
        if token_type != "paragraph_open":
            return None
        stripped = raw.strip()
        if (stripped.startswith("$$") and stripped.endswith("$$")) or (
            stripped.startswith("\\[") and stripped.endswith("\\]")
        ):
            return "formula"
        if _VIDEO_MARKDOWN.match(stripped):
            return "video"
        if _IMAGE_ONLY.match(stripped):
            return "image"
        if _CALLOUT.match(stripped):
            return "callout"
        return "text"

    @staticmethod
    def _group_sections(blocks: Sequence[ContentBlock]) -> Iterable[tuple[tuple[str, ...], list[ContentBlock]]]:
        active_path: tuple[str, ...] | None = None
        active: list[ContentBlock] = []
        for block in blocks:
            if active and block.heading_path != active_path:
                yield active_path or (), active
                active = []
            active_path = block.heading_path
            active.append(block)
        if active:
            yield active_path or (), active

    def _context_prefix(self, document_title: str, heading_path: tuple[str, ...]) -> str:
        path = tuple(part for part in heading_path if part)
        if path and path[0] == document_title:
            value = " > ".join(path)
        elif path:
            value = " > ".join((document_title, *path))
        else:
            value = document_title
        return f"【章节上下文】: {value}".strip()

    def _chunk_section(
        self,
        blocks: Sequence[ContentBlock],
        *,
        heading_path: tuple[str, ...],
        document_id: str,
        document_title: str,
    ) -> list[StructuralChunk]:
        prefix = self._context_prefix(document_title, heading_path)
        body_budget = max(24, self.child_max_tokens - self.counter.count(prefix) - 2)
        units: list[ContentBlock] = []
        for block in blocks:
            units.extend(self._split_oversized_block(block, body_budget))

        chunks: list[StructuralChunk] = []
        normal_buffer: list[ContentBlock] = []

        def flush_normal() -> None:
            if not normal_buffer:
                return
            chunks.append(
                self._make_child(
                    normal_buffer,
                    document_id=document_id,
                    document_title=document_title,
                    heading_path=heading_path,
                )
            )
            normal_buffer.clear()

        for block in units:
            if block.kind in _SPECIAL_KINDS:
                flush_normal()
                chunks.append(
                    self._make_child(
                        [block],
                        document_id=document_id,
                        document_title=document_title,
                        heading_path=heading_path,
                    )
                )
                continue

            trial = [*normal_buffer, block]
            trial_text = "\n\n".join(item.markdown for item in trial)
            trial_total = self.counter.count(f"{prefix}\n\n{trial_text}")
            if normal_buffer and trial_total > self.child_target_tokens:
                flush_normal()
            normal_buffer.append(block)
            current_text = "\n\n".join(item.markdown for item in normal_buffer)
            if self.counter.count(f"{prefix}\n\n{current_text}") >= self.child_target_tokens:
                flush_normal()
        flush_normal()
        return chunks

    def _split_oversized_block(self, block: ContentBlock, body_budget: int) -> list[ContentBlock]:
        if self.counter.count(block.markdown) <= body_budget:
            return [block]
        if block.kind == "table":
            return self._split_table(block, body_budget)
        if block.kind == "code":
            return self._split_fenced(block, body_budget)
        if block.kind == "formula":
            return self._split_delimited(block, body_budget, "$$")
        return self._split_text_block(block, body_budget)

    def _split_table(self, block: ContentBlock, budget: int) -> list[ContentBlock]:
        lines = block.markdown.splitlines()
        if len(lines) < 3:
            return self._split_text_block(block, budget)
        header = lines[:2]
        rows = lines[2:]
        fragments: list[ContentBlock] = []
        current = list(header)
        for row in rows:
            trial = "\n".join([*current, row])
            if self.counter.count(trial) <= budget:
                current.append(row)
                continue
            if len(current) > 2:
                fragments.append(replace(block, markdown="\n".join(current)))
                current = list(header)
            single_row = "\n".join([*header, row])
            if self.counter.count(single_row) <= budget:
                current.append(row)
            else:
                fragments.extend(self._split_oversized_table_row(block, header, row, budget))
        if len(current) > 2:
            fragments.append(replace(block, markdown="\n".join(current)))
        return fragments or [block]

    def _split_oversized_table_row(
        self,
        block: ContentBlock,
        header: Sequence[str],
        row: str,
        budget: int,
    ) -> list[ContentBlock]:
        """Keep an exceptional giant row readable without violating the cap.

        Real-world HTML-to-Markdown converters sometimes collapse a navigation
        table into one enormous row. Normal tables retain their original header;
        only an individually oversized row is represented as bounded continuation
        tables. The original header is included in the text so information is not
        silently discarded.
        """

        source = f"原表表头：{' '.join(header)}\n原表行：{row}".strip()
        table_header = "| 续表内容 |\n| --- |"

        def render(value: str) -> str:
            safe = value.replace("|", "\\|").replace("\n", "<br>")
            return f"{table_header}\n| {safe} |"

        return [replace(block, markdown=render(value)) for value in self._split_wrapped_text(source, budget, render)]

    def _split_fenced(self, block: ContentBlock, budget: int) -> list[ContentBlock]:
        lines = block.markdown.splitlines()
        if len(lines) < 3 or not lines[0].lstrip().startswith("```"):
            return self._split_text_block(block, budget)
        opening = lines[0]
        closing = lines[-1] if lines[-1].lstrip().startswith("```") else "```"
        body = lines[1:-1] if lines[-1].lstrip().startswith("```") else lines[1:]
        fragments: list[ContentBlock] = []
        current: list[str] = []
        for line in body:
            trial = "\n".join([opening, *current, line, closing])
            if self.counter.count(trial) <= budget:
                current.append(line)
                continue
            if current:
                fragments.append(replace(block, markdown="\n".join([opening, *current, closing])))
                current = []
            single_line = "\n".join([opening, line, closing])
            if self.counter.count(single_line) <= budget:
                current = [line]
            else:
                render = lambda value: "\n".join([opening, value, closing])
                fragments.extend(
                    replace(block, markdown=render(value))
                    for value in self._split_wrapped_text(line, budget, render)
                )
        if current:
            fragments.append(replace(block, markdown="\n".join([opening, *current, closing])))
        return fragments or [block]

    def _split_delimited(self, block: ContentBlock, budget: int, delimiter: str) -> list[ContentBlock]:
        lines = block.markdown.splitlines()
        body = lines[1:-1] if len(lines) >= 2 else lines
        fragments: list[ContentBlock] = []
        current: list[str] = []
        for line in body:
            trial = "\n".join([delimiter, *current, line, delimiter])
            if self.counter.count(trial) <= budget:
                current.append(line)
                continue
            if current:
                fragments.append(replace(block, markdown="\n".join([delimiter, *current, delimiter])))
                current = []
            single_line = "\n".join([delimiter, line, delimiter])
            if self.counter.count(single_line) <= budget:
                current = [line]
            else:
                render = lambda value: "\n".join([delimiter, value, delimiter])
                fragments.extend(
                    replace(block, markdown=render(value))
                    for value in self._split_wrapped_text(line, budget, render)
                )
        if current:
            fragments.append(replace(block, markdown="\n".join([delimiter, *current, delimiter])))
        return fragments or [block]

    def _split_wrapped_text(self, text: str, budget: int, render) -> list[str]:
        """Split text while accounting for Markdown wrapper overhead."""

        remaining = text.strip()
        output: list[str] = []
        while remaining:
            low, high = 1, len(remaining)
            best = ""
            while low <= high:
                middle = (low + high) // 2
                candidate = remaining[:middle]
                if self.counter.count(render(candidate)) <= budget:
                    best = candidate
                    low = middle + 1
                else:
                    high = middle - 1
            if not best:
                raise ValueError("Markdown wrapper exceeds structural chunk budget")
            preferred = max(best.rfind(mark) for mark in ("。", "；", "，", "\n", " "))
            if preferred >= max(1, len(best) // 2):
                best = best[: preferred + 1]
            output.append(best.strip())
            remaining = remaining[len(best) :].strip()
        return [value for value in output if value]

    def _split_text_block(self, block: ContentBlock, budget: int) -> list[ContentBlock]:
        pieces = [piece.strip() for piece in _SENTENCE_BOUNDARY.split(block.markdown) if piece.strip()]
        if not pieces:
            pieces = [block.markdown]
        output: list[str] = []
        current = ""
        for piece in pieces:
            candidate = f"{current}{piece}" if current else piece
            if current and self.counter.count(candidate) > budget:
                output.append(current.strip())
                current = piece
            else:
                current = candidate
            while self.counter.count(current) > budget:
                cut = self._largest_prefix_within_budget(current, budget)
                output.append(cut.strip())
                current = current[len(cut):].strip()
        if current.strip():
            output.append(current.strip())
        return [replace(block, markdown=value) for value in output if value]

    def _largest_prefix_within_budget(self, text: str, budget: int) -> str:
        low, high = 1, len(text)
        best = text[:1]
        while low <= high:
            middle = (low + high) // 2
            candidate = text[:middle]
            if self.counter.count(candidate) <= budget:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        preferred = max(best.rfind(mark) for mark in ("。", "；", "，", "\n", " "))
        if preferred >= max(1, len(best) // 2):
            return best[: preferred + 1]
        return best

    def _make_child(
        self,
        blocks: Sequence[ContentBlock],
        *,
        document_id: str,
        document_title: str,
        heading_path: tuple[str, ...],
    ) -> StructuralChunk:
        display = "\n\n".join(block.markdown for block in blocks).strip()
        prefix = self._context_prefix(document_title, heading_path)
        embedding = f"{prefix}\n\n{display}".strip()
        if self.counter.count(embedding) > self.child_max_tokens:
            raise ValueError("structural chunk exceeds child_max_tokens")
        kinds = {block.kind for block in blocks}
        kind = next(iter(kinds)) if len(kinds) == 1 else "text"
        chunk_id = self._stable_id("child", document_id, "/".join(heading_path), display)
        return StructuralChunk(
            chunk_id=chunk_id,
            parent_id="",
            kind=kind,
            display_content=display,
            embedding_text=embedding,
            heading_path=heading_path,
            token_count=self.counter.count(embedding),
            start_line=min(block.start_line for block in blocks),
            end_line=max(block.end_line for block in blocks),
        )

    def _merge_tiny_neighbors(
        self,
        chunks: Sequence[StructuralChunk],
        *,
        document_id: str,
        document_title: str,
    ) -> list[StructuralChunk]:
        merged: list[StructuralChunk] = []
        for chunk in chunks:
            if not merged:
                merged.append(chunk)
                continue
            previous = merged[-1]
            can_merge = (
                chunk.heading_path == previous.heading_path
                and chunk.kind not in _SPECIAL_KINDS
                and previous.kind not in _SPECIAL_KINDS
                and (chunk.token_count < self.minimum_child_tokens or previous.token_count < self.minimum_child_tokens)
            )
            if can_merge:
                display = f"{previous.display_content}\n\n{chunk.display_content}"
                prefix = self._context_prefix(document_title, chunk.heading_path)
                embedding = f"{prefix}\n\n{display}"
                if self.counter.count(embedding) <= self.child_max_tokens:
                    merged[-1] = StructuralChunk(
                        chunk_id=self._stable_id("child", document_id, "/".join(chunk.heading_path), display),
                        parent_id="",
                        kind="text",
                        display_content=display,
                        embedding_text=embedding,
                        heading_path=chunk.heading_path,
                        token_count=self.counter.count(embedding),
                        start_line=previous.start_line,
                        end_line=chunk.end_line,
                    )
                    continue
            merged.append(chunk)
        return merged

    def _build_parents(
        self,
        children: Sequence[StructuralChunk],
        *,
        document_id: str,
    ) -> tuple[tuple[ParentChunk, ...], tuple[StructuralChunk, ...]]:
        parents: list[ParentChunk] = []
        assigned: list[StructuralChunk] = []
        cursor = 0

        def render_parent(group: Sequence[StructuralChunk]) -> str:
            parts: list[str] = []
            previous_path: tuple[str, ...] | None = None
            for item in group:
                if item.heading_path != previous_path and item.heading_path:
                    parts.append(f"### {' > '.join(item.heading_path)}")
                parts.append(item.display_content)
                previous_path = item.heading_path
            return "\n\n".join(parts)

        while cursor < len(children):
            # Parent spans adjacent leaf sections within the same top-level document
            # heading. This prevents a short but valid subsection from becoming an
            # equally tiny parent while preserving document/chapter boundaries.
            parent_scope = children[cursor].heading_path[:1]
            group: list[StructuralChunk] = []
            while cursor < len(children) and children[cursor].heading_path[:1] == parent_scope:
                candidate = children[cursor]
                trial = render_parent([*group, candidate])
                if group and self.counter.count(trial) > self.parent_target_tokens:
                    break
                group.append(candidate)
                cursor += 1
                if self.counter.count(trial) >= self.parent_target_tokens:
                    break
            content = render_parent(group)
            if self.counter.count(content) > self.parent_max_tokens:
                raise ValueError("parent chunk exceeds parent_max_tokens")
            heading_path = self._common_heading_prefix([item.heading_path for item in group])
            parent_id = self._stable_id("parent", document_id, "/".join(heading_path), content)
            parent = ParentChunk(
                parent_id=parent_id,
                display_content=content,
                heading_path=heading_path,
                child_ids=tuple(item.chunk_id for item in group),
                token_count=self.counter.count(content),
            )
            parents.append(parent)
            assigned.extend(replace(item, parent_id=parent_id) for item in group)
        return tuple(parents), tuple(assigned)

    @staticmethod
    def _common_heading_prefix(paths: Sequence[tuple[str, ...]]) -> tuple[str, ...]:
        if not paths:
            return ()
        common = list(paths[0])
        for path in paths[1:]:
            length = min(len(common), len(path))
            common = common[:length]
            while common and tuple(common) != path[: len(common)]:
                common.pop()
        return tuple(common)

    @staticmethod
    def _stable_id(*parts: str) -> str:
        digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:24]
        return f"{parts[0]}-{digest}"
