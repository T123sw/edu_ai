"""LLM integration — JSON parsing and response cleaning utilities.

Shared by all services that call LLMs and need to parse JSON from their output.
"""

from __future__ import annotations

import json
import re
from typing import Optional


def remove_thinking_tags(text: str) -> str:
    """Remove think / thought / thinking tags from LLM output."""
    patterns = [
        r'<think>.*?</think>',
        r'<thinking>.*?</thinking>',
        r'<thought>.*?</thought>',
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def clean_json_text(text: str) -> str:
    """Strip markdown code fences and thinking tags, extract JSON body."""
    cleaned = remove_thinking_tags(text)
    if cleaned.startswith("```"):
        lines = cleaned.split("\n", 1)
        cleaned = lines[1] if len(lines) > 1 else cleaned.lstrip("`")
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    if "{" in cleaned:
        cleaned = cleaned[cleaned.find("{"):]
    return cleaned


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output with basic cleanup (code fences, thinking tags)."""
    cleaned = clean_json_text(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # try extracting just the outermost braces
        if "{" in cleaned and "}" in cleaned:
            extracted = cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
            return json.loads(extracted)
        raise


def smart_json_parse(text: str) -> Optional[dict]:
    """Multi-strategy JSON parser for potentially malformed LLM output.

    Strategies (in order):
    1. Direct parse
    2. Brace-matching truncation
    3. Unclosed string repair
    4. Regex-based field extraction (best-effort fallback)
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Brace-matching truncation
    try:
        brace_count = 0
        last_valid_pos = -1
        for i, char in enumerate(text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    last_valid_pos = i
        if last_valid_pos > 0:
            return json.loads(text[:last_valid_pos + 1])
    except (json.JSONDecodeError, IndexError):
        pass

    # Unclosed string repair
    try:
        fixed = text
        matches = list(re.finditer(r'"(\w+)":\s*"', fixed))
        if matches:
            last_field = matches[-1]
            field_start = last_field.end()
            remaining = fixed[field_start:]
            quote_pos = -1
            i = 0
            while i < len(remaining):
                if remaining[i] == '"':
                    backslash_count = 0
                    j = i - 1
                    while j >= 0 and remaining[j] == '\\':
                        backslash_count += 1
                        j -= 1
                    if backslash_count % 2 == 0:
                        quote_pos = field_start + i
                        break
                i += 1
            if quote_pos == -1:
                end_pos = len(fixed)
                for i in range(field_start, len(fixed)):
                    if fixed[i] == '\n':
                        after = fixed[i+1:].lstrip()
                        if after and after[0] in ['}', ']', ',']:
                            end_pos = i
                            break
                before = fixed[:end_pos].rstrip()
                after = fixed[end_pos:].lstrip()
                if after and after[0] in ['}', ']']:
                    fixed = before + '"' + after
                elif after and after[0] == ',':
                    fixed = before + '"' + after
                else:
                    fixed = before + '"' + (after if after else '}')
                open_braces = fixed.count('{')
                close_braces = fixed.count('}')
                missing = open_braces - close_braces
                if missing > 0:
                    fixed += '}' * missing
                return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # Regex-based field extraction (best-effort)
    return _regex_extract_report_fields(text)


def _regex_extract_report_fields(text: str) -> Optional[dict]:
    """Regex-based extraction of report fields from malformed JSON (last-resort fallback)."""
    try:
        result: dict = {}
        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', text)
        if title_match:
            result['title'] = title_match.group(1)
        summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if summary_match:
            result['summary'] = summary_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')[:500]
        intro_match = re.search(r'"introduction"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if intro_match:
            result['introduction'] = intro_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')[:500]
        concl_match = re.search(r'"conclusions"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if concl_match:
            result['conclusions'] = concl_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')[:500]
        findings_match = re.search(r'"keyFindings"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if findings_match:
            findings_text = findings_match.group(1)
            findings = re.findall(r'"((?:[^"\\]|\\.)*)"', findings_text)
            result['keyFindings'] = [f.replace('\\"', '"').replace('\\n', '\n') for f in findings[:10]]
        else:
            result['keyFindings'] = []
        main_match = re.search(r'"mainContent"\s*:\s*\[(.*)\]', text, re.DOTALL)
        if main_match:
            content_text = main_match.group(1)
            sections = []
            section_pattern = r'\{\s*"title"\s*:\s*"([^"]*)"\s*,\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)"'
            for match in re.finditer(section_pattern, content_text, re.DOTALL):
                content = match.group(2).replace('\\"', '"').replace('\\n', '\n')[:400]
                sections.append({'title': match.group(1), 'content': content, 'subsections': None})
            result['mainContent'] = sections[:5] if sections else []
        else:
            result['mainContent'] = []
        rec_match = re.search(r'"recommendations"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if rec_match:
            rec_text = rec_match.group(1)
            result['recommendations'] = [r.replace('\\"', '"') for r in re.findall(r'"((?:[^"\\]|\\.)*)"', rec_text)[:5]]
        else:
            result['recommendations'] = None
        if result.get('title') and result.get('summary'):
            return result
    except Exception:
        pass
    return None
