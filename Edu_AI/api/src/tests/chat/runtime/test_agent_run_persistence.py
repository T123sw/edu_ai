from app.chat.persistence.agent_run_store import AgentRunStore


def test_agent_run_store_survives_a_new_store_instance(tmp_path):
    db_path = tmp_path / "agent_runs.db"
    first = AgentRunStore(db_path)
    first.save(
        conversation_id="conv-1",
        owner_user_id="teacher-1",
        course_id="course-1",
        state={
            "active_draft_outline": {"subject": "快速排序", "resource_type": "report"},
            "pending_tasks": [{"task_id": "job-1", "workflow_type": "report"}],
            "task_contract": {"intent": "generate_single"},
        },
    )
    first.close()

    second = AgentRunStore(db_path)
    restored = second.load("conv-1", owner_user_id="teacher-1")

    assert restored["active_draft_outline"]["subject"] == "快速排序"
    assert restored["pending_tasks"][0]["task_id"] == "job-1"
    assert restored["task_contract"]["intent"] == "generate_single"


def test_agent_run_store_does_not_return_another_owner_state(tmp_path):
    store = AgentRunStore(tmp_path / "agent_runs.db")
    store.save("conv-1", "teacher-1", "course-1", {"pending_tasks": [{"task_id": "job-1"}]})

    assert store.load("conv-1", owner_user_id="teacher-2") == {}


def test_agent_run_store_does_not_return_another_course_state(tmp_path):
    store = AgentRunStore(tmp_path / "agent_runs.db")
    store.save("conv-1", "teacher-1", "course-1", {
        "agent_memory": {"working_memory": {"active_topic": "快速排序"}}
    })

    assert store.load(
        "conv-1", owner_user_id="teacher-1", course_id="course-2"
    ) == {}
    restored = store.load(
        "conv-1", owner_user_id="teacher-1", course_id="course-1"
    )
    assert restored["agent_memory"]["working_memory"]["active_topic"] == "快速排序"
