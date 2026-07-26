import { useEffect, useMemo, useRef, useState } from 'react';
import {
  patchInteractiveHtml,
  WidgetMessageBuffer,
} from './interactiveScene';
import { SceneActionPlayback } from './SceneActionPlayback';
import type { InteractiveClassroomContent } from '../stitch/api/types';

export interface InteractiveScenePlayerProps {
  sceneId: string;
  content: InteractiveClassroomContent;
  actions?: Array<Record<string, unknown>>;
}

type InteractiveRuntimeMessage = {
  __eduClassroomInteractive?: boolean;
  kind?: string;
  message?: string;
};

export function InteractiveScenePlayer({
  sceneId,
  content,
  actions,
}: InteractiveScenePlayerProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const widget = useMemo(() => new WidgetMessageBuffer(), []);
  const srcDoc = useMemo(
    () => (content.html ? patchInteractiveHtml(content.html) : undefined),
    [content.html],
  );
  const sourceUrl = srcDoc ? undefined : content.url;

  useEffect(() => {
    const handleMessage = (event: MessageEvent<InteractiveRuntimeMessage>) => {
      if (event.source !== iframeRef.current?.contentWindow) return;
      const message = event.data;
      if (
        !message ||
        message.__eduClassroomInteractive !== true ||
        message.kind !== 'runtime-error'
      ) {
        return;
      }
      setRuntimeError(message.message || '互动内容运行时发生错误');
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [reloadKey]);

  useEffect(() => () => widget.setSender(null), [widget]);

  const reload = () => {
    widget.setSender(null);
    setRuntimeError(null);
    setReloadKey((value) => value + 1);
  };

  if (!srcDoc && !sourceUrl) {
    return (
      <SceneMessage
        title="互动场景缺少内容"
        detail="该场景既没有内嵌 HTML，也没有可访问的 URL。"
      />
    );
  }

  return (
    <SceneActionPlayback sceneId={sceneId} actions={actions} widget={widget}>
      <div className="relative h-full w-full overflow-hidden bg-white">
        <iframe
          key={reloadKey}
          ref={iframeRef}
          title={`互动场景 ${sceneId}`}
          src={sourceUrl}
          srcDoc={srcDoc}
          sandbox="allow-scripts allow-forms allow-modals allow-popups allow-downloads"
          referrerPolicy="no-referrer"
          className="h-full w-full border-0"
          onLoad={() => {
            const frame = iframeRef.current?.contentWindow;
            if (!frame) return;
            widget.setSender((type, payload) => {
              frame.postMessage({ type, ...payload }, '*');
            });
          }}
        />
        {runtimeError ? (
          <div className="absolute inset-x-4 bottom-4 rounded-xl border border-rose-200 bg-white/95 p-4 shadow-lg">
            <p className="font-semibold text-rose-700">互动内容运行失败</p>
            <p className="mt-1 line-clamp-3 text-sm text-rose-600">
              {runtimeError}
            </p>
            <button
              type="button"
              onClick={reload}
              className="mt-3 rounded-full bg-(--accent-strong) px-4 py-2 text-sm font-semibold text-white"
            >
              重新加载
            </button>
          </div>
        ) : null}
      </div>
    </SceneActionPlayback>
  );
}

function SceneMessage({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex h-full w-full items-center justify-center bg-(--surface-subtle) p-10 text-center">
      <div>
        <p className="font-semibold text-(--app-text)">{title}</p>
        <p className="mt-2 text-sm text-(--muted-text)">{detail}</p>
      </div>
    </div>
  );
}
