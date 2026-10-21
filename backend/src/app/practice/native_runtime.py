"""Package native Tailwind/KaTeX dependencies without network access in the iframe."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
import re

from .runtime import BRIDGE, CSP

ROOT = Path(__file__).resolve().parents[4]


def inline_script(source):
    return '<script>' + re.sub(r'</script', r'<\\/script', source, flags=re.I) + '</script>'


@lru_cache(maxsize=1)
def assets():
    modules = ROOT / 'frontend/node_modules'
    katex = modules / 'katex/dist'
    paths = [modules / '@tailwindcss/browser/dist/index.global.js', katex / 'katex.min.js', katex / 'contrib/auto-render.min.js']
    if not all(path.is_file() for path in paths):
        raise RuntimeError('原生实验运行库缺失，请在 frontend 执行 pnpm install --frozen-lockfile')
    css = (katex / 'katex.min.css').read_text()

    def embed_font(match):
        # Use one WOFF2 source per font instead of embedding all three formats.
        filename = re.search(r'url\((?:[\'\"])?(fonts/[^)\'\"]+\.woff2)', match[0])
        if not filename:
            raise RuntimeError('KaTeX 字体资源格式不受支持')
        encoded = base64.b64encode((katex / filename[1]).read_bytes()).decode()
        return 'src:url(data:font/woff2;base64,' + encoded + ') format("woff2")'

    css = re.sub(r'src:[^;}]+', embed_font, css)
    return '<style data-maic-katex>' + css + '</style>' + ''.join(inline_script(path.read_text()) for path in paths)


def wrap_native_html(raw, guidance=None, experiment=None, stage_page=None):
    start = re.search(r'<!doctype\s+html|<html\b', raw, re.I)
    end = raw.lower().rfind('</html>')
    if not start or end < 0 or len(raw) > 400000:
        raise ValueError('原生引擎没有返回完整的实验页面')
    html = raw[start.start():end + 7]
    if not re.search(r'<head(?:\s[^>]*)?>', html, re.I):
        raise ValueError('实验页面缺少 head')
    # Native CDN references are replaced by installed, pinned libraries. Unknown
    # resources fail explicitly instead of silently shipping a broken page.
    def script(match):
        tag = match[0]
        src = re.search(r'\bsrc\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag.split('>', 1)[0], re.I)
        if not src:
            return tag
        url = next(value for value in src.groups() if value is not None)
        if re.fullmatch(r'https://(?:cdn\.tailwindcss\.com(?:/[\d.]+)?|cdn\.jsdelivr\.net/npm/(?:@tailwindcss/browser@[\d.]+(?:/dist/index\.global\.js)?|katex@[\d.]+/dist/(?:katex\.min\.js|contrib/auto-render\.min\.js)))', url):
            return ''
        raise ValueError('实验引用了未打包的脚本，请仅使用已提供的 Tailwind、KaTeX 和原生绘图')
    html = re.sub(r'<script\b[^>]*>.*?</script\s*>', script, html, flags=re.I | re.S)
    def link(match):
        if re.search(r'https://cdn\.jsdelivr\.net/npm/katex@[\d.]+/dist/katex\.min\.css', match[0]):
            return ''
        raise ValueError('实验引用了未打包的样式或字体，请使用内联 CSS 和系统字体')
    html = re.sub(r'<link\b[^>]*>', link, html, flags=re.I)
    # The sandbox's policy is host-owned; generated policies/base URLs cannot
    # disable the packaged dependencies or redirect resource resolution.
    html = re.sub(r'<meta\b[^>]*http-equiv\s*=\s*[\'\"]?(?:refresh|content-security-policy)\b[^>]*>', '', html, flags=re.I)
    html = re.sub(r'<base\b[^>]*>', '', html, flags=re.I)
    html = html.replace('trust: true', 'trust: false')
    step_bridge = inline_script("EduPractice.selectStep=index=>{if(Number.isInteger(index)&&index>=0&&index<5)parent.postMessage({type:'edu-practice-step',step:index},'*')};")
    head = '<meta http-equiv="Content-Security-Policy" content="' + CSP + '">' + BRIDGE + step_bridge + assets()
    if experiment:
        import json
        from .experiment.bundle import bundle
        head += inline_script("window.__experimentSpec=" + json.dumps(experiment["spec"], ensure_ascii=False).replace("<", "\\u003c") + ";window.__experimentRevision=" + json.dumps(experiment["revision"]) + ";") + inline_script(bundle().read_text())
    if stage_page:
        import json
        from .pages.bundle import bundle
        from .pages.contracts import page_spec
        stage_page = {**stage_page, 'spec': page_spec(stage_page['spec'], stage_page['phase'])}
        head += inline_script('window.__stagePage=' + json.dumps(stage_page, ensure_ascii=False).replace('<', '\\u003c') + ';') + inline_script(bundle().read_text())
    if guidance:
        import json
        from .guidance.bundle import bundle
        head += inline_script('window.__practiceManifest=' + json.dumps(guidance, ensure_ascii=False) + ';') + inline_script(bundle('runtime').read_text())
    return re.sub(r'(<head(?:\s[^>]*)?>)', lambda match: match[0] + head, html, count=1, flags=re.I)
