"""
对话存储模块：使用 JSON 文件永久保存对话及其消息记录
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.config import Config


def _now_iso() -> str:
    return datetime.now().isoformat()


class ConversationStorage:
    """简单的 JSON 文件对话存储"""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = Path(storage_file or Config.CONVERSATIONS_FILE)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -------- 基础读写 --------
    def _load(self):
        if not self.storage_file.exists():
            return
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self._conversations = {}
            return

        conversations = raw
        if isinstance(raw, dict):
            conversations = raw.get("conversations", [])

        if not isinstance(conversations, list):
            conversations = []

        for conv in conversations:
            conv_id = conv.get("conversation_id")
            if conv_id:
                conv.setdefault("messages", [])
                conv["messages"] = [
                    self._normalize_message(message, conversation_id=str(conv_id), index=index)
                    for index, message in enumerate(conv.get("messages", []))
                ]
                conv.setdefault("created_at", _now_iso())
                conv.setdefault("updated_at", conv["created_at"])
                conv.setdefault("title", self._generate_title_from_messages(conv["messages"]))
                conv.setdefault("state", {})
                conv.setdefault("owner", conv.get("owner"))
                self._conversations[conv_id] = conv

    @staticmethod
    def _normalize_message(message: Dict[str, Any], *, conversation_id: str, index: int) -> Dict[str, Any]:
        normalized = dict(message or {})
        normalized.setdefault("timestamp", _now_iso())
        normalized.setdefault("message_id", f"{conversation_id}:msg:{index + 1}")
        normalized.setdefault(
            "message_kind",
            "user_content" if str(normalized.get("role") or "").strip() == "user" else "assistant_content",
        )
        return normalized

    def _save_locked(self):
        payload = {
            "updated_at": _now_iso(),
            "conversations": list(self._conversations.values()),
        }
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # -------- 对话管理 --------
    def _generate_title(self, question: Optional[str]) -> str:
        if question:
            title = question.strip().split("\n")[0]
            return title[:32] + ("…" if len(title) > 32 else "")
        return f"对话 {len(self._conversations) + 1}"

    def _generate_title_from_messages(self, messages: List[Dict[str, Any]]) -> str:
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                return self._generate_title(msg["content"])
        return f"对话 {len(self._conversations) + 1}"

    def ensure_conversation(
        self,
        conversation_id: str,
        first_question: Optional[str] = None,
        owner: Optional[str] = None,
    ):
        with self._lock:
            if conversation_id in self._conversations:
                conv = self._conversations[conversation_id]
                if not conv.get("title") and first_question:
                    conv["title"] = self._generate_title(first_question)
                if owner and not conv.get("owner"):
                    conv["owner"] = owner
                    self._save_locked()
                return

            now = _now_iso()
            self._conversations[conversation_id] = {
                "conversation_id": conversation_id,
                "title": self._generate_title(first_question),
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "state": {},
                "owner": owner,
            }
            self._save_locked()

    def list_conversations(self, owner: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            items = []
            total_messages = 0
            for conv in self._conversations.values():
                if owner and conv.get("owner") != owner:
                    continue
                message_count = len(conv.get("messages", []))
                total_messages += message_count
                items.append(
                    {
                        "conversation_id": conv["conversation_id"],
                        "title": conv.get("title")
                        or self._generate_title_from_messages(conv.get("messages", [])),
                        "created_at": conv.get("created_at"),
                        "updated_at": conv.get("updated_at"),
                        "message_count": message_count,
                    }
                )

            items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
            return {
                "conversations": items,
                "count": len(items),
                "total_messages": total_messages,
            }

    def get_conversation(self, conversation_id: str, owner: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if conversation_id not in self._conversations:
                raise KeyError(conversation_id)
            conv = self._conversations[conversation_id]
            if owner and conv.get("owner") != owner:
                raise KeyError(conversation_id)
            return {
                "conversation_id": conv["conversation_id"],
                "title": conv.get("title"),
                "history": conv.get("messages", []),
                "message_count": len(conv.get("messages", [])),
                "created_at": conv.get("created_at"),
                "updated_at": conv.get("updated_at"),
            }

    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return []
            messages = conv.get("messages", [])
            if limit is not None and limit > 0:
                return messages[-limit:]
            return list(messages)

    def get_state(self, conversation_id: str) -> Dict[str, Any]:
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return {}
            state = conv.get("state") or {}
            return dict(state)

    def update_state(self, conversation_id: str, patch: Dict[str, Any]):
        with self._lock:
            if conversation_id not in self._conversations:
                self.ensure_conversation(conversation_id)
            conv = self._conversations[conversation_id]
            state = conv.setdefault("state", {})
            state.update(patch or {})
            conv["updated_at"] = _now_iso()
            self._save_locked()

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        sources: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
        message_kind: Optional[str] = None,
    ):
        with self._lock:
            if conversation_id not in self._conversations:
                self.ensure_conversation(conversation_id, content if role == "user" else None)
            conv = self._conversations[conversation_id]
            message = {
                "message_id": f"{conversation_id}:msg:{uuid4().hex}",
                "role": role,
                "content": content,
                "timestamp": timestamp or _now_iso(),
                "message_kind": message_kind or ("user_content" if role == "user" else "assistant_content"),
            }
            if sources:
                message["sources"] = sources
            conv.setdefault("messages", []).append(message)
            conv["updated_at"] = _now_iso()
            self._save_locked()

    def delete_conversation(self, conversation_id: str, owner: Optional[str] = None):
        with self._lock:
            if conversation_id in self._conversations:
                if owner and self._conversations[conversation_id].get("owner") != owner:
                    raise KeyError(conversation_id)
                del self._conversations[conversation_id]
                self._save_locked()

    def truncate_messages(self, conversation_id: str, keep_count: int):
        """截断对话消息，只保留前 keep_count 条消息"""
        with self._lock:
            if conversation_id not in self._conversations:
                return
            conv = self._conversations[conversation_id]
            messages = conv.get("messages", [])
            if keep_count < len(messages):
                conv["messages"] = messages[:keep_count]
                conv["updated_at"] = _now_iso()
                self._save_locked()

    def delete_message_pair(self, conversation_id: str, message_index: int):
        """删除指定索引的消息对（用户消息+助手回复）"""
        with self._lock:
            if conversation_id not in self._conversations:
                return
            conv = self._conversations[conversation_id]
            messages = conv.get("messages", [])
            
            if message_index < 0 or message_index >= len(messages):
                return
            
            # 确定要删除的范围
            start_idx = message_index
            end_idx = message_index
            
            # 如果是用户消息，同时删除后面的助手回复
            if messages[message_index].get("role") == "user":
                if message_index + 1 < len(messages) and messages[message_index + 1].get("role") == "assistant":
                    end_idx = message_index + 1
            # 如果是助手消息，同时删除前面的用户问题
            elif messages[message_index].get("role") == "assistant":
                if message_index > 0 and messages[message_index - 1].get("role") == "user":
                    start_idx = message_index - 1
            
            # 删除消息
            conv["messages"] = messages[:start_idx] + messages[end_idx + 1:]
            conv["updated_at"] = _now_iso()
            self._save_locked()

    def update_message(self, conversation_id: str, message_index: int, new_content: str):
        """更新指定索引的消息内容"""
        with self._lock:
            if conversation_id not in self._conversations:
                return
            conv = self._conversations[conversation_id]
            messages = conv.get("messages", [])
            
            if message_index < 0 or message_index >= len(messages):
                return
            
            messages[message_index]["content"] = new_content
            messages[message_index]["timestamp"] = _now_iso()
            conv["updated_at"] = _now_iso()
            self._save_locked()


conversation_storage = ConversationStorage()
