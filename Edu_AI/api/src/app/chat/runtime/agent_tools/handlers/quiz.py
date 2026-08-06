"""Agent tool handler: enqueue a durable quiz-generation command."""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result
from app.services.generation_command import (
    GenerationCommand,
    generation_command_service,
)
from uuid import uuid4


def handle_generate_quiz(name: str, args: dict, ctx) -> dict:
    subject = str(args.get("subject", "")).strip()
    question_count = int(args.get("question_count") or 10)
    difficulty = str(args.get("difficulty") or "medium")
    question_types = list(args.get("question_types") or [])

    if not subject:
        return error_result(name, "missing_subject", "题目主题不能为空")

    # Default to mixed types if not specified
    if not question_types:
        question_types = ["choice", "blank", "short"]

    conversation_id = str(getattr(ctx.request, "conversation_id", "") or "")
    owner = getattr(ctx.request, "owner", None)
    course_id = getattr(ctx.request, "course_id", None)
    allow_rag = bool(getattr(ctx.capability, "allow_rag", False))
    selected_doc_ids = list(getattr(ctx.capability, "selected_doc_ids", []) or [])
    try:
        command = GenerationCommand(
            resource_type="quiz",
            owner_user_id=str(owner or ""),
            course_id=str(course_id or ""),
            scope_type=str(
                getattr(ctx.request, "scope_type", None) or "course"
            ),
            scope_id=getattr(ctx.request, "scope_id", None),
            selected_doc_ids=selected_doc_ids,
            config={
                "entrypoint": "agent",
                "title": subject,
                "subject": subject,
                "question_count": question_count,
                "difficulty": difficulty,
                "question_types": question_types,
                "conversation_id": conversation_id,
                "allow_rag": allow_rag,
            },
            idempotency_key=f"agent-quiz-{uuid4()}",
        )
        job = generation_command_service.submit(command)
        task_id = job.edu_job_id
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交练习题生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "quiz"},
    )
