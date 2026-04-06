# Course Materials Pin Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When resources are generated, persist them into the course materials area as well as the right-side studio list, and support pinning course materials so the linked file moves to the top of the three-column studio list.

**Architecture:** Persist course materials metadata in backend storage with pin fields, expose pin/delete APIs from the course materials routes, refresh the course materials store from backend after generation, and use a shared frontend sorting helper so both the course materials page and the studio list honor the same pinned-first order.

**Tech Stack:** FastAPI, JSON course storage, React, Zustand, TypeScript, Ant Design

---
