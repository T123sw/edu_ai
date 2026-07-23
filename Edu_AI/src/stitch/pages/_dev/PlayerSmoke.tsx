import type { Slide } from '@openmaic/renderer';
import type { Action } from '@openmaic/dsl';
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

const slide: Slide = {
  id: 'smoke-slide-1',
  viewportSize: 1000,
  viewportRatio: 0.5625,
  theme: {
    backgroundColor: '#ffffff',
    themeColors: ['#5b8def'],
    fontColor: '#222222',
    fontName: 'sans-serif',
  },
  elements: [
    {
      type: 'text',
      id: 'el-formula',
      left: 120,
      top: 220,
      width: 760,
      height: 100,
      rotate: 0,
      content: '<p style="font-size: 40px;">冒泡排序：相邻元素两两比较，大的往后冒泡</p>',
      defaultFontName: 'sans-serif',
      defaultColor: '#222',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  ],
  background: { type: 'solid', color: '#ffffff' },
};

const actionsOverlap: Action[] = [
  { id: 'act-spot-1', type: 'spotlight', elementId: 'el-formula' },
  { id: 'act-speech-1', type: 'speech', text: '这是冒泡排序' },
];

const actionsMissingElement: Action[] = [
  { id: 'act-spot-2', type: 'spotlight', elementId: 'el-does-not-exist' },
  { id: 'act-speech-2', type: 'speech', text: '聚焦指向不存在的元素，验证不崩溃' },
];

export function PlayerSmokePage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32, padding: 24 }}>
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
    </div>
  );
}
