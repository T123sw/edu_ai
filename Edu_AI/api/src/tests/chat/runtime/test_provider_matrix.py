from scripts.smoke_teacher_agent_provider_matrix import (
    _provider_id,
    _run_tool_case,
)


class _ToolGateway:
    def stream_chat_with_tools(self, *_args, **_kwargs):
        yield {
            "type": "tool_calls",
            "calls": [{
                "name": "record_teaching_topic",
                "args": {"topic": "快速排序", "audience": "高一学生"},
            }],
        }
        yield {"type": "done"}


def test_provider_report_identifier_never_contains_credentials():
    identifier = _provider_id({
        "api_base": "https://provider.example/v1",
        "api_key": "secret-value",
        "model_name": "model-a",
    })

    assert identifier == "provider.example/model-a"
    assert "secret" not in identifier


def test_provider_tool_case_requires_named_call_and_arguments():
    passed, observation = _run_tool_case(_ToolGateway())

    assert passed is True
    assert observation == "required_tool_with_arguments"
