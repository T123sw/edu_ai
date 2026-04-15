export type SpeechInputFallback = 'none';

export interface SpeechInputResolution {
  message: string;
  fallback: SpeechInputFallback;
}

function normalizeErrorName(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '';
  }
  return String((error as { name?: unknown }).name || '').trim();
}

function normalizeErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '';
  }
  return String((error as { message?: unknown }).message || '').trim();
}

export function resolveSpeechInputError(error: unknown): SpeechInputResolution {
  const name = normalizeErrorName(error);
  const message = normalizeErrorMessage(error).toLowerCase();

  if (
    name === 'NotFoundError'
    || message.includes('requested device not found')
    || message.includes('device not found')
    || message.includes('no audio input')
  ) {
    return {
      message: '未检测到可用麦克风设备，请检查设备连接后重试。',
      fallback: 'none',
    };
  }

  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return {
      message: '麦克风权限被拒绝，请先在浏览器中允许访问麦克风。',
      fallback: 'none',
    };
  }

  if (name === 'NotReadableError' || name === 'AbortError') {
    return {
      message: '麦克风当前不可用，可能正被其他应用占用。',
      fallback: 'none',
    };
  }

  return {
    message: normalizeErrorMessage(error) || '语音输入启动失败，请稍后重试。',
    fallback: 'none',
  };
}
