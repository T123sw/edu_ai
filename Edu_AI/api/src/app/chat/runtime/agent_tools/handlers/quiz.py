"""Agent tool handler: generate_quiz.

Calls QuizGenerator.generate() directly via submit_callable_task.
No outline step required — agent calls this directly on user request.
"""
from __future__ import annotations

from app.chat.runtime.agent_tools.result import error_result, ok_result


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
    rag_fetcher = ctx.rag_retriever

    def _run():
        from app.chat.agents.report_generation import get_fallback_llm
        from app.chat.workflows.quiz.generator import QuizGenerator

        generator = QuizGenerator(
            llm=get_fallback_llm(),
            rag_fetcher=rag_fetcher,
        )
        preparation = {
            "topic": subject,
            "question_count": question_count,
            "question_types": question_types,
            "difficulty": difficulty,
            "knowledge_points": [],
            "weak_points": [],
            "source_scope": selected_doc_ids,
        }
        artifact = generator.generate(
            preparation=preparation,
            context_summary="",
            conversation_id=conversation_id,
            owner=owner,
            allow_rag=allow_rag,
            selected_doc_ids=selected_doc_ids,
        )
        return {"status": "completed", "artifacts": [artifact]}

    try:
        from app.chat.tasks.background_runner import submit_callable_task
        task_id = submit_callable_task(
            fn=_run,
            workflow_type="quiz",
            owner_user_id=owner,
            course_id=course_id,
            scope_type=str(getattr(ctx.request, "scope_type", None) or "course"),
            scope_id=getattr(ctx.request, "scope_id", None),
            input_summary={"title": subject},
        )
    except Exception as exc:
        return error_result(name, str(exc), f"任务提交失败: {exc}")

    return ok_result(
        name,
        f"已提交练习题生成任务，task_id={task_id}",
        {"task_id": task_id, "workflow_type": "quiz"},
    )
