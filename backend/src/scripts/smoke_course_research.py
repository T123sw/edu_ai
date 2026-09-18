"""Run the real research/path agent without writing to the application database.

From backend/src: python -m scripts.smoke_course_research --goal '理解递归' --output /tmp/research.json
"""
import argparse
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from uuid import uuid4

from dotenv import load_dotenv

from app.chat.model_gateway import ChatModelGateway
from app.course_preparation.model_adapter import ResearchModelAdapter
from app.course_preparation.research_agent import ResearchAgent
from app.course_preparation.research_contracts import ResearchRequest, ResearchState
from app.course_preparation.research_sources import ResearchSources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--goal', required=True)
    parser.add_argument('--minutes', type=int, default=60)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--log-dir', type=Path, help='新建目录：详细日志、逐步检查点与 HTML 报告')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[3] / '.env', override=False)
    candidates = [{
        'api_base': os.getenv('ANSWER_LLM_API_BASE', os.getenv('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')),
        'api_key': os.getenv('ANSWER_LLM_API_KEY', os.getenv('QWEN_API_KEY', '')),
        'model_name': os.getenv('COURSE_RESEARCH_MODEL', os.getenv('ANSWER_LLM_MODEL', os.getenv('VISION_MODEL_ID', 'qwen3.5-plus'))),
    }]
    if os.getenv('DEEPSEEK_API_KEY'):
        candidates.append({'api_base': os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
                           'api_key': os.environ['DEEPSEEK_API_KEY'],
                           'model_name': os.getenv('DSH_MODEL', 'deepseek-v4-flash')})
    gateway = SimpleNamespace(candidates=candidates,
        _thinking_params=ChatModelGateway._thinking_params, _build_headers=ChatModelGateway._build_headers)
    agent = ResearchAgent(model=ResearchModelAdapter(gateway), sources=ResearchSources(
        tavily_key=os.getenv('TAVILY_API_KEY', ''), bocha_key=os.getenv('BOCHA_API_KEY', ''),
        tavily_base=os.getenv('TAVILY_BASE_URL', 'https://api.tavily.com')))
    request = ResearchRequest(request_id=uuid4(), goal=args.goal, overrides={'total_minutes': args.minutes})
    state = ResearchState()
    from scripts.research_run_log import RunLog
    audit = RunLog(args.log_dir) if args.log_dir else None
    if audit:
        agent.model = audit.model(agent.model)
        agent.sources = audit.sources(agent.sources)
        audit.event('run_started', request=request.model_dump(mode='json'))
    start = time.monotonic()

    def save(value):
        nonlocal state
        state = value
        if audit:
            audit.checkpoint(request, value)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'purpose': 'research_learning_path', 'course_ready': False,
            'request': request.model_dump(mode='json'), 'elapsed_seconds': round(time.monotonic() - start, 2),
            'state': value.model_dump(mode='json')}, ensure_ascii=False, indent=2))

    try:
        while state.phase != 'done':
            remaining = 600 - (time.monotonic() - start)
            if remaining <= 0:
                raise TimeoutError('research deadline exceeded')
            state = agent.step(request, state, timeout=min(90, remaining), reserve=save)
            save(state)
            print(f'phase={state.phase} calls={state.calls} sources={len(state.evidence)} '
                  f'error={state.last_error["code"] if state.last_error else "none"}', flush=True)
    except Exception as exc:
        if audit:
            audit.event('run_failed', error_type=type(exc).__name__, message=str(exc)[:1600])
            audit.checkpoint(request, state, status='failed', error=str(exc)[:1600])
        raise
    if audit:
        audit.event('run_succeeded', nodes=len(state.path.nodes))
        audit.checkpoint(request, state, status='succeeded')
    print(f'path_nodes={len(state.path.nodes)} review={state.review.decision} output={args.output}', flush=True)


if __name__ == '__main__':
    main()
