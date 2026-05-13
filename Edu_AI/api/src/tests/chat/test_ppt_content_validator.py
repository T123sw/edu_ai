from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.chat.workflows.ppt.content_validator import PptContentValidator


def test_content_validator_accepts_full_protocol_block_set():
    markdown = """# Deck
- Title: TCP 三次握手
- Subtitle: 课堂讲解
- Theme: heu_academic_elegant

---

## Slide 1
- Role: cover
- Title: TCP 三次握手

### Blocks
- Lead: 从建立连接理解可靠传输。
- Meta:
  - Audience: 大一学生

---

## Slide 2
- Role: toc
- Title: 目录

### Blocks
- Toc:
  - 基本概念
  - 三次握手流程

---

## Slide 3
- Role: content
- Title: 三次握手流程

### Blocks
- Bullets:
  - 第一次握手发送 SYN。
  - 第二次握手返回 SYN + ACK。
- Process:
  - Step-Title: SYN
    Step-Text: 客户端发起连接请求。
  - Step-Title: ACK
    Step-Text: 双方完成确认。
- Comparison:
  - Left-Title: 未完成握手
    Left-Items:
      - 无法安全传输
    Right-Title: 完成握手
    Right-Items:
      - 可以进入数据传输
- Cards:
  - Title: 核心目标
    Text: 确认双方收发能力正常。
- Media:
  - Kind: image
  - URL: https://example.com/tcp.png
"""

    validation = PptContentValidator().validate(markdown)

    assert validation["ok"] is True
    assert validation["errors"] == []


def test_content_validator_rejects_invalid_role_and_missing_blocks():
    markdown = """# Deck
- Title: Broken Deck

---

## Slide 1
- Role: not-a-role
- Title: Broken
"""

    validation = PptContentValidator().validate(markdown)

    assert validation["ok"] is False
    assert any("invalid role" in error for error in validation["errors"])
    assert any("missing blocks" in error for error in validation["errors"])
