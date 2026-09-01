import type { ClassroomPptxInput } from './pptxExporter.ts';

interface DownloadDependencies {
  build: (input: ClassroomPptxInput) => Promise<Blob>;
  save: (blob: Blob, filename: string) => void;
}

export interface PptxDownloader {
  readonly running: boolean;
  run(input: ClassroomPptxInput): Promise<boolean>;
}

const WINDOWS_RESERVED_NAME =
  /^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i;

export function sanitizePptxFilename(title: string): string {
  let filename = title
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f：／？＜＞]/g, '_')
    .replace(/[.\s]+$/g, '')
    .slice(0, 96)
    .replace(/[.\s]+$/g, '');
  if (!filename || /^\.+$/.test(filename)) filename = '课件';
  if (WINDOWS_RESERVED_NAME.test(filename)) filename += '_';
  return filename;
}

export function createPptxDownloader(
  dependencies: DownloadDependencies = {
    build: async (input) => {
      const { buildClassroomPptx } = await import('./pptxExporter.ts');
      return buildClassroomPptx(input);
    },
    save: saveBlob,
  },
): PptxDownloader {
  let running = false;
  return {
    get running() {
      return running;
    },
    async run(input) {
      if (running) return false;
      running = true;
      try {
        const blob = await dependencies.build(input);
        if (blob.size === 0) throw new Error('PPTX export produced an empty file');
        dependencies.save(blob, `${sanitizePptxFilename(input.title)}.pptx`);
        return true;
      } finally {
        running = false;
      }
    },
  };
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
