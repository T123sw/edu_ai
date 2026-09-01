# Teacher Content Templates

## 1) Lesson Plan JSON Template

```json
{
  "title": "课程标题",
  "objectives": ["目标1", "目标2"],
  "keyPoints": ["重点1", "重点2"],
  "hardPoints": ["难点1"],
  "process": [
    {"step": "导入", "content": "...", "duration": "5-8分钟"},
    {"step": "新授", "content": "...", "duration": "20-30分钟"}
  ],
  "homework": "课后任务说明"
}
```

## 2) Report JSON Template

```json
{
  "title": "报告标题",
  "summary": "执行摘要",
  "introduction": "引言",
  "mainContent": [
    {
      "title": "章节标题",
      "content": "章节内容",
      "subsections": [
        {"title": "子标题", "content": "子内容"}
      ]
    }
  ],
  "keyFindings": ["发现1", "发现2"],
  "conclusions": "结论",
  "recommendations": ["建议1"]
}
```

## 3) Question Item Template

```json
{
  "id": 1,
  "type": "选择题",
  "difficulty": "中",
  "content": "题干",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": "A",
  "analysis": "解析"
}
```

## 4) Generated Material Storage Template

```json
{
  "id": "material_id",
  "title": "标题",
  "material_type": "lesson_plan|report|quiz|blog",
  "selected_doc_ids": ["doc1"],
  "documents_used": ["文件名.pdf"],
  "created_at": "2026-03-21T00:00:00",
  "created_by": "teacher"
}
```
