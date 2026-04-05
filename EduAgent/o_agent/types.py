from typing import TypedDict, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from .token_counter import count_langchain_messages


def add_tuple_messages(
        old: List[tuple],
        new: List[tuple]|tuple,
)->List[tuple]:


    messages = []
    for m in old:
        messages.append(m)

    if isinstance(new, tuple):
        messages.append(new)
        return messages
    for m in new:
        messages.append(m)
    return messages

def add_count(
        old: int,
        new: int,
)->int:
    return old + new


class Tokenizer(BaseModel):
    messages: List[BaseMessage] = []
    count: int = 0

    def update(self, messages: List[BaseMessage]) -> None:
        self.count += count_langchain_messages(messages)


class State(TypedDict):
    messages: Annotated[List[tuple],add_tuple_messages]
    current_message: BaseMessage
    step: int
    response: str|None
    thought: str|None
    count: Annotated[int,add_count]


class Thought(BaseModel):
    thought: str = Field(description='你对于现在要做什么的思考',)

