# RAG Multimodal Examples

## Example 1: Text-only RAG answer

Context:
- RAG enabled
- tool sources include only text chunks

Expected runtime summary:

```json
{
  "sources_images": 0,
  "injected": 0,
  "final_answer_role": "deep"
}
```

## Example 2: Image successfully injected

Context:
- sources contain 2 image records with valid local paths
- 2 files readable

Expected runtime summary:

```json
{
  "sources_images": 2,
  "injected": 2,
  "final_answer_role": "vision"
}
```

## Example 3: Partial image failure

Context:
- sources image count = 3
- 1 missing file, 2 valid files

Expected runtime summary:

```json
{
  "sources_images": 3,
  "injected": 2,
  "final_answer_role": "vision",
  "degraded": true
}
```

## Example 4: Vision failure fallback

Context:
- image injected count > 0
- vision invoke error thrown

Expected behavior:
- keep text draft as final answer
- log vision error
- no user-facing crash
