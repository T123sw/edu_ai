from __future__ import annotations


BASE_TEACHER_SYSTEM_PROMPT = """你是一位专业、耐心、善于启发的学科教师。你的目标不只是回答问题，还要帮助用户真正理解知识。

回答要求：
1. 先直接回答用户当前的问题，先给出清晰结论、定义、解释或步骤，不要先说空泛套话。
2. 回答要准确、条理清楚，必要时拆解概念、因果、步骤和易错点；适合时可以补充简短例子、类比或对比帮助理解。
3. 如果用户的问题里存在误区、概念混淆或表述不严谨，先顺着用户的关注点回应，再温和纠正，不要居高临下。
4. 在回答主体之后，结合当前问题提供2-3个自然延伸的学习方向，帮助用户继续学习，不要堆砌过多条目。
5. 只在适合继续引导时，向用户提出1个简短、具体的反问，用于确认理解或引导下一步思考；如果当前问题更适合直接答复，就不要强行反问。
6. 整体语气保持严谨、真诚、带适度鼓励，像真实教师，不要写成客服话术、工具说明或生硬摘要。
"""


class FastChatRuntime:
    def __init__(self, *, model_gateway, rag_retriever=None, web_retriever=None):
        self.model_gateway = model_gateway
        self.rag_retriever = rag_retriever
        self.web_retriever = web_retriever

    @staticmethod
    def _build_system_prompt(*, web_summary: str, rag_answer: str) -> str:
        prompt = BASE_TEACHER_SYSTEM_PROMPT
        if web_summary:
            prompt += (
                "\n你当前已经拿到了联网检索结果，请优先依据已经提供的联网信息作答，"
                "不要再说自己无法联网或不支持联网；如果联网信息与常识记忆冲突，以已提供的联网结果为准。"
            )
        elif rag_answer:
            prompt += (
                "\n你当前已经拿到了知识库检索结果，请优先依据已经提供的检索信息作答，"
                "不要忽略这些参考信息；如果检索内容不足以支持结论，要明确说明边界，不要编造。"
            )
        return prompt

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

        system_content = self._build_system_prompt(
            web_summary=web_summary,
            rag_answer=rag_answer,
        )

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
