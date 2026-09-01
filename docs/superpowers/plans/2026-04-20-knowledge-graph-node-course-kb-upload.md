# Knowledge Graph Node Course KB Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-panel upload button on the knowledge graph page so the selected node can import local files directly into its course knowledge base scope.

**Architecture:** Reuse the existing course knowledge-base upload API and only add a scope-aware frontend entry on `KnowledgeGraphPage.tsx`. The selected graph node determines whether uploads go to `scope_type=knowledge_point` or `scope_type=course`, and the node detail panel refreshes its document count after upload succeeds.

**Tech Stack:** React, TypeScript, Ant Design, FastAPI route tests, node-based frontend text/structure tests

---

## File Map

- Modify: `frontend/src/pages/teacher/KnowledgeGraphPage.tsx`
  Responsibility: Add the node-detail upload button, file input wiring, scope-aware upload request, and post-upload refresh behavior.
- Test: `frontend/tests/frontend/knowledgeGraph.node-course-kb-upload.test.ts`
  Responsibility: Assert that the node-detail upload button exists and sends uploads into the correct course knowledge-base scope.
- Modify: `backend/src/tests/chat/test_course_scope_routes.py`
  Responsibility: Cover direct course knowledge-base uploads for both knowledge-point nodes and the course root scope.

---
