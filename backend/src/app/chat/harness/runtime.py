"""Python SDK lifecycle, event adapter and explicit cross-turn recovery."""
from __future__ import annotations

import json
import logging
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

from filelock import Timeout

from .bridge import tool_bridge
from .store import HarnessStore
from .tools import ReportTools

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
PERSONA = (ROOT / "root-role.md").read_text(encoding="utf-8")


class HarnessRuntime:
    def __init__(self, *, store, tool_factory, sdk_factory=None, model="deepseek-v4-flash",
                 api_key="", base_url="https://api.deepseek.com/v1", timeout=180):
        self.store, self.tool_factory, self.sdk_factory = store, tool_factory, sdk_factory
        self.model, self.api_key, self.base_url, self.timeout = model, api_key, base_url, timeout

    @staticmethod
    def supports(request):
        # Explicit UI actions outside this pilot retain their existing path.
        return (not getattr(request, "input_images", None) and not getattr(request, "input_videos", None)
                and not getattr(request, "artifact_reference", None)
                and (getattr(request, "action_hint", None) or "") in {"", "chat.reply", "generate.report", "research.lookup"})

    def run(self, *, request, snapshot):
        result = None
        for event in self.run_stream(request=request, snapshot=snapshot):
            if event["type"] == "result":
                result = event["payload"]
        if result is None:
            raise RuntimeError("Harness returned no result")
        return result

    def run_stream(self, *, request, snapshot):
        if not request.conversation_id:
            request.conversation_id = "conv-" + uuid4().hex[:12]
        request.request_id = request.request_id or uuid4().hex
        original_request = request.model_dump(mode="json")
        events = queue.Queue()
        cancelled = threading.Event()
        active = []

        def worker():
            try:
                with self.store.session(request) as session:
                    saved = session.data["responses"].get(request.request_id)
                    if saved:
                        if saved["request"] != original_request:
                            raise ValueError("request_id reused with different input")
                        replay = json.loads(json.dumps(saved["result"]))
                        replay["trace"]["response_replayed"] = True
                        events.put({"type": "result", "payload": replay})
                        return
                    tools = self.tool_factory(request=request, session=session,
                                              emit=events.put, cancelled=cancelled)
                    session.event({"type": "request", "request_id": request.request_id,
                                   "question": request.question})
                    context = self._context(request, snapshot, session, tools)
                    with tool_bridge(tools) as (url, token), tempfile.TemporaryDirectory(prefix="edu-dsh-") as temp:
                        patch_file = Path(temp) / "profile.patch.yml"
                        patch_file.write_text(self._patch(url), encoding="utf-8")
                        sdk_factory = self.sdk_factory
                        if sdk_factory is None:
                            from deepseek_harness import DeepSeekHarness
                            sdk_factory = DeepSeekHarness
                        harness = sdk_factory(
                            provider="deepseek-official", model=self.model, max_tokens=16000,
                            api_key=self.api_key, base_url=self.base_url, profile="sdk-minimal",
                            cwd=temp, dsh_home=str(Path(temp) / "home"), patches=(str(patch_file),),
                            initialize_timeout_seconds=min(40, self.timeout),
                            request_timeout_seconds=self.timeout, shutdown_timeout_seconds=2,
                            env={"DSH_TELEMETRY_DISABLED": "1", "EDU_MCP_TOKEN": token},
                        )
                        active.append(harness)
                        if cancelled.is_set():
                            return

                        def observe(notification):
                            if cancelled.is_set():
                                return
                            if notification.method != "session.event":
                                return
                            event = notification.payload.get("event") or {}
                            chunk = (event.get("data") or {}).get("chunk") or {}
                            if event.get("type") == "assistant/chunk" and chunk.get("type") == "text-delta":
                                # The saved outline is the confirmation source of truth.
                                # Do not stream a second, model-paraphrased outline before it.
                                if not any(item["ok"] and item["tool"] == "draft_report_outline" for item in tools.outcomes):
                                    events.put({"type": "delta", "payload": {"content": chunk.get("text", "")}})
                            if event.get("type") in {"tool/call", "tool/result", "turn/end", "step/end"}:
                                session.event({"request_id": request.request_id, "harness_event": event})
                            if event.get("type") == "tool/call" and (event.get("data") or {}).get("name") == "skill":
                                events.put({"type": "status", "payload": {"stage": "skill", "label": "正在加载任务流程"}})

                        try:
                            with harness:
                                response = harness.run(context, session_id=request.request_id, on_notification=observe)
                                missing = tools.required_retrieval_missing()
                                if missing:
                                    response = harness.run('用户本轮开启的检索按钮是必须执行的要求。尚未调用：' + ', '.join(missing) +
                                        '。请调用相应工具后再答复；若失败如实说明，不编造结果。',
                                        session_id=request.request_id, on_notification=observe)
                                if tools.required_retrieval_missing():
                                    raise RuntimeError('required_retrieval_not_attempted')
                        finally:
                            harness.close()
                        if cancelled.is_set():
                            return
                        if response.finish_reason not in {None, "stop", "end_turn", "completed"}:
                            raise RuntimeError("Harness turn did not finish normally")
                        result = self._result(request, response.final_response, tools)
                        session.data["history"].extend([
                            {"role": "user", "content": request.question},
                            {"role": "assistant", "content": result["message"]["content"]},
                        ])
                        session.data["history"] = session.data["history"][-20:]
                        session.data["responses"][request.request_id] = {"request": original_request, "result": result}
                        # Keep recent response replay bounded; operation idempotency
                        # for submitted reports lives in the business job service.
                        while len(session.data["responses"]) > 50:
                            del session.data["responses"][next(iter(session.data["responses"]))]
                        session.save()
                        session.event({"type": "response", "request_id": request.request_id, "result": result})
                        events.put({"type": "result", "payload": result})
            except Timeout:
                events.put({"type": "result", "payload": self._failure(request, "当前对话正在处理另一条请求，请稍后重试。", "conversation_busy")})
            except Exception as exc:
                logger.warning("Harness turn failed (%s)", type(exc).__name__)
                # Do not silently execute a second runtime after side effects.
                events.put({"type": "result", "payload": self._failure(request,
                    "对话处理未完成，请重试。已提交的报告任务可在任务列表中查看。", "harness_unavailable")})
            finally:
                events.put(None)

        thread = threading.Thread(target=worker, name="edu-harness-turn", daemon=True)
        thread.start()
        deadline = time.monotonic() + self.timeout
        yield {"type": "metadata", "payload": {"conversation_id": request.conversation_id,
               "runtime": "deepseek-harness", "trace": {"path": "deepseek-harness"}}}
        yield {"type": "status", "payload": {"stage": "thinking", "label": "正在处理请求"}}
        try:
            while True:
                if time.monotonic() >= deadline:
                    yield {"type": "result", "payload": self._failure(request,
                        "本轮处理超时。已提交的报告任务仍可在任务列表中查看。", "harness_timeout")}
                    break
                try:
                    event = events.get(timeout=min(1, max(.01, deadline-time.monotonic())))
                except queue.Empty:
                    continue
                if event is None:
                    break
                yield event
        finally:
            cancelled.set()
            for harness in active:
                harness.close()
            thread.join(timeout=2)

    def _patch(self, url):
        rows = [{"id": name, "disabled": True} for name in
                ("persistent-bash", "persistent-pwsh", "str-replace-editor")]
        rows += [{"id": "system-prompt", "config": {"includeHarnessIdentity": False,
                  "includeRuntimeContext": False, "persona": PERSONA}},
                 {"insert": [
                     {"id": "edu-skills", "name": "@deepseek-ai/dsh-skill"},
                     {"id": "edu-skill-files", "name": "@deepseek-ai/dsh-skill-filesystem", "config": {
                         "includeDefaultRoots": False, "customSkillDirs": [str(ROOT / "skills")], "watch": False}},
                     {"id": "edu-skill-loader", "name": "@deepseek-ai/dsh-tool-skill"},
                     {"id": "edu-mcp", "name": "@deepseek-ai/dsh-mcp-client", "config": {
                         "serverName": "edu", "transport": "stdio", "command": sys.executable,
                         "args": [str(ROOT / "mcp_proxy.py")], "failOnStartupError": True,
                         "toolCallTimeoutMs": 130000, "reconnect": {"enabled": False},
                         "env": {"EDU_MCP_URL": url, "EDU_MCP_TOKEN": "__TOKEN_FROM_ENV__"}}},
                 ]}]
        return json.dumps(rows, ensure_ascii=False).replace('"__TOKEN_FROM_ENV__"', '!!js process.env.EDU_MCP_TOKEN')

    @staticmethod
    def _context(request, snapshot, session, tools=None):
        discovery = {"lookup_status": "unavailable", "candidates": []}
        report_links = {}
        if tools is not None:
            # Authorization precedes every automatic read, just as it does tool calls.
            tools.authorize(request)
            try:
                from .tools import ReportLookup
                discovery = tools.find_report_jobs(ReportLookup())
                report_links = tools.readable_report_links()
            except Exception:
                logger.warning("Report discovery unavailable", exc_info=False)
        active = session.data.get("active_outline")
        history = session.data["history"] or list(snapshot.recent_messages or [])
        data = {
            **(tools.planning_context() if tools is not None else {}),
            "authenticated_role": request.actor_role,
            "scope": {"course_id": request.course_id, "scope_type": request.scope_type, "scope_id": request.scope_id},
            "workspace_context": request.workspace_context.model_dump() if request.workspace_context else None,
            "capability": request.capability.model_dump(),
            "history_reference": [{"role": m.get("role"), "content": str(m.get("content") or "")[:4000]} for m in history[-12:]],
            "memory_reference": snapshot.agent_memory_context,
            "summary_reference": snapshot.summary[:4000],
            "current_outline": session.data["outlines"].get(active),
            "report_jobs": session.data["jobs"],
            "report_discovery": discovery,
            "report_links": report_links,
            "knowledge_plan": session.data.get("knowledge_plan"),
            "action_hint": request.action_hint,
            "current_user_message": request.question,
        }
        return "以下是应用提供的上下文数据。只执行 current_user_message 的当前请求；历史和记忆是参考。直接回应当前教学问题，结尾也不要追加功能菜单或服务推销。\n" + json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _result(request, answer, tools):
        result = {"message": {"role": "assistant", "content": answer},
                  "conversation": {"conversation_id": request.conversation_id},
                  "action": {"name": "chat.reply"}, "artifacts": [], "workflow": None,
                  "sources": [], "trace": {"path": "deepseek-harness", "model_runtime": "dsh",
                    "request_id": request.request_id, "tool_events": tools.outcomes}}
        successful = [item for item in tools.outcomes if item["ok"]]
        for item in successful:
            if item["tool"] in {"rag_search", "web_search"}:
                result["sources"].extend(item["data"]["sources"])
        actions = [item for item in successful if item["tool"] in {"draft_report_outline", "submit_report", "query_report_job", "cancel_report_job"}]
        queried = {item['data']['task_id']: item['data'] for item in actions if item['tool'] == 'query_report_job'}
        if actions and actions[-1]['tool'] == 'query_report_job' and len(queried) > 1:
            # Inspection of several candidates does not select the final one.
            lines = []
            for data in queried.values():
                passed = (data.get('verification') or {}).get('decision') == 'pass'
                label = '已生成并通过模型审阅' if passed else {
                    'succeeded': '已生成，但尚未通过当前交付校验',
                    'failed': '生成失败', 'canceled': '已取消',
                    'queued': '排队中', 'running': '生成中',
                }.get(data['status'], '需要继续核对状态')
                date = str(data.get('created_at') or '')
                lines.append(f"- 《{data.get('title') or '报告'}》{('（' + date + '）') if date else ''}：{label}")
            result['message']['content'] = '查到了多份报告，状态分别是：\n\n' + '\n'.join(lines) + '\n\n你指的是哪一份？'
            return result
        if actions:
            last = actions[-1]
            data = last["data"]
            result["action"] = {"name": "generate.report"}
            if last["tool"] == "draft_report_outline":
                saved_outline = tools.session.data['outlines'].get(data['outline_id'])
                if saved_outline is not None:
                    saved_outline['presented_revision'] = data['revision']
                    saved_outline['presented_request_id'] = request.request_id
                    tools.session.save()
                result["message"]["content"] = data["markdown"] + "\n\n大纲第 " + str(data["revision"]) + " 版。可以提出修改意见，或告诉我按此结构继续。"
                result["workflow"] = {"type": "report", "status": "awaiting_confirm", "stage": "outline"}
                result["harness_outline"] = {k: data[k] for k in ("outline_id", "revision", "subject")}
            elif last["tool"] == "submit_report":
                result["message"]["content"] = "正在生成报告，完成后会在这里显示。"
                result["workflow"] = {"type": "report", "status": "running", "stage": "generating"}
                result["task_id"] = data["task_id"]
            elif last["tool"] == "query_report_job":
                passed = (data.get("verification") or {}).get("decision") == "pass"
                result["message"]["content"] = "报告已生成并通过模型审阅，可查看正文。" if passed else {"queued": "报告正在排队生成。", "submitted": "报告已提交，正在等待生成。", "running": "正在生成报告。", "failed": "报告生成未完成。", "canceled": "报告生成已取消。", "succeeded": "报告已生成，正在核对结果。"}.get(data["status"], "正在处理报告。")
                if data.get("failure_reason"):
                    result["message"]["content"] += data["failure_reason"]
                if data.get("verification") and not passed:
                    result["message"]["content"] += "正文尚未通过审阅或审阅版本已失效，暂不作为完成报告交付。"
                if passed:
                    result["artifacts"] = [data["artifact"]]
                status = "completed" if passed else (
                    "failed" if data.get("verification") or data["status"] in {"failed", "partially_succeeded"}
                    else "interrupted" if data["status"] == "canceled" else "running")
                result["workflow"] = {"type": "report", "status": status, "stage": "result_check"}
                result["verification"] = data.get("verification")
                result["task_id"] = data["task_id"]
            elif last["tool"] == "cancel_report_job":
                result["message"]["content"] = "已提交取消请求。"
                result["workflow"] = {"type": "report", "status": "interrupted", "stage": "cancel_requested"}
                result["task_id"] = data["task_id"]
        return result

    @staticmethod
    def _failure(request, message, code):
        return {"message": {"role": "assistant", "content": message},
                "conversation": {"conversation_id": request.conversation_id},
                "action": {"name": "agent.failed"}, "artifacts": [], "workflow": None, "sources": [],
                "trace": {"path": "deepseek-harness", "error": code}}


def build_harness_runtime():
    from core.config import Config
    from app.chat.harness.content_gateway import build_content_gateway
    from app.chat.tools.agent_tools import rag_search_tool, web_search_tool
    from app.chat.application.knowledge_context import validate_generation_scope, authorize_workspace
    from app.services.generation_command import generation_command_service
    from app.services.job_store import get_job, cancel_job, list_job_page
    from app.chat.runtime.agent_tools.handlers.control import _resolve_course_material

    def factory(**kwargs):
        from core.course_storage import storage_manager
        return ReportTools(**kwargs, course_storage=storage_manager, gateway=build_content_gateway(),
                           submit=generation_command_service.submit, get_job=get_job,
                           cancel_job=cancel_job, read_artifact=_resolve_course_material,
                           list_report_jobs=list_job_page,
                           resolve_report_source=HarnessStore(Config.STORAGE_ROOT / "deepseek_harness").report_source,
                           validate_scope=validate_generation_scope,
                           authorize=lambda request: authorize_workspace(request) if request.course_id else None,
                           rag=rag_search_tool, web=web_search_tool)

    return HarnessRuntime(store=HarnessStore(Config.STORAGE_ROOT / "deepseek_harness"),
                          tool_factory=factory, model=Config.DSH_MODEL,
                          api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_BASE_URL,
                          timeout=Config.DSH_TIMEOUT_SECONDS)
