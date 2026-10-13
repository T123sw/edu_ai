import { reportAnchors } from "../components/shared/reportAnchors";
import type { ReadingSnapshot } from '../liveLearning/agentTurns';
import { acceptReadingMessage, resourceRef, refKey } from '../liveLearning/readingContext';
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { emptyEvidence, uid, resourceDurationLabel, type Evidence, type LearningResource } from "./model";
import { Icon } from "./ui";

// Shared by the reader and Markdown export so exported examples match the preview.
// eslint-disable-next-line react-refresh/only-export-components
export function reportParagraphs(resource: LearningResource): string[] {
  if (resource.content) return resource.content.split(/\n\s*\n/).map(p => p.trim()).filter(p => p && !p.startsWith("#"));
  const agent = /agent|react|mcp|工具调用/i.test(resource.topic);
  if (agent)
    return [
      "理解 Agent，可以先从“完成一个目标”开始。普通问答通常产生一次回答；Agent 则围绕目标，结合当前信息，决定下一步需要执行的行动。",
      "一个典型的过程包含三个环节：理解目标、调用工具、根据结果继续判断。模型提供推理能力，工具提供与外部环境交互的能力，运行流程则把这些能力组织起来。",
      "以整理学习资料为例：先确定需要解决的问题，再检索相关文档，阅读并筛选内容，最后形成结构化笔记。如果资料不足，可以继续检索，而不是立刻给出结论。",
      "ReAct 把推理与行动交替组织起来；MCP 则提供连接外部工具和数据的协议。它们解决的是不同层面的问题，需要在实际案例中区分。",
    ];
  if (/python|变量|函数|脚本/i.test(resource.topic))
    return [
      "编程是一种把问题拆解成可执行步骤的方法。学习 Python 时，先写一个能运行的小例子，观察输入与输出的关系，再逐渐增加复杂度。",
      "变量保存数据，条件表达判断，循环处理重复操作，函数把一组步骤组织成可复用的能力。这些基础能力可以组合成完整的小程序。",
      "例如整理一份消费记录：读取每条记录，按类别分组，计算总额，然后输出结果。先用几条自己构造的数据验证，再处理更多真实数据。",
      "遇到错误时先缩小范围：查看具体的报错位置，确认变量的值和类型，重新运行最小例子。理解原因比直接复制答案更有帮助。",
    ];
  return [
    `这一节围绕「${resource.topic}」展开。先明确它要解决什么问题，再把核心概念放到一个具体情境中理解。`,
    "把一个复杂主题拆成三个问题：它是什么、为什么需要它、如何实际使用。每回答一个问题，都用自己的话写下一段解释。",
    "选择一个与你的目标相关的小案例，列出已知条件、执行步骤和预期结果。比较不同方法，找出每种方法的适用边界。",
    "这份内容是前端交互示例。真实课堂将在接口联调后根据你的知识点、学习目标和检索来源生成。",
  ];
}

export function LearningContent({
  resource,
  evidence = emptyEvidence(),
  onEvidence,
  paused = false,
  onReading,
  onReadingSnapshot,
  onReferenceRequest,
  clearReferenceSignal = 0,
}: {
  resource: LearningResource;
  evidence?: Evidence;
  onEvidence?: (patch: Partial<Evidence>) => void;
  paused?: boolean;
  onReadingSnapshot?: (snapshot: ReadingSnapshot) => void;
  onReferenceRequest?: (snapshot: ReadingSnapshot) => void;
  clearReferenceSignal?: number;
  onReading?: (type: string, payload: Record<string, unknown>) => void;
}) {
  const channel = useRef(uid());
  const stream = useRef(uid());
  const sequence = useRef(0);
  const lastPosition = useRef('');
  const opened = useRef(false);
  const reachedEnd = useRef(false);
  const onSnapshotRef = useRef(onReadingSnapshot);
  onSnapshotRef.current = onReadingSnapshot;
  const referenceRequestRef = useRef(onReferenceRequest);
  referenceRequestRef.current = onReferenceRequest;
  const initialLocator = useRef(evidence.locator);
  const onReadingRef = useRef(onReading);
  onReadingRef.current = onReading;
  const frame = useRef<HTMLIFrameElement>(null);
  const initialPosition = useRef(evidence.position);
  const [playing, setPlaying] = useState(false);
  const [localPosition, setLocalPosition] = useState(evidence.position);
  const [choice, setChoice] = useState<number | undefined>(evidence.answer);
  const [submitted, setSubmitted] = useState(evidence.answer !== undefined);
  const onEvidenceRef = useRef(onEvidence);
  useEffect(() => {
    onEvidenceRef.current = onEvidence;
  }, [onEvidence]);
  const position = onEvidence ? evidence.position : localPosition;
  const duration = 36;
  function seek(value: number) {
    const p = Math.max(0, Math.min(duration, value));
    setLocalPosition(p);
    onEvidence?.({ position: p });
  }
  useEffect(() => {
    if (paused) setPlaying(false);
  }, [paused]);
  useEffect(() => {
    if (!playing) return;
    if (position >= duration) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setLocalPosition(position + 1);
      onEvidenceRef.current?.({ position: position + 1 });
    }, 1000);
    return () => clearTimeout(timer);
  }, [playing, position]);
  useEffect(() => {
    if (clearReferenceSignal) frame.current?.contentWindow?.postMessage({ type: 'learning-clear-selection', channel_id: channel.current }, location.origin);
  }, [clearReferenceSignal]);
  useEffect(() => {
    frame.current?.contentWindow?.postMessage({ type: 'learning-pause', paused }, location.origin);
  }, [paused]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.source !== frame.current?.contentWindow) return;
      const ref = resourceRef(resource);
      if ((onReadingRef.current || onSnapshotRef.current) && ref) {
        if (event.data?.type === 'learning-context-request') {
          frame.current?.contentWindow?.postMessage({ type: 'learning-context-init', channel_id: channel.current, resource_ref: ref, stream_id: stream.current, can_reference: !!onSnapshotRef.current && !!referenceRequestRef.current }, location.origin);
        } else if (event.data?.type === 'learning-context-ready' && event.data.channel_id === channel.current && event.data.resource_ref && refKey(event.data.resource_ref) === refKey(ref)) {
          if (!opened.current) { opened.current = true; onReadingRef.current?.('resource_opened', {}); }
        } else if (opened.current && acceptReadingMessage(event.data, channel.current, ref, sequence.current)) {
          sequence.current = event.data.sequence;
          const snapshot = { resource_ref: ref, locator: event.data.locator, selected_text: event.data.selected_text || '', classroom: event.data.classroom, practice: event.data.practice, question_prompt: event.data.question_prompt };
          onSnapshotRef.current?.(snapshot);
          if (event.data.intent === 'ask') referenceRequestRef.current?.(snapshot);
          const positionKey = JSON.stringify(event.data.locator);
          if (lastPosition.current !== positionKey) {
            lastPosition.current = positionKey;
            onReadingRef.current?.('reading_position_set', { stream_id: stream.current, sequence: sequence.current, locator: event.data.locator });
          }
          if (event.data.reached_end && !reachedEnd.current) { reachedEnd.current = true; onReadingRef.current?.('resource_end_reached', { locator: event.data.locator }); }
        }
        return;
      }
      if (event.data?.type !== 'learning-position') return;
      const position = event.data.position;
      if (typeof position === 'number' && Number.isFinite(position) && position >= 0) onEvidenceRef.current?.({ position });
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [resource]);
  if (resource.remote) {
    const params = new URLSearchParams({ course_id: resource.remote.courseId, material_id: resource.remote.materialId,
      material_type: resource.remote.materialType, version: String(resource.remote.version), visibility: resource.remote.visibility, position: String(initialPosition.current) });
    if (initialLocator.current?.kind === 'classroom') params.set('scene_id', initialLocator.current.scene_id);
    return <iframe ref={frame} onLoad={() => frame.current?.contentWindow?.postMessage({ type: 'learning-pause', paused }, location.origin)} className="sl-live-material" title={resource.title} src={`?learningPlayer=1#ai?${params}`} />;
  }
  if (!resource.ready)
    return (
      <div className="sl-preparing" role="status">
        <span className="sl-orbit">
          <Icon name="spark" size={35} />
        </span>
        <h2>{resource.live ? "本节内容尚未就绪" : "正在为你准备这一节"}</h2>
        <p>
          学习路径已整理好，内容将在这里陆续出现。
          <br />
          也可以先与右侧的 Agent 聊聊你的学习目标。
        </p>
        <small>{resource.live ? "可在后台任务中查看生成进度或重试" : "本地生成流程演示"}</small>
      </div>
    );
  const paragraphs = reportParagraphs(resource);
  if (resource.kind === "quiz")
    return (
      <article className="sl-article sl-quiz">
        <span className="sl-eyebrow">QUICK CHECK · 示例练习</span>
        <h1>用一个问题，检查你的理解</h1>
        <p>完成观看和真正理解是两回事。先试着做一道检查题。</p>
        <fieldset>
          <legend>面对一个新的学习主题，哪种做法更有助于检查理解？</legend>
          {[
            "播放完全部内容，就认为自己已掌握",
            "用自己的话解释，并尝试解决一个新例子",
            "跳过不熟悉的概念",
          ].map((answer, i) => (
            <label className={choice === i ? "selected" : ""} key={answer}>
              <input
                type="radio"
                name={`answer-${resource.id}`}
                checked={choice === i}
                onChange={() => {
                  setChoice(i);
                  setSubmitted(false);
                }}
              />
              {answer}
            </label>
          ))}
        </fieldset>
        <button
          className="sl-primary"
          disabled={choice === undefined}
          onClick={() => {
            setSubmitted(true);
            onEvidence?.({ answer: choice });
          }}
        >
          检查答案 <Icon name="check" size={17} />
        </button>
        {submitted && (
          <div
            className={`sl-feedback ${choice === 1 ? "correct" : ""}`}
            role="status"
          >
            <strong>{choice === 1 ? "这道题回答正确" : "再想一想"}</strong>
            <p>
              主动解释和迁移到新例子，可以帮助发现理解上的空缺。本题反馈不代表整个主题的掌握程度。
            </p>
          </div>
        )}
      </article>
    );
  if (resource.kind === "video" || resource.kind === "slides") {
    const slide = Math.min(2, Math.floor(position / 12));
    return (
      <div className="sl-lecture">
        <div className="sl-lecture-top">
          <span>
            <Icon name="video" size={16} />
            {resource.kind === "slides" ? "交互课件" : "视频讲解"} · 分镜演示
          </span>
          <span>0{slide + 1} / 03</span>
        </div>
        <div className={`sl-slide sl-slide-${slide}`}>
          <span className="sl-eyebrow">
            {["01 / UNDERSTAND", "02 / CONNECT", "03 / PRACTICE"][slide]}
          </span>
          <h1>{resource.topic}</h1>
          <p>
            {
              [
                "从一个目标开始，理解核心概念。",
                "把知识串起来，让方法变得清晰。",
                "用一个小实践，检验自己的理解。",
              ][slide]
            }
          </p>
          <div className="sl-concept-flow">
            {(slide === 0
              ? ["学习目标", "核心概念", "具体例子"]
              : slide === 1
                ? ["理解问题", "采取行动", "观察结果"]
                : ["动手尝试", "发现问题", "回顾总结"]
            ).map((label, i) => (
              <div key={label}>
                <span>
                  <Icon name={["book", "spark", "check"][i]} size={26} />
                </span>
                <strong>{label}</strong>
                {i < 2 && (
                  <i>
                    <Icon name="arrow" size={20} />
                  </i>
                )}
              </div>
            ))}
          </div>
          <div className="sl-slide-note">{paragraphs[slide]}</div>
        </div>
        <div className="sl-player">
          <button
            className="sl-play-button"
            aria-label={playing ? "暂停讲解" : "播放讲解"}
            onClick={() => {
              if (position >= duration) seek(0);
              setPlaying(!playing);
            }}
          >
            <Icon name={playing ? "pause" : "play"} size={18} />
          </button>
          <span>00:{String(Math.floor(position)).padStart(2, "0")}</span>
          <input
            aria-label="讲解播放位置"
            type="range"
            min="0"
            max={duration}
            step="1"
            value={position}
            onChange={(e) => seek(Number(e.target.value))}
          />
          <span>00:36</span>
        </div>
        <p className="sl-demo-note">
          此处使用 3 段分镜演示播放、暂停和续学；真实音视频将在接口联调后接入。
        </p>
        <div className="sl-lecture-summary">
          <h3>这一节，你将理解</h3>
          <p>{paragraphs[0]}</p>
        </div>
      </div>
    );
  }
  return (
    <article className="sl-article">
      <span className="sl-eyebrow">LEARNING NOTES · 学习报告</span>
      <h1>{resource.content ? resource.title : resource.topic}</h1>
      <p className="sl-article-lead">把知识拆开看，再把它们连接起来。</p>
      <div className="sl-article-meta">
        <span>
          <Icon name="clock" size={15} />{resourceDurationLabel(resource)}
        </span>
        <span>示例内容</span>
      </div>
      <hr />
      {resource.content ? <ReactMarkdown rehypePlugins={[reportAnchors]}>{resource.content.replace(/^#\s+[^\n]+\n?/, "")}</ReactMarkdown> : <>
      <h2>01 / 从一个问题开始</h2>
      <p>{paragraphs[0]}</p>
      <div className="sl-callout">
        <Icon name="spark" />
        <div>
          <strong>带着目标阅读</strong>
          <p>读完后，试着向学习 Agent 解释这个概念，再用一个自己的例子验证。</p>
        </div>
      </div>
      <h2>02 / 建立核心认识</h2>
      <p>{paragraphs[1]}</p>
      <p>{paragraphs[2]}</p>
      <h2>03 / 联系与实践</h2>
      <p>{paragraphs[3]}</p>
      <blockquote>
        学习的下一步，是把“我看过了”变成“我能解释，并且会使用”。
      </blockquote>
      <h2>回顾这一节</h2>
      <p>
        用三句话总结：它解决什么问题？它如何工作？你打算在什么情境下使用它？
      </p>
      </>}
      <p className="sl-demo-note">
        报告为本地预置示例。正式生成时将展示对应的检索来源与引用。
      </p>
    </article>
  );
}
