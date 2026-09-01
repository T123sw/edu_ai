# Report Workflow Examples

## Example 1: Missing core slots -> ask

State:
- topic present
- period missing

Expected route:

```json
{
  "response_type": "ask",
  "missing": ["period"]
}
```

## Example 2: Slots complete -> outline

State:
- required slots all available
- outline not yet produced

Expected route:

```json
{
  "response_type": "outline",
  "report_outline_pending": true
}
```

## Example 3: Outline pending + user confirms

Input:
- user: `按这个大纲生成`

Expected route:

```json
{
  "user_intent": "confirm_outline",
  "response_type": "generate"
}
```

## Example 4: User modifies outline

Input:
- user: `第一章加上研究背景，第三章删掉`

Expected route:

```json
{
  "user_intent": "modify",
  "response_type": "outline"
}
```

Behavior:
- update only requested sections
- preserve unchanged sections
