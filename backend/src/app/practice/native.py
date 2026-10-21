"""MAIC-UI native generators, with a provider and storage boundary for Edu_AI.

The complete upstream checkout stays unmodified. Generation, prompt assembly,
themes, extraction, metadata, and formula postprocessing execute upstream code.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
import threading
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
REVISION = 'aad58ddcc2103058b4c2deffc48a3c13e2c64dd6'
PRESENTATION = 'maic-ui-native-v1'
_load_lock = threading.RLock()

# Keep the native layout and typography. This contract only specifies the host
# bridge, packaged dependencies, and concrete rendering/interaction guarantees.
INTEGRATION = '''
【Edu_AI 运行环境适配】
保留上文的完整原生实验页面、过程面板、交互同步和视觉设计，不限制代码行数。
宿主已提供 Tailwind 浏览器版 4、KaTeX 公式渲染及 window.EduPractice，不要自行下载资源。
使用 Tailwind 默认工具类及普通 CSS；自定义主题用 CSS，不使用 tailwind.config。
允许 LaTeX 公式。不要引用 CDN、外部字体或其他第三方库，不发起网络请求。
canvas 必须按 CSS 尺寸×devicePixelRatio 设置位图尺寸，绘制使用 CSS 坐标。
逻辑高度保存为常量或单独变量，不得从已放大的 canvas.height 再乘像素密度。
用 ResizeObserver 监听容器宽度并重绘；反复缩放和重置不得累积放大或清空图像。
正文16px，图表标签至少13px，主图至少260px高；手机宽度360px时标签仍可辨认。
每个参数控件标记唯一 data-param 并配可见 label。运行按钮 data-action="run"，
暂停按钮 data-action="pause"，重置按钮 data-action="reset"；算法单步按钮 data-action="step"。
初始化、参数改变、运行和每个关键步骤后调用 EduPractice.report({中文结果名:实际值})。
宿主会合并消息，不要自行节流丢弃最后一次更新。不要重定义 EduPractice。
统计必须对应当前已执行步骤，不能提前显示最终结果。
如果预计算算法动画，必须在数组副本上生成动作序列；显示数组仅由逐步执行动作修改，不能提前排序后再重复交换。
执行交换或基准归位动作时，必须真实更新显示数组，再更新计数、绘图和上报；只改变颜色或计数而数组不变是错误实现。
绘图与窗口缩放函数必须只读取状态，不得重复执行交换。排序结束显示数组必须与初始数组的正确排序结果一致。
教学操作步骤与实际控件一致；选择基准、比较、交换、归位应有不同可见状态。
原生过程步骤与输入 key_steps 保持一一对应，传给宿主的步骤序号也使用这个顺序。
动画可暂停、重置，重置取消旧动画并恢复初始参数与结果。每次用户手动切换教学步骤时
可以调用 EduPractice.selectStep(从0开始的步骤序号)，不以步骤切换宣称掌握。
已有科学约束与教学步骤必须保留。只返回完整 HTML。
'''


class NoSharedCache:
    """Never serve one learner's generated HTML as another learner's fallback."""
    def get_cached(self, *_):
        return None

    def save_success(self, *_):
        return False


@lru_cache(maxsize=1)
def load_native():
    with _load_lock:
        checkout = ROOT / '.runtime/maic-ui-native'
        if not (checkout / 'backend/src/services/ai_processor.py').is_file():
            raise RuntimeError('请先运行 scripts/install-maic-ui.py 安装完整 MAIC-UI 原生仓库')
        actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != REVISION:
            raise RuntimeError('MAIC-UI 原生仓库版本不匹配，请运行安装脚本')
        if subprocess.run(['git', '-C', str(checkout), 'diff', '--quiet', 'HEAD', '--', 'backend/src/services']).returncode:
            raise RuntimeError('MAIC-UI 原生模块存在未记录的修改，请恢复固定版本后重试')
        # Independent package namespace avoids collisions with Edu_AI services.
        name = '_edu_maic_native'
        package = ModuleType(name)
        package.__path__ = [str(checkout / 'backend/src')]
        sys.modules[name] = package
        processor = importlib.import_module(name + '.services.ai_processor')
        generation = importlib.import_module(name + '.services.html_generation')
        cache = importlib.import_module(name + '.services.html_generation.cache')
        cache._cache_instance = NoSharedCache()
        return SimpleNamespace(processor=processor, generation=generation)


class PlatformProvider:
    """Translate native provider calls into the existing per-user model gateway."""
    backend = 'zhipu'
    text_model = 'edu-ai-configured-model'

    def __init__(self, complete, owner, context, guidance=None, experiment=None, page_instructions=None):
        self.complete, self.owner, self.context = complete, owner, context
        self.guidance = guidance
        self.experiment = experiment
        self.page_instructions = page_instructions
        self.page_system = None
        self.phase = 'science'
        self.calls = []

    def get_provider_name(self):
        return 'Edu_AI configured gateway'

    def _map_grade_level_to_string(self, grade_level):
        return '入门学习者'

    async def _run_zhipu_call(self, *, messages, thinking_params=None, **_):
        if self.context.is_cancel_requested():
            raise asyncio.CancelledError('实验生成已取消')
        html = self.phase != 'science' and (thinking_params or {}).get('type') == 'enabled'
        prompt = '\n'.join(str(message['content']) for message in messages)
        if html:
            if self.page_instructions is not None:
                prompt += self.page_instructions
            elif self.experiment:
                from .experiment.generation import integration
                prompt += integration(self.experiment)
            else:
                prompt += INTEGRATION
            if self.guidance:
                from .guidance.generation import integration
                prompt += integration(self.guidance)
        self.calls.append({'stage': self.phase if html else 'science' if self.phase == 'science' else 'metadata',
                           'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()})
        options = {'system': self.page_system} if html and self.page_system else {}
        content = await self.complete(self.owner, prompt, tokens=24000 if html else 5000, **options)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def generate_native(plan, context, complete):
    native = load_native()
    provider = PlatformProvider(complete, context.owner_user_id, context, plan.get("guidance"), plan.get("experiment"))
    context.progress(24, 'practice_science', '正在用原生引擎建立实验模型')
    science = await native.processor.ScientificEngine(provider).run(plan)
    if not all(getattr(science, key) for key in ('core_formulas', 'mechanism', 'constraints', 'forbidden_errors')):
        raise ValueError('原生科学建模未返回完整约束，未交付实验')
    scientific_data = json.loads(science.raw_analysis[science.raw_analysis.find('{'):science.raw_analysis.rfind('}') + 1])

    class IntegratedHeavyGenerator(native.generation.HeavyGenerator):
        async def _generate_aligned_simulation(self, context_data):
            provider.phase = 'interaction'
            context.progress(42, 'practice_native_interaction', '正在生成原生步骤与交互模拟')
            return await super()._generate_aligned_simulation(context_data)

        async def _polish_layout_and_visuals(self, context_data):
            provider.phase = 'polish'
            context.progress(64, 'practice_native_polish', '正在优化实验布局、可读性与交互反馈')
            return await super()._polish_layout_and_visuals(context_data)

    analysis = {
        'title': plan['concept_name'], 'subject_area': plan['subject'],
        'main_topics': [plan['concept_name']], 'key_concepts': [plan['concept_name']],
        'learning_objectives': [plan['mastery_points']],
        'procedural_concepts': [{
            'name': plan['concept_name'], 'description': plan['concept_overview'],
            'design_idea': plan['design_idea'], 'key_steps': plan['steps'],
            'scientific_model': scientific_data,
        }],
    }
    result = await IntegratedHeavyGenerator(provider).generate([], analysis, {
        'language': 'zh-CN', 'grade_level': 10, 'include_exercises': False,
    })
    info = result.get('generation_info', {})
    if info.get('fallback_used') or info.get('stages_completed') != 2:
        raise ValueError('原生实验生成或视觉润色未完成，未发布降级占位页面')
    return {**result, 'science': scientific_data, 'native_calls': provider.calls}


def postprocess_native(raw):
    """Run upstream formula postprocessing before packaging runtime resources."""
    return load_native().processor.PostProcessor.run(raw)
