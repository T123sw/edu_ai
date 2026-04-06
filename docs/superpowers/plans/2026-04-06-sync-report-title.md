# Sync Report Title Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a report is generated, automatically sync a stable report name into the artifact list so the right-side studio shows a meaningful file name instead of a generic fallback.

**Architecture:** Add a backend title-normalization step in the report service so report artifacts persist with a concrete `title`, then keep a frontend fallback that derives the name from the report content heading when older artifacts have no title.

**Tech Stack:** FastAPI, TypeScript, React

---
