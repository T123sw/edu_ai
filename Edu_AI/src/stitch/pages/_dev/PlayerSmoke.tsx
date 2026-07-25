import type { Slide } from '@openmaic/renderer';
import type { Action } from '@openmaic/dsl';
import katex from 'katex';
import { SlidePlayer } from '../../../openmaic/SlidePlayer';

/**
 * Dev-only smoke test for the Phase 3 player (SPEC-08 §6 / ACC-08 §3.2).
 * Not linked from any nav — reachable at `#player-smoke` during development.
 *
 * Action order note: the fixture is `[spotlight, speech]`, not
 * `[speech, spotlight]`. Fire-and-forget actions (spotlight/laser) resolve
 * immediately and don't block the timeline (ported faithfully from
 * OpenMAIC's `lib/action/engine.ts`/`lib/playback/engine.ts` — see
 * actionEngine.ts's docstring) — so for a spotlight to actually overlap a
 * speech's duration, it must be authored *before* that speech in the actions
 * array. `[speech, spotlight]` would show the spotlight only *after* the
 * narration finishes, which would fail the "overlap, no extra clock time"
 * assertion this smoke test exists to check.
 */

const chineseFontStack =
  '"Noto Sans SC", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", Arial, sans-serif';
const formulaHtml = katex.renderToString(
  String.raw`T(n)=\sum_{i=1}^{n-1}(n-i)=\frac{n(n-1)}{2}`,
  { throwOnError: false, displayMode: true },
);

const slide: Slide = {
  id: 'smoke-slide-1',
  viewportSize: 1000,
  viewportRatio: 0.5625,
  theme: {
    backgroundColor: '#ffffff',
    themeColors: ['#5b8def'],
    fontColor: '#222222',
    fontName: chineseFontStack,
  },
  elements: [
    {
      type: 'text',
      id: 'el-formula',
      left: 120,
      top: 80,
      width: 760,
      height: 100,
      rotate: 0,
      content:
        `<p data-font-probe="primary" style="font-family:${chineseFontStack};font-size:40px;">` +
        '冒泡排序：相邻元素两两比较，大的往后冒泡</p>',
      defaultFontName: chineseFontStack,
      defaultColor: '#222',
    },
    {
      type: 'latex',
      id: 'el-latex',
      left: 170,
      top: 205,
      width: 660,
      height: 105,
      rotate: 0,
      latex: String.raw`T(n)=\sum_{i=1}^{n-1}(n-i)=\frac{n(n-1)}{2}`,
      html: formulaHtml,
      color: '#1d4ed8',
      align: 'center',
    },
    {
      type: 'text',
      id: 'el-explanation',
      left: 160,
      top: 330,
      width: 680,
      height: 70,
      rotate: 0,
      content:
        `<p style="font-family:${chineseFontStack};font-size:28px;text-align:center;">` +
        '相邻元素的比较次数形成等差数列，因此时间复杂度为 O(n²)。</p>',
      defaultFontName: chineseFontStack,
      defaultColor: '#334155',
    },
    {
      type: 'text',
      id: 'el-font-probe',
      left: 100,
      top: 470,
      width: 800,
      height: 42,
      rotate: 0,
      content:
        `<p data-font-probe="fallback" style="font-family:${chineseFontStack};font-size:18px;text-align:center;">` +
        '字体回退探针：中文标点【】、生僻字“龘”、Latin ABC、数字 123</p>',
      defaultFontName: chineseFontStack,
      defaultColor: '#64748b',
    },
  ],
  background: { type: 'solid', color: '#ffffff' },
};

const actionsOverlap: Action[] = [
  { id: 'act-spot-1', type: 'spotlight', elementId: 'el-formula' },
  {
    id: 'act-speech-1',
    type: 'speech',
    text: '这是冒泡排序。相邻元素依次比较，较大的元素向后移动。',
    voice: 'zh-CN',
    speed: 0.95,
  },
];

const actionsMissingElement: Action[] = [
  { id: 'act-spot-2', type: 'spotlight', elementId: 'el-does-not-exist' },
  { id: 'act-speech-2', type: 'speech', text: '聚焦指向不存在的元素，验证不崩溃' },
];

const videoSlide: Slide = {
  ...slide,
  id: 'smoke-slide-video',
  elements: [
    {
      type: 'video',
      id: 'el-video',
      left: 100,
      top: 56,
      width: 800,
      height: 450,
      rotate: 0,
      autoplay: false,
      src: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
      ext: 'mp4',
    },
  ],
};

const actionsVideo: Action[] = [
  { id: 'act-video-1', type: 'play_video', elementId: 'el-video' },
];

export function PlayerSmokePage() {
  return (
    <div
      data-chinese-font-stack={chineseFontStack}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 32,
        padding: 24,
        fontFamily: chineseFontStack,
      }}
    >
      <section>
        <h2 style={{ marginBottom: 8 }}>AC-08-2 · spotlight + speech 时间窗重叠</h2>
        <p style={{ marginBottom: 8, color: '#667085', fontSize: 13 }}>
          期望：文本渲染在正确位置；播放开始后 el-formula 立刻出现 spotlight
          聚焦（DOM 应有 #slide-element-el-formula 且被 SVG mask 高亮）；旁白
          （浏览器 TTS 或朗读时长 dwell）结束前聚焦应保持，不额外占用播放时钟。
        </p>
        <div style={{ width: 800, height: 450, border: '1px solid #ddd' }}>
          <SlidePlayer slide={slide} actions={actionsOverlap} />
        </div>
      </section>

      <section>
        <h2 style={{ marginBottom: 8 }}>AC-08-4 · spotlight 指向不存在 id 不应崩溃</h2>
        <p style={{ marginBottom: 8, color: '#667085', fontSize: 13 }}>
          期望：控制台可能有降级告警，但页面正常渲染、不抛未捕获异常、播放能走完整个动作序列。
        </p>
        <div style={{ width: 800, height: 450, border: '1px solid #ddd' }}>
          <SlidePlayer slide={slide} actions={actionsMissingElement} />
        </div>
      </section>

      <section>
        <h2 style={{ marginBottom: 8 }}>AC-08-5 · play_video 受时间线控制</h2>
        <p style={{ marginBottom: 8, color: '#667085', fontSize: 13 }}>
          期望：视频挂载后带有 data-video-state="registered"，动作开始时变为
          "playing"，播放结束后变为 "completed"；未执行动作前不应自动播放，且嵌入音频默认静音。
        </p>
        <div style={{ width: 800, height: 450, border: '1px solid #ddd' }}>
          <SlidePlayer slide={videoSlide} actions={actionsVideo} />
        </div>
      </section>
    </div>
  );
}
