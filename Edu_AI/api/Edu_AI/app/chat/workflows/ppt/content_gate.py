from __future__ import annotations

from typing import Any

from .content_validator import PptContentValidator


class PptContentGate:
    def __init__(
        self,
        *,
        content_validator: PptContentValidator | None = None,
    ) -> None:
        self.content_validator = content_validator or PptContentValidator()

    @staticmethod
    def _issue(
        *,
        code: str,
        severity: str,
        slide_index: int | None,
        field_path: str,
        message: str,
        suggested_action: str,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "severity": severity,
            "slide_index": slide_index,
            "field_path": field_path,
            "message": message,
            "suggested_action": suggested_action,
        }

    def apply(self, *, content_markdown: str, outline) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        validation = self.content_validator.validate(content_markdown)
        for error in list(validation.get("errors") or []):
            issues.append(
                self._issue(
                    code="content.structure.invalid",
                    severity="error",
                    slide_index=None,
                    field_path="content_markdown",
                    message=str(error),
                    suggested_action="fix_content_structure",
                )
            )

        errors = [issue["message"] for issue in issues if issue.get("severity") == "error"]
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": [],
            "issues": issues,
            "transformations": [],
            "final_markdown": content_markdown,
        }
