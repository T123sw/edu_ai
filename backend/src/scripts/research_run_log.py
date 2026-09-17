"""Opt-in local audit artifacts for real-provider research smoke runs."""
import html
import json
import time
from datetime import datetime, timezone
from pathlib import Path


class RunLog:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.sequence = 0
        self.snapshots = 0

    def event(self, kind, **data):
        self.sequence += 1
        value = {'sequence': self.sequence, 'at': datetime.now(timezone.utc).isoformat(),
                 'elapsed_seconds': round(time.monotonic() - self.started, 2), 'event': kind, **data}
        with (self.directory / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        print(f'[{value["elapsed_seconds"]:7.2f}s] {kind} {data.get("tool", data.get("phase", ""))}', flush=True)

    def checkpoint(self, request, state, *, status='running', error=None):
        self.snapshots += 1
        value = {'request': request.model_dump(mode='json'), 'state': state.model_dump(mode='json'),
                 'status': status, 'error': error, 'course_ready': False,
                 'elapsed_seconds': round(time.monotonic() - self.started, 2)}
        name = f'{self.snapshots:03d}-call-{state.calls:02d}-{state.phase}.json'
        (self.directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))
        self.event('checkpoint', phase=state.phase, call=state.calls, status=status, artifact=name,
                   validation_error={k: v for k, v in (state.last_error or {}).items() if k != 'arguments'})
        for key in ('brief', 'summary', 'path', 'review'):
            artifact = getattr(state, key)
            if artifact is not None:
                (self.directory / f'{key}.json').write_text(artifact.model_dump_json(indent=2))
        self.report(value)

    def report(self, value):
        state = value['state']
        esc = html.escape
        def block(title, data):
            return f'<details><summary>{esc(title)}</summary><pre>{esc(json.dumps(data, ensure_ascii=False, indent=2))}</pre></details>'
        nodes = (state.get('path') or {}).get('nodes', [])
        rows = ''.join(f'<tr><td>{i}</td><td>{esc(n["title"])}</td><td>{n["minutes"]}</td><td>{esc(", ".join(n["prerequisite_keys"]) or "无")}</td></tr>' for i,n in enumerate(nodes,1))
        sections = ''.join(block(title, state[key]) for title,key in [('意图与约束','brief'),('搜索候选','candidates'),('已读正文与来源','evidence'),('研究汇总与引用','summary'),('完整学习路径、活动与自测','path'),('独立审阅','review'),('工具轨迹','trace'),('最近错误与修正输入','last_error')])
        content = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>课程研究 Agent 执行记录</title>
<style>body{{font-family:system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#203040;background:#fafbfc}}h1{{font-size:28px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #ddd}}details{{background:white;padding:16px;margin:14px 0;border:1px solid #ddd;border-radius:8px}}summary{{cursor:pointer;font-weight:600}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}.meta{{padding:16px;background:#e8f0ff}}</style>
<h1>课程研究 Agent：执行记录与学习路径</h1><p>{esc(value['request']['goal'])}</p>
<p class="meta">状态：{esc(value['status'])} · 阶段：{state['phase']} · 耗时：{value['elapsed_seconds']} 秒 · 模型决策：{state['calls']} · 搜索：{state['searches']} · 正文片段：{len(state['evidence'])} · 路径总时长：{sum(n['minutes'] for n in nodes)} 分钟</p>
<p>本记录使用真实模型和检索服务；结果为研究与学习路径，课程资源尚未生成。展开下方项目查看中间产物。</p>
<p><a href="events.jsonl">按时间排列的详细日志</a> · <a href="path.json">学习路径 JSON（产出后可用）</a></p>
<table><thead><tr><th>顺序</th><th>知识节点</th><th>分钟</th><th>先修节点</th></tr></thead><tbody>{rows}</tbody></table>
{block('运行错误', value['error']) if value['error'] else ''}{sections}</html>'''
        temporary = self.directory / 'report.html.tmp'
        temporary.write_text(content)
        temporary.replace(self.directory / 'report.html')

        lines = ['# 课程研究 Agent 执行记录', '',
                 f"状态：{value['status']}；阶段：{state['phase']}；耗时：{value['elapsed_seconds']} 秒。", '',
                 value['request']['goal'], '',
                 f"模型决策 {state['calls']} 次；搜索 {state['searches']} 次；已读 {len(state['evidence'])} 段正文。", '',
                 '## 中间产物与日志', '',
                 '- [完整时间线日志](events.jsonl)',
                 '- [意图与需求约束](brief.json)', '- [研究汇总和逐条引用](summary.json)',
                 '- [学习路径 JSON](path.json)', '- [独立审阅](review.json)',
                 '- [交互展开报告（含正文与工具轨迹）](report.html)', '',
                 '目录中的 NNN-call-NN-阶段.json 保存每步状态；尚未产生的阶段文件暂不存在。', '',
                 '## 资料来源', '']
        for evidence in state['evidence']:
            lines.append(f"- [{evidence['title']}]({evidence['url']})：偏移 {evidence['offset_chars']}，证据 ID `{evidence['source_id']}`。")
        if state.get('summary'):
            lines += ['', '## 研究汇总', '', state['summary']['overview'], '']
            for finding in state['summary']['findings']:
                lines.append(f"- {finding['finding_id']}：{finding['claim']}")
        lines += ['', '## 学习路径', '']
        for index, node in enumerate(nodes, 1):
            lines += [f"### {index}. {node['title']}（{node['minutes']} 分钟）", '',
                      '先修：' + (', '.join(node['prerequisite_keys']) or '无'), '',
                      '目标：' + '；'.join(node['objectives']), '', '学习活动：', '']
            lines.extend('- ' + item for item in node['learning_activities'])
            lines += ['', '自测：' + node['self_check'], '']
        lines += [f"总时长：{sum(n['minutes'] for n in nodes)} 分钟。", '',
                  '说明：这是研究与学习路径产物，尚未生成完整教学资源。']
        if value['error']:
            lines += ['', '本次失败：' + value['error']]
        (self.directory / 'report.md').write_text('\n'.join(lines) + '\n')

    def model(self, wrapped):
        log = self
        class LoggedModel:
            def decide(self, context, tools, **kwargs):
                log.event('model_requested', phase=context['phase'], call=context['calls'],
                          mounted_tools=[t['function']['name'] for t in tools])
                try:
                    name, arguments = wrapped.decide(context, tools, **kwargs)
                except Exception as exc:
                    log.event('model_error', error_type=type(exc).__name__, message=str(exc)[:1600])
                    raise
                log.event('tool_selected', tool=name, arguments=arguments)
                return name, arguments
        return LoggedModel()

    def sources(self, wrapped):
        log = self
        class LoggedSources:
            def search(self, query, **kwargs):
                log.event('search_started', query=query)
                result = wrapped.search(query, **kwargs)
                log.event('search_completed', query=query, candidates=result)
                return result
            def read(self, url, **kwargs):
                log.event('source_read_started', url=url)
                result = wrapped.read(url, **kwargs)
                log.event('source_read_completed', url=url, extracted_chars=len(result))
                return result
        return LoggedSources()
