import { useRef, useState } from 'react';
import type { PptxExportScene } from './pptxExporter.ts';
import { createPptxDownloader } from './pptxDownload.ts';

export interface PptxExportButtonProps {
  title: string;
  scenes: readonly PptxExportScene[];
}

export function PptxExportButton({
  title,
  scenes,
}: PptxExportButtonProps) {
  const downloader = useRef(createPptxDownloader());
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const hasSlides = scenes.some(
    (scene) =>
      scene.content?.type === 'slide' && scene.content.canvas !== undefined,
  );

  const handleExport = async () => {
    if (downloader.current.running) return;
    setExporting(true);
    setStatus(null);
    try {
      const downloaded = await downloader.current.run({ title, scenes });
      if (downloaded) setStatus('PPTX 已开始下载');
    } catch (error) {
      setStatus(
        error instanceof Error ? `导出失败：${error.message}` : '导出失败，请重试',
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={handleExport}
        disabled={!hasSlides || exporting}
        aria-busy={exporting}
        className="inline-flex items-center gap-2 rounded-full bg-(--accent-strong) px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
      >
        <span aria-hidden="true">↓</span>
        {exporting ? '正在导出…' : '导出 PPTX'}
      </button>
      <span
        role="status"
        aria-live="polite"
        className="max-w-72 text-xs text-(--muted-text)"
      >
        {status}
      </span>
    </div>
  );
}
