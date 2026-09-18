"""Locate exact source spans despite presentation-only Markdown differences."""
import re


def visible_with_offsets(text):
    positions = list(range(len(text)))
    # Keep link labels and inline code text, never rewrite words or operators.
    for pattern in (r'\[([^\]\n]+)\]\([^\n]*?\)', r'`([^`\n]+)`', r'(?<![\w*])\*\*([^\s*](?:[^*\n]*?[^\s*])?)\*\*(?![\w*])', r'(?<![\w*])\*([^\s*](?:[^*\n]*?[^\s*])?)\*(?![\w*])'):
        for match in reversed(list(re.finditer(pattern, text))):
            start, end = match.span()
            left, right = match.span(1)
            positions[start:end] = positions[left:right]
            text = text[:start] + text[left:right] + text[end:]
    chars, offsets = [], []
    for char, offset in zip(text, positions):
        if char.isspace():
            if chars and chars[-1] != ' ':
                chars.append(' ')
                offsets.append(offset)
        else:
            chars.append(char)
            offsets.append(offset)
    return ''.join(chars), offsets


def locate_quote(content, quote):
    if quote in content:
        return quote
    visible, offsets = visible_with_offsets(content)
    needle, _ = visible_with_offsets(quote)
    needle = needle.strip()
    if len(needle) < 8:
        return None
    start = visible.find(needle)
    if start < 0 or visible.find(needle, start + 1) >= 0:
        return None
    raw = content[offsets[start]:offsets[start + len(needle) - 1] + 1]
    # Return actual original bytes/text, not a paraphrase or normalized citation.
    return raw if 8 <= len(raw) <= 400 else None
