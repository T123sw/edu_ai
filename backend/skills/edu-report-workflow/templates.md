# Report Workflow Templates

## 1) Ask Template (single-slot follow-up)

```text
收到，你想做【{topic_or_hint}】方向的报告。为了继续，我还需要确认一点：{missing_slot_question}？
```

Constraints:
- 1-2 sentences
- ask one thing only
- ends with `？`

## 2) Outline Template

```markdown
下面是报告大纲，请你确认是否按此生成正文：

## 一、{section_1}
- {point_1}
- {point_2}

## 二、{section_2}
- {point_1}
- {point_2}

## 三、{section_3}
- {point_1}
- {point_2}

如需修改，请直接说“第X部分改为...”；如确认，请回复“按这个生成”。
```

## 3) Final Markdown Template

```markdown
# {report_title}

## 引言
{intro}

## {section_1}
{content_1}

## {section_2}
{content_2}

## {section_3}
{content_3}

## 结论与建议
{conclusion}
```

Requirements:
- Keep section order consistent with confirmed outline
- Use professional but readable Chinese
- Avoid unrelated sections
