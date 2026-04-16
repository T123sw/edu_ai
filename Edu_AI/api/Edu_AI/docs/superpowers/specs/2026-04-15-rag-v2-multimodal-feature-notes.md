# RAG v2 Multimodal Feature Notes

Date: 2026-04-15

## Planned Features

- Use a vision-capable model so retrieved images can participate in answer generation.
- Switch the system answer-generation model to `qwen3.5plus`; the environment file is expected to provide the needed configuration.
- Let users input images in chat, including paste-from-clipboard into the text box.
- Let RAG retrieve image content and provide image context to the answer model.
- When uploaded/imported files are images, store them locally first.
- Show uploaded/imported images in the frontend left source preview panel.

## Current Slice

Implement image preview first:

- Frontend upload accepts common image files.
- Image uploads use the RAG v2 image import endpoint.
- RAG v2 document listing includes owner-scoped image entries.
- The left source panel recognizes image entries and renders the stored image through the guarded RAG media endpoint.
