# Routing Examples

## Example 1: Normal question

Input:
- question: `什么是TCP三次握手？`
- state: no awaiting flags

Expected:

```json
{
  "intent_category": "chat",
  "router_reason": "llm_json",
  "is_report": false,
  "response_type": "chat"
}
```

## Example 2: Report request

Input:
- question: `帮我生成一份期末教学总结报告`
- state: no awaiting flags

Expected:

```json
{
  "intent_category": "generate_content",
  "router_reason": "llm_json",
  "is_report": true,
  "response_type": "generate"
}
```

Note: `generate` here means enter report subgraph, not direct final markdown.

## Example 3: Awaiting clarification override

Input:
- question: `可以`
- state: `awaiting_clarification=true`

Expected:

```json
{
  "intent_category": "generate_content",
  "router_reason": "awaiting_clarification_override",
  "is_report": true,
  "response_type": "ask"
}
```

## Example 4: Fallback keyword routing

Input:
- question: `给我做个课件`
- LLM intent parsing failed

Expected:

```json
{
  "intent_category": "generate_content",
  "router_reason": "fallback_keyword:做个|课件",
  "response_type": "generate"
}
```
