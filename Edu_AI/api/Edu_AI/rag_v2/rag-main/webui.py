import streamlit as st
import requests
import re
import json

# 你的 FastAPI 问答接口地址
API_URL = "http://127.0.0.1:8000/api/rag/query_stream"


def render_citation_html(source: str, score: float, text: str) -> str:
    """
    将引用信息转换为可点击的 HTML 链接，使用纯 CSS 实现弹窗（无需 JS）

    Args:
        source: 文件名
        score: 相关性分数
        text: 原文片段

    Returns:
        HTML 字符串
    """
    # 截断过长的文本（弹窗中显示）
    if len(text) > 200:
        text = text[:200] + "..."

    # 使用纯 CSS :hover 实现悬停显示（兼容性更好的方式）
    html = f'''
    <style>
        .citation-{hash(source)}:hover .citation-popup {{
            display: block !important;
        }}
    </style>
    <span class="citation-{hash(source)}" style="display:inline-block; position:relative; margin:0 3px; vertical-align:middle;">
        <a href="#"
           title="来源：{source}\n分数：{score:.2f}"
           style="color:#0366d6; text-decoration:none; cursor:pointer; font-size:0.9em; display:inline-block;">
            📎
        </a>
        <div class="citation-popup" style="display:none; position:absolute; z-index:1000; left:0; top:100%; min-width:250px; max-width:400px; background:#fff; border:1px solid #e1e4e8; border-radius:6px; box-shadow:0 4px 12px rgba(0,0,0,0.15); padding:8px 10px; font-size:0.85em; line-height:1.5; color:#24292e;">
            <div style="font-weight:600; color:#0366d6; margin-bottom:6px; padding-bottom:4px; border-bottom:1px solid #e1e4e8;">
                📄 {source} <span style="float:right; color:#6a737d; font-weight:400;">分数：{score:.2f}</span>
            </div>
            <div style="color:#586069; font-style:italic; max-height:300px; overflow-y:auto;">
                {text}
            </div>
        </div>
    </span>
    '''
    return html


def process_citations(answer: str, sources: list):
    """
    处理回答中的 <cite> 标签，在文末用可展开的 details 标签展示引用信息

    Args:
        answer: LLM 生成的回答（包含 <cite> 标签）
        sources: 参考资料列表

    Returns:
        处理后的文本（移除 cite 标签，在文末添加可展开的参考资料）
    """
    if not sources:
        return answer

    source_map = {}
    for src in sources:
        source_name = src.get('source', '未知')
        score = src.get('rerank_score') or src.get('combined_score') or 0.0
        content = src.get('content', '')
        source_map[source_name] = {'score': score, 'content': content}

    cite_pattern = r'<cite\s+source="([^"]+)"\s+score="([^"]+)">([^<]+)</cite>'

    citations = []
    citation_counter = 0

    def replace_citation(match):
        nonlocal citation_counter
        source = match.group(1)
        score_str = match.group(2)
        cited_text = match.group(3).strip()

        try:
            score = float(score_str)
        except ValueError:
            score = 0.0

        if source in source_map:
            actual_score = source_map[source]['score']
            actual_content = source_map[source]['content']

            import re as regex
            clean_content = actual_content

            repeat_header = r'([\d\.]+\s*[\u4e00-\u9fa5]+[^\n]*)(\s*\n?\s*\1)+'
            clean_content = regex.sub(repeat_header, r'\1', clean_content)

            latex = r'\\(pmb|frac|sqrt|sum|prod|int|left|right|begin|end)\{[^}]*\}'
            clean_content = regex.sub(latex, '', clean_content)

            special = r'[*#=]{3,}'
            clean_content = regex.sub(special, '', clean_content)

            clean_content = regex.sub(r'\s+', ' ', clean_content).strip()

            if len(clean_content) > 200:
                clean_content = clean_content[:200] + "..."

            citations.append({
                'index': citation_counter,
                'source': source,
                'score': actual_score,
                'content': clean_content
            })
        else:
            citations.append({
                'index': citation_counter,
                'source': source,
                'score': score,
                'content': cited_text[:200]
            })

        citation_counter += 1
        # 用上标数字替换 cite 标签
        return f"^{citation_counter}^"

    processed_answer = re.sub(cite_pattern, replace_citation, answer)

    refs_pattern = r'\n?\n?(参考资料 | 参考文献 | References|Sources)[:：]?.*?(?=\n\n|$)'
    processed_answer = re.sub(refs_pattern, '', processed_answer, flags=re.IGNORECASE | re.DOTALL)

    # 如果有引用，在文末添加可展开的参考资料列表
    if citations:
        processed_answer += "\n\n---\n\n### 📚 参考资料\n"
        for cit in citations:
            # 使用 HTML details 标签实现可展开效果
            processed_answer += f"""
<details style="margin: 8px 0; padding: 8px 12px; background: #f6f8fa; border-left: 3px solid #0366d6; border-radius: 4px;">
<summary style="cursor: pointer; font-weight: 600; color: #0366d6;">
📄 {cit['source']} (相关性：{cit['score']:.2f})
</summary>
<div style="margin-top: 8px; padding: 8px; background: white; border-radius: 3px; color: #24292e; font-size: 0.9em; line-height: 1.5;">
<strong>原文内容：</strong><br>
{cit['content']}
</div>
</details>
"""

    return processed_answer

st.set_page_config(page_title="考研数据结构 AI 助教", page_icon="🤖", layout="wide")

st.title("🤖 考研数据结构 AI 助教")
st.caption("基于 RAG 技术的智能问答系统 | 支持流式输出和多模态内容（图片/视频）")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # 处理引用标签并渲染 Markdown（包含图片和视频）
            processed_content = process_citations(message["content"], message.get("sources", []))
            st.markdown(processed_content, unsafe_allow_html=True)

            # 显示检索指标
            retrieval_metrics = message.get("retrieval_metrics")
            if retrieval_metrics:
                with st.expander("📊 检索质量评估"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("最高分", f"{retrieval_metrics.get('max_score', 0):.2f}")
                    with col2:
                        st.metric("平均分", f"{retrieval_metrics.get('avg_score', 0):.2f}")
                    with col3:
                        st.metric("文档数", retrieval_metrics.get('doc_count', 0))
        else:
            st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 显示助手回复（流式）
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        sources = []
        retrieval_metrics = {}

        try:
            # 构建请求数据
            conversation_history = []
            for msg in st.session_state.messages[:-1]:  # 排除刚添加的用户消息
                if msg["role"] in ["user", "assistant"]:
                    conversation_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            payload = {
                "question": prompt,
                "top_k": 5,
                "use_enhanced_retrieval": True,
                "hyde_weight": 0.5,
                "use_rrf": True,
                "conversation_history": conversation_history
            }

            # 流式请求
            with requests.post(API_URL, json=payload, stream=True, timeout=300) as response:
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str.strip() == '[DONE]':
                                    break

                                try:
                                    data = json.loads(data_str)

                                    if data.get('type') == 'metadata':
                                        # 接收元数据
                                        sources = data.get('sources', [])
                                        retrieval_metrics = data.get('retrieval_metrics', {})

                                    elif data.get('type') == 'content':
                                        # 接收内容流
                                        chunk = data.get('content', '')
                                        full_response += chunk
                                        # 实时显示（Markdown 会自动渲染图片和视频）
                                        processed = process_citations(full_response, sources)
                                        message_placeholder.markdown(processed + "▌", unsafe_allow_html=True)

                                except json.JSONDecodeError:
                                    continue

                    # 最终显示
                    processed_response = process_citations(full_response, sources)
                    message_placeholder.markdown(processed_response, unsafe_allow_html=True)

                    # 显示检索指标
                    if retrieval_metrics:
                        with st.expander("📊 检索质量评估"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("最高分", f"{retrieval_metrics.get('max_score', 0):.2f}")
                            with col2:
                                st.metric("平均分", f"{retrieval_metrics.get('avg_score', 0):.2f}")
                            with col3:
                                st.metric("文档数", retrieval_metrics.get('doc_count', 0))

                    # 保存到会话
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_response,
                        "sources": sources,
                        "retrieval_metrics": retrieval_metrics
                    })
                else:
                    st.error(f"后端报错！状态码: {response.status_code}")

        except Exception as e:
            st.error(f"连接后端失败: {e}")

