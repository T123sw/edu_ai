from __future__ import annotations


class FastChatRuntime:
    def __init__(self, *, model_gateway, rag_retriever=None, web_retriever=None):
        self.model_gateway = model_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever

    def run(self, *, request, snapshot, decision):
        recent_messages = list(getattr(snapshot, "recent_messages", []) or []) if snapshot is not None else []
        capability = getattr(request, "capability", None)
        sources = []
        context_blocks = []
        web_summary = ""
        rag_answer = ""
        web_trace = {}

        if self.rag_retriever is not None and bool(getattr(capability, "allow_rag", False)):
            rag_result = self.rag_retriever(
                query=request.question,
                top_k=5,
                selected_doc_ids=list(getattr(capability, "selected_doc_ids", []) or []),
                owner=getattr(request, "owner", None),
            )
            payload = dict((rag_result or {}).get("payload") or {}) if isinstance(rag_result, dict) else {}
            rag_sources = list(payload.get("sources") or [])
            rag_answer = str(payload.get("answer") or "").strip()
            if rag_answer:
                context_blocks.append(f"以下是知识库检索到的参考信息，请优先基于这些内容回答：\n{rag_answer}")
            sources.extend(rag_sources)

        if self.web_retriever is not None and bool(getattr(capability, "allow_web", False)):
            web_result = self.web_retriever(
                query=request.question,
                owner=getattr(request, "owner", None),
            )
            payload = dict((web_result or {}).get("payload") or {}) if isinstance(web_result, dict) else {}
            web_sources = list(payload.get("sources") or [])
            web_summary = str(payload.get("summary") or payload.get("answer") or "").strip()
            web_trace = dict(payload.get("trace") or {})
            if web_summary:
                context_blocks.append(f"以下是联网检索到的参考信息，请结合这些内容回答：\n{web_summary}")
            sources.extend(web_sources)

        user_content = request.question
        if context_blocks:
            user_content = "\n\n".join([*context_blocks, f"用户问题：{request.question}"])

        system_content = "你是教学对话助手，请提供准确、清晰、可执行的回答。"
        if web_summary:
            system_content += "\n你当前已经拿到了联网检索结果，请直接基于这些联网结果回答，不要再说自己无法联网或不支持联网。"
        elif rag_answer:
            system_content += "\n你当前已经拿到了知识库检索结果，请优先基于检索结果回答，不要忽略这些参考信息。"

        messages = [
            {"role": "system", "content": system_content},
            *recent_messages,
            {"role": "user", "content": user_content},
        ]
        answer = self.model_gateway.chat(messages)
        action_name = getattr(decision, "action", "chat.reply") if decision is not None else "chat.reply"
        trace = {
            "path": "fast",
            "rag_used": bool(getattr(capability, "allow_rag", False) and self.rag_retriever is not None),
            "web_used": bool(getattr(capability, "allow_web", False) and self.web_retriever is not None),
        }
        if web_trace:
            trace.update(web_trace)
        if sources and trace.get("web_used"):
            trace["web_sources_count"] = len(sources)

        return {
            "message": {"role": "assistant", "content": answer},
            "conversation": {"conversation_id": getattr(request, "conversation_id", "") or ""},
            "action": {"name": action_name},
            "artifacts": [],
            "workflow": None,
            "sources": sources,
            "trace": trace,
        }
