export type SpeechInputFallback = 'none';

export interface SpeechInputResolution {
  message: string;
  fallback: SpeechInputFallback;
}

export function resolveSpeechInputError(error: unknown): SpeechInputResolution {
  const err = error as { name?: string; message?: string };
  const resolution = (() => {

  switch (err?.name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return { message: '麦克风权限被拒绝，请允许浏览器访问麦克风。' };
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return { message: '未检测到可用麦克风设备。' };
    case 'NotReadableError':
    case 'TrackStartError':
      return { message: '麦克风当前不可用，请检查设备占用情况。' };
    case 'OverconstrainedError':
    case 'ConstraintNotSatisfiedError':
      return { message: '当前设备不满足录音条件，请更换设备后重试。' };
    case 'AbortError':
      return { message: '录音已中断，请重试。' };
    default:
      return { message: err?.message || '语音输入启动失败，请稍后重试。' };
  }
  })();

  return { ...resolution, fallback: 'none' };
}
