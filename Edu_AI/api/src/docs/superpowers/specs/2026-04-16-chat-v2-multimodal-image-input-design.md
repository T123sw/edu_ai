# Chat V2 Multimodal Image Input Design

Date: 2026-04-16

## Goal

Enable chat v2 to accept user-provided images and let the answer stage use both:

- user input images
- RAG-retrieved images

through the same `qwen3.5-plus` multimodal answer path.

## Scope

This slice covers:

- teacher chat input supports paste/select image
- backend stores chat input images locally under a guarded temp/chat area
- `/api/chat/v2/reply` accepts structured image references in JSON
- fast chat runtime upgrades from text-only to multimodal when images exist
- conversation persistence keeps enough image metadata for frontend display and resend context

This slice does not yet cover:

- image-aware ranking improvements inside retrieval
- OCR/caption generation for user input images before answering
- full historical image message rendering in all chat pages

## Recommended Approach

Use `JSON + pre-upload`.

Frontend uploads images first and receives backend-owned image references. The normal `/api/chat/v2/reply` request then includes `input_images`. This keeps the existing reply route, auth model, error handling, and conversation persistence stable while avoiding large base64 request bodies.

## Data Model

Add a shared `input_images` field across chat v2 request models that need direct chat input.

Each image item should include:

- `image_id`: stable backend-generated id
- `storage_path`: absolute backend path, server-side only
- `relative_path`: relative storage path for guarded preview serving
- `image_url`: frontend-readable guarded media URL
- `mime_type`
- `file_name`
- `source`: `upload` or `paste`

Runtime should treat `storage_path` as the authoritative model-input source and `image_url` as frontend display metadata.

## Backend Flow

1. Frontend uploads one or more images to a new chat image upload endpoint.
2. Backend stores files under `storage/chat_images/<owner>/<conversation-or-session>/`.
3. Upload response returns normalized image metadata plus guarded preview URL.
4. Frontend sends `/api/chat/v2/reply` with `question + input_images`.
5. `normalize_chat_request()` carries `input_images` into `ChatRequestV2`.
6. `FastChatRuntime` builds one multimodal message:
   - text block with user question and any RAG/web context
   - image blocks for user input images
   - image blocks for RAG image sources when present
7. If any image block exists, runtime calls the vision-capable gateway/model path; otherwise it stays on text chat.

## Frontend Flow

1. `ChatPanel` supports:
   - paste image from clipboard
   - select image from file picker
   - thumbnail preview before send
   - remove pending image before send
2. On add, image uploads immediately and returns backend metadata.
3. Pending images are shown under the text box.
4. On send, `buildChatReplyPayload()` includes `input_images`.
5. After successful send, pending images clear.

## Conversation Persistence

Store input image metadata in conversation state so follow-up UX can evolve without re-uploading raw files.

Minimum state patch:

- `last_input_images`
- `last_input_image_count`

Optionally include lightweight message metadata later, but this slice avoids changing the core message schema more than necessary.

## Error Handling

- upload type validation: allow common raster image MIME types only
- upload size guard: fail clearly when file exceeds configured limit
- missing file after upload: skip image and return actionable error
- multimodal model failure: fall back to text-only answer with the same textual context when possible

## Testing

Backend:

- route/schema accepts `input_images`
- upload endpoint returns normalized metadata
- fast runtime builds multimodal messages when input images exist
- no-image requests remain text-only

Frontend:

- paste/upload image creates pending preview
- removing image updates state
- send includes `input_images`
- successful send clears pending images

## Follow-up

After this slice is stable, the next slice should make retrieved image hits and user input images visible in the same answer evidence UI, then add image-aware retrieval/reranking.
