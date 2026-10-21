"""Make consecutive listening samples without normalizing or changing pitch."""
import html
import json
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

root = Path(__file__).resolve().parent
results = json.loads((root / 'results.json').read_text())
cloud = json.loads((root / 'cloud.json').read_text())
texts = json.loads((root / 'texts.json').read_text())
groups = {
    'A_official': 'A · 官方默认采样，无风格指令',
    'B_official_with_instruction': 'B · 官方默认采样，加当前风格指令',
    'C_current_raw': 'C · 当前风格与采样，变调前',
    'D_current_aligned': 'D · 与 C 同一份音频，经过当前变调',
    'E_cloud': 'E · 当前云端模型与音色',
}
cards = []
for key, label in groups.items():
    waves = []
    for i in range(len(texts)):
        source = root / f'{key}-{i}.wav'
        if key == 'E_cloud':
            data = subprocess.check_output(['/usr/bin/ffmpeg', '-v', 'error', '-i',
                str(root / f'{key}-{i}.mp3'), '-f', 'f32le', '-ar', '24000', '-ac', '1', '-'])
            wave = np.frombuffer(data, dtype='<f4')
        else:
            wave, sr = sf.read(source, dtype='float32')
            assert sr == 24000
        if i:
            waves.append(np.zeros(14400, dtype='float32'))
        waves.append(wave)
    target = root / f'{key}-joined.mp3'
    subprocess.run(['/usr/bin/ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', '24000',
        '-ac', '1', '-i', 'pipe:0', '-codec:a', 'libmp3lame', '-b:a', '192k', str(target)],
        input=np.concatenate(waves).astype('<f4').tobytes(), check=True)
    subprocess.run(['/usr/bin/ffmpeg', '-v', 'error', '-i', str(target), '-f', 'null', '-'], check=True)
    timing = next((f"模型生成耗时 {r['generation_seconds']:.1f} 秒" for r in results['runs'] if r['group'] == key), '')
    if key == 'D_current_aligned':
        timing = '使用 C 的原始波形，单独比较后处理影响'
    if key == 'E_cloud':
        timing = f"两路云端请求完成耗时 {cloud['batch_seconds']:.1f} 秒；模型、音色均与本地不同"
    cards.append(f'<section><h2>{html.escape(label)}</h2><p>{timing}</p>'
                 f'<audio controls preload="none" src="{target.name}"></audio>'
                 f'<p><a href="{target.name}" download>下载连续试听音频</a></p></section>')
body = '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
body += '<title>TTS 对照试听</title><style>body{font:17px/1.7 system-ui;max-width:850px;margin:36px auto;padding:0 20px;color:#202734;background:#f5f7fa}section{padding:20px;margin:16px 0;background:white;border:1px solid #dde3ec;border-radius:12px}h2{font-size:20px}audio{width:100%}a{color:#145ac4}</style>'
body += '<h1>TTS 对照试听</h1><p>同样两段完整播客文本，各组依次播放，段间仅加入 0.6 秒静音；没有额外响度归一或变速。比较 A/B 看风格指令，B/C 看采样方式，C/D 看变调影响。E 是云端体验基准，不能单独用于判断参数因果。</p>'
body += '<p>本次只有一批、两段文本。音高统计不能证明音色是否一致，未进行人工听感评定或说话人相似度评测。线上保持云端。</p>'
body += ''.join(cards)
body += '<details><summary>完整测试文本</summary>' + ''.join('<p>'+html.escape(t['text'])+'</p>' for t in texts) + '</details></html>'
(root / 'listen.html').write_text(body)
print('Five listening samples built and decoded successfully.')
