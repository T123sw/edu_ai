from src.o_agent import get_agent
from langchain_deepseek import ChatDeepSeek
llm = ChatDeepSeek(model='deepseek-chat', temperature=0.4)
sub_agent = get_agent('sub_agent', llm, [])


