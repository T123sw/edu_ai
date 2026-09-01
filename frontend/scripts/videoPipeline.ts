import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import {
  copyFile,
  mkdir,
  readFile,
  readdir,
  rm,
  writeFile,
} from 'node:fs/promises';
import { homedir } from 'node:os';
import { basename, dirname, extname, join, parse, resolve } from 'node:path';
import { chromium, type Page } from 'playwright';
import type { LessonTimeline, TimelineClip } from '../src/openmaic/timeline.ts';
import {
  mergeMeasuredSceneTimelines,
  timelineToSrt,
} from '../src/openmaic/videoExport.ts';

export interface VideoExportOptions {
  baseUrl: string;
  outputDir: string;
  fixture?: boolean;
  courseId?: string;
  classroomId?: string;
  authJson?: string;
  ffmpegPath?: string;
  overwrite?: boolean;
  timeoutMs: number;
  sceneTimeoutMs: number;
  onProgress?: (event: VideoExportProgress) => void;
}

export interface VideoExportProgress {
  step: 'preparing' | 'recording' | 'encoding' | 'mixing' | 'completed';
  progress: number;
  message: string;
}

export interface VideoExportResult {
  videoPath: string;
  subtitlePath: string;
  timelinePath: string;
  durationMs: number;
  sceneCount: number;
  streams: Array<{ codec_type?: string; codec_name?: string }>;
}

export interface BuildRenderUrlOptions {
  baseUrl: string;
  fixture?: boolean;
  courseId?: string;
  classroomId?: string;
  sceneIndex: number;
}

type CapturedAudio = {
  path: string;
  localStartMs: number;
};

type CapturedScene = {
  timeline: LessonTimeline;
  videoPath: string;
  audio: CapturedAudio[];
};

export function buildRenderUrl(options: BuildRenderUrlOptions): string {
  const params = new URLSearchParams();
  if (options.fixture) {
    params.set('fixture', '1');
  } else {
    if (!options.courseId || !options.classroomId) {
      throw new Error('courseId and classroomId are required');
    }
    params.set('course_id', options.courseId);
    params.set('classroom_id', options.classroomId);
  }
  params.set('scene_index', String(options.sceneIndex));
  return `${options.baseUrl.replace(/\/+$/, '')}/#video-render?${params.toString()}`;
}

function optionValue(args: readonly string[], name: string): string | undefined {
  const inline = args.find((argument) => argument.startsWith(`${name}=`));
  if (inline) {
    const value = inline.slice(name.length + 1);
    if (!value) throw new Error(`${name} requires a value`);
    return value;
  }
  const index = args.indexOf(name);
  if (index < 0) return undefined;
  const value = args[index + 1];
  if (!value || value.startsWith('--')) throw new Error(`${name} requires a value`);
  return value;
}

export function parseVideoExportArguments(args: readonly string[]): VideoExportOptions {
  const baseUrl = optionValue(args, '--base-url') ?? 'http://127.0.0.1:4173';
  const outputDir = optionValue(args, '--output-dir');
  if (!outputDir) throw new Error('--output-dir is required');

  const fixture = args.includes('--fixture');
  const courseId = optionValue(args, '--course-id');
  const classroomId = optionValue(args, '--classroom-id');
  const authJson =
    optionValue(args, '--auth-json') ?? process.env.EDU_AI_EXPORT_AUTH_JSON;
  if (!fixture && (!courseId || !classroomId)) {
    throw new Error('--course-id and --classroom-id are required');
  }
  if (!fixture && !authJson) {
    throw new Error('--auth-json is required for a classroom export');
  }
  if (fixture && (courseId || classroomId)) {
    throw new Error('--fixture cannot be combined with classroom identifiers');
  }

  const timeoutValue = optionValue(args, '--timeout-ms');
  const timeoutMs = timeoutValue ? Number.parseInt(timeoutValue, 10) : 120000;
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) {
    throw new Error('--timeout-ms must be a positive integer');
  }
  const sceneTimeoutValue = optionValue(args, '--scene-timeout-ms');
  const sceneTimeoutMs = sceneTimeoutValue
    ? Number.parseInt(sceneTimeoutValue, 10)
    : 600000;
  if (!Number.isInteger(sceneTimeoutMs) || sceneTimeoutMs <= 0) {
    throw new Error('--scene-timeout-ms must be a positive integer');
  }

  return {
    baseUrl,
    outputDir,
    ...(fixture ? { fixture: true } : { courseId, classroomId, authJson }),
    ...(optionValue(args, '--ffmpeg')
      ? { ffmpegPath: optionValue(args, '--ffmpeg') }
      : {}),
    ...(args.includes('--overwrite') ? { overwrite: true } : {}),
    timeoutMs,
    sceneTimeoutMs,
  };
}

export function serializeConcatManifest(paths: readonly string[]): string {
  return `${paths
    .map((path) => {
      const normalized = path.replaceAll('\\', '/').replaceAll("'", "'\\''");
      return `file '${normalized}'`;
    })
    .join('\n')}\n`;
}

export function buildAudioMixArguments(
  audio: readonly { path: string; startMs: number }[],
  narrationGain: number,
): string[] {
  if (audio.length === 0) return [];
  const filters = audio.map(
    (asset, index) =>
      `[${index + 1}:a]adelay=${Math.round(asset.startMs)}|${Math.round(
        asset.startMs,
      )},volume=${narrationGain}[n${index}]`,
  );
  const mixInputs = audio.map((_, index) => `[n${index}]`).join('');
  filters.push(
    `${mixInputs}amix=inputs=${audio.length}:duration=longest:dropout_transition=0:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]`,
  );
  return [
    ...audio.flatMap((asset) => ['-i', asset.path]),
    '-filter_complex',
    filters.join(';'),
    '-map',
    '0:v:0',
    '-map',
    '[aout]',
    '-c:v',
    'copy',
    '-c:a',
    'aac',
    '-ar',
    '48000',
    '-b:a',
    '128k',
  ];
}

export function createTimelineArtifact(timeline: LessonTimeline): LessonTimeline {
  const artifact = structuredClone(timeline);
  for (const scene of artifact.scenes) {
    for (const clip of scene.clips) {
      if (typeof clip.payload.audioUrl !== 'string') continue;
      delete clip.payload.audioUrl;
      clip.payload.audioMixed = true;
    }
  }
  return artifact;
}

function resolveFfmpegPath(explicit?: string): string {
  const condaPrefix = process.env.CONDA_PREFIX;
  const candidates = [
    explicit,
    process.env.FFMPEG_PATH,
    condaPrefix ? join(condaPrefix, 'Library', 'bin', 'ffmpeg.exe') : undefined,
    'D:\\anaconda\\envs\\edu-ai\\Library\\bin\\ffmpeg.exe',
    'ffmpeg',
  ].filter((candidate): candidate is string => Boolean(candidate));
  return candidates.find((candidate) => candidate === 'ffmpeg' || existsSync(candidate)) ?? 'ffmpeg';
}

function ffprobeFor(ffmpegPath: string): string {
  if (ffmpegPath === 'ffmpeg') return 'ffprobe';
  const extension = extname(ffmpegPath);
  return join(dirname(ffmpegPath), `ffprobe${extension}`);
}

async function runCommand(command: string, args: readonly string[]): Promise<string> {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolvePromise(stdout);
      } else {
        reject(
          new Error(
            `${basename(command)} exited with code ${code}: ${stderr.slice(-4000)}`,
          ),
        );
      }
    });
  });
}

function ensureSafeOutputDirectory(outputDir: string): void {
  const target = resolve(outputDir);
  const root = parse(target).root;
  const unsafe = new Set([root, resolve(process.cwd()), resolve(homedir())]);
  if (unsafe.has(target)) {
    throw new Error(`refusing unsafe output directory: ${target}`);
  }
}

async function prepareOutputDirectory(
  outputDir: string,
  overwrite: boolean,
): Promise<{ outputDir: string; workDir: string }> {
  const absoluteOutput = resolve(outputDir);
  ensureSafeOutputDirectory(absoluteOutput);
  if (existsSync(absoluteOutput)) {
    const entries = await readdir(absoluteOutput);
    if (entries.length > 0 && !overwrite) {
      throw new Error(`output directory is not empty: ${absoluteOutput}`);
    }
    if (entries.length > 0) {
      await rm(absoluteOutput, { recursive: true, force: true });
    }
  }
  await mkdir(absoluteOutput, { recursive: true });
  const workDir = join(absoluteOutput, '.work');
  await mkdir(workDir, { recursive: true });
  return { outputDir: absoluteOutput, workDir };
}

function extensionForMime(mimeType: string): string {
  if (mimeType.includes('mpeg')) return '.mp3';
  if (mimeType.includes('ogg')) return '.ogg';
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return '.m4a';
  return '.wav';
}

function decodeDataUrl(url: string): { bytes: Buffer; mimeType: string } {
  const match = /^data:([^;,]+)?(;base64)?,(.*)$/s.exec(url);
  if (!match) throw new Error('invalid narration data URL');
  const mimeType = match[1] || 'application/octet-stream';
  return {
    bytes: match[2]
      ? Buffer.from(match[3], 'base64')
      : Buffer.from(decodeURIComponent(match[3]), 'utf8'),
    mimeType,
  };
}

async function readAudioUrl(
  page: Page,
  url: string,
): Promise<{ bytes: Buffer; mimeType: string }> {
  if (url.startsWith('data:')) return decodeDataUrl(url);
  const payload = await page.evaluate(async (sourceUrl) => {
    const response = await fetch(sourceUrl);
    if (!response.ok) throw new Error(`audio fetch failed: ${response.status}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    return {
      base64: btoa(binary),
      mimeType: response.headers.get('content-type') || 'application/octet-stream',
    };
  }, url);
  return { bytes: Buffer.from(payload.base64, 'base64'), mimeType: payload.mimeType };
}

function narrationClips(timeline: LessonTimeline): TimelineClip[] {
  return timeline.scenes.flatMap((scene) =>
    scene.clips.filter(
      (clip) =>
        clip.track === 'narration' &&
        typeof clip.payload.audioUrl === 'string' &&
        clip.payload.audioUrl.length > 0,
    ),
  );
}

async function captureScene(
  browserInstance: Awaited<ReturnType<typeof chromium.launch>>,
  options: VideoExportOptions,
  sceneIndex: number,
  workDir: string,
): Promise<{ captured: CapturedScene; sceneCount: number }> {
  const videoDir = join(workDir, `recording-${sceneIndex}`);
  await mkdir(videoDir, { recursive: true });
  const context = await browserInstance.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
  });
  if (options.authJson) {
    const auth = options.authJson.startsWith('@')
      ? await readFile(options.authJson.slice(1), 'utf8')
      : options.authJson;
    JSON.parse(auth);
    await context.addInitScript((storedAuth) => {
      window.localStorage.setItem('edu-ai-auth', storedAuth);
    }, auth);
  }

  const page = await context.newPage();
  const video = page.video();
  if (!video) throw new Error('Playwright video recording did not start');
  const url = buildRenderUrl({
    baseUrl: options.baseUrl,
    fixture: options.fixture,
    courseId: options.courseId,
    classroomId: options.classroomId,
    sceneIndex,
  });

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: options.timeoutMs });
    const root = page.locator('[data-video-render-root]');
    await root.waitFor({ state: 'attached', timeout: options.timeoutMs });
    await page.waitForFunction(
      () => {
        const element = document.querySelector('[data-video-render-root]');
        const status = element?.getAttribute('data-export-status');
        return status === 'completed' || status === 'failed';
      },
      undefined,
      { timeout: options.sceneTimeoutMs },
    );
    const status = await root.getAttribute('data-export-status');
    if (status !== 'completed') {
      throw new Error(
        (await root.getAttribute('data-export-error')) || 'classroom render failed',
      );
    }
    const sceneCount = Number(await root.getAttribute('data-scene-count'));
    const timelineRaw = await root.locator('[data-export-timeline]').textContent();
    if (!timelineRaw?.trim()) throw new Error('render route returned no timeline');
    const timeline = JSON.parse(timelineRaw) as LessonTimeline;

    const audio: CapturedAudio[] = [];
    for (const [audioIndex, clip] of narrationClips(timeline).entries()) {
      const sourceUrl = String(clip.payload.audioUrl);
      const payload = await readAudioUrl(page, sourceUrl);
      const path = join(
        workDir,
        `audio-${sceneIndex}-${audioIndex}${extensionForMime(payload.mimeType)}`,
      );
      await writeFile(path, payload.bytes);
      audio.push({ path, localStartMs: clip.startMs });
    }

    await context.close();
    return {
      captured: { timeline, videoPath: await video.path(), audio },
      sceneCount,
    };
  } catch (error) {
    await context.close().catch(() => undefined);
    throw error;
  }
}

async function probeMedia(ffprobePath: string, path: string) {
  const output = await runCommand(ffprobePath, [
    '-v',
    'error',
    '-show_entries',
    'format=duration',
    '-show_streams',
    '-of',
    'json',
    path,
  ]);
  return JSON.parse(output) as {
    format?: { duration?: string };
    streams?: Array<{ codec_type?: string; codec_name?: string }>;
  };
}

export async function exportClassroomVideo(
  options: VideoExportOptions,
): Promise<VideoExportResult> {
  const emit = (event: VideoExportProgress) => options.onProgress?.(event);
  emit({ step: 'preparing', progress: 2, message: '准备视频导出环境' });
  const { outputDir, workDir } = await prepareOutputDirectory(
    options.outputDir,
    options.overwrite === true,
  );
  const ffmpegPath = resolveFfmpegPath(options.ffmpegPath);
  const ffprobePath = ffprobeFor(ffmpegPath);
  await runCommand(ffmpegPath, ['-version']);
  await runCommand(ffprobePath, ['-version']);

  const browserInstance = await chromium.launch({ headless: true });
  const capturedScenes: CapturedScene[] = [];
  try {
    let sceneCount = 1;
    for (let sceneIndex = 0; sceneIndex < sceneCount; sceneIndex += 1) {
      emit({
        step: 'recording',
        progress: 8 + Math.round((sceneIndex / Math.max(sceneCount, 1)) * 42),
        message: `录制场景 ${sceneIndex + 1}/${sceneCount}`,
      });
      const result = await captureScene(
        browserInstance,
        options,
        sceneIndex,
        workDir,
      );
      sceneCount = result.sceneCount;
      capturedScenes.push(result.captured);
    }
  } finally {
    await browserInstance.close();
  }

  const timeline = mergeMeasuredSceneTimelines(
    options.classroomId ?? 'fixture-video-render',
    capturedScenes.map((scene) => scene.timeline),
  );
  const timelinePath = join(outputDir, 'timeline.json');
  const subtitlePath = join(outputDir, 'classroom.srt');
  await writeFile(
    timelinePath,
    `${JSON.stringify(createTimelineArtifact(timeline), null, 2)}\n`,
    'utf8',
  );
  await writeFile(subtitlePath, timelineToSrt(timeline), 'utf8');

  emit({ step: 'encoding', progress: 55, message: '转码并拼接课堂画面' });
  const encodedScenes: string[] = [];
  for (const [sceneIndex, captured] of capturedScenes.entries()) {
    const targetDurationSeconds = Math.max(captured.timeline.durationMs / 1000, 0.05);
    const sourceProbe = await probeMedia(ffprobePath, captured.videoPath);
    const sourceDurationSeconds = Number(sourceProbe.format?.duration ?? 0);
    const leadInSeconds = Math.max(
      0,
      sourceDurationSeconds - targetDurationSeconds - 0.05,
    );
    const encodedPath = join(workDir, `scene-${sceneIndex}.mp4`);
    await runCommand(ffmpegPath, [
      '-y',
      '-ss',
      leadInSeconds.toFixed(3),
      '-i',
      captured.videoPath,
      '-t',
      targetDurationSeconds.toFixed(3),
      '-an',
      '-vf',
      'fps=30,scale=1920:1080:flags=lanczos,format=yuv420p',
      '-c:v',
      'libx264',
      '-preset',
      'veryfast',
      '-movflags',
      '+faststart',
      encodedPath,
    ]);
    encodedScenes.push(encodedPath);
  }

  const concatManifest = join(workDir, 'scenes.txt');
  const mergedSilentPath = join(workDir, 'classroom-silent.mp4');
  await writeFile(concatManifest, serializeConcatManifest(encodedScenes), 'utf8');
  await runCommand(ffmpegPath, [
    '-y',
    '-f',
    'concat',
    '-safe',
    '0',
    '-i',
    concatManifest,
    '-c',
    'copy',
    mergedSilentPath,
  ]);

  const audio = capturedScenes.flatMap((scene, sceneIndex) =>
    scene.audio.map((asset) => ({
      path: asset.path,
      startMs: timeline.scenes[sceneIndex].startMs + asset.localStartMs,
    })),
  );
  const videoPath = join(outputDir, 'classroom.mp4');
  emit({ step: 'mixing', progress: 85, message: '混合课堂配音' });
  const audioArguments = buildAudioMixArguments(
    audio,
    timeline.render?.audioMix.narrationGain ?? 1,
  );
  if (audioArguments.length > 0) {
    await runCommand(ffmpegPath, [
      '-y',
      '-i',
      mergedSilentPath,
      ...audioArguments,
      '-movflags',
      '+faststart',
      videoPath,
    ]);
  } else {
    await copyFile(mergedSilentPath, videoPath);
  }

  const finalProbe = await probeMedia(ffprobePath, videoPath);
  await rm(workDir, { recursive: true, force: true });
  emit({ step: 'completed', progress: 100, message: '视频导出完成' });
  return {
    videoPath,
    subtitlePath,
    timelinePath,
    durationMs: Math.round(Number(finalProbe.format?.duration ?? 0) * 1000),
    sceneCount: capturedScenes.length,
    streams: finalProbe.streams ?? [],
  };
}
