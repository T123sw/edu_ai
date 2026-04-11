from __future__ import annotations

import re


class PptContentValidator:
    _VALID_ROLES = {"cover", "toc", "section", "content", "thanks"}
    _VALID_BLOCKS = {"Lead", "Bullets", "Meta", "Toc", "Cards", "Comparison", "Process", "Media"}

    @staticmethod
    def _extract_slide_chunks(text: str) -> list[tuple[str, str]]:
        pattern = re.compile(r"(?ms)^## Slide\s+(\d+)\s*$\n(.*?)(?=^---\s*$|^## Slide\s+\d+\s*$|\Z)")
        return [(match.group(1), match.group(2)) for match in pattern.finditer(text)]

    @staticmethod
    def _extract_blocks_section(slide_text: str) -> str:
        match = re.search(r"(?ms)^### Blocks\s*$\n(.*?)(?=^### Notes\s*$|^---\s*$|\Z)", slide_text)
        return (match.group(1) if match else "").strip()

    def validate(self, markdown: str) -> dict:
        text = str(markdown or "").strip()
        errors: list[str] = []

        if not text:
            return {"ok": False, "errors": ["empty content_markdown"]}

        if not text.startswith("# Deck"):
            errors.append("missing deck header")

        slide_chunks = self._extract_slide_chunks(text)
        if not slide_chunks:
            errors.append("missing slide blocks")

        for slide_index, slide_body in slide_chunks:
            role_match = re.search(r"(?m)^- Role:\s*(.+?)\s*$", slide_body)
            title_match = re.search(r"(?m)^- Title:\s*(.+?)\s*$", slide_body)
            if role_match is None:
                errors.append(f"slide {slide_index} missing role")
            else:
                role = str(role_match.group(1) or "").strip()
                if role not in self._VALID_ROLES:
                    errors.append(f"slide {slide_index} invalid role: {role}")
            if title_match is None:
                errors.append(f"slide {slide_index} missing title")

            if "### Blocks" not in slide_body:
                errors.append(f"slide {slide_index} missing blocks")
                continue

            blocks_text = self._extract_blocks_section(slide_body)
            if not blocks_text:
                errors.append(f"slide {slide_index} missing blocks")
                continue

            block_names = re.findall(r"(?m)^- ([A-Za-z][A-Za-z-]*):", blocks_text)
            if not block_names:
                errors.append(f"slide {slide_index} missing protocol block type")
                continue

            invalid_block_names = [name for name in block_names if name not in self._VALID_BLOCKS]
            for name in invalid_block_names:
                errors.append(f"slide {slide_index} invalid block type: {name}")

            if block_names.count("Media") > 1:
                errors.append(f"slide {slide_index} has more than one Media block")

            if "Media" in block_names:
                media_block = re.search(r"(?ms)^- Media:\s*$\n(.*?)(?=^- [A-Za-z][A-Za-z-]*:|^### Notes\s*$|^---\s*$|\Z)", blocks_text)
                media_text = media_block.group(1) if media_block else ""
                if not re.search(r"(?m)^\s*- Kind:\s*(image|video)\s*$", media_text):
                    errors.append(f"slide {slide_index} media block missing valid Kind")
                if not re.search(r"(?m)^\s*- URL:\s*\S+\s*$", media_text):
                    errors.append(f"slide {slide_index} media block missing URL")

        return {"ok": not errors, "errors": errors}
