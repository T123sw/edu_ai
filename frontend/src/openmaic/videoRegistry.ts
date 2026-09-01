import type {
  ActionVideoController,
  VideoPlaybackResult,
} from './actionEngine';

interface ActivePlayback {
  video: HTMLVideoElement;
  settle: (result: Exclude<VideoPlaybackResult, 'missing'>) => void;
}

/**
 * Connects stable DSL element IDs to native video elements rendered inside a
 * slide. Only an explicit play_video action starts playback.
 */
export class VideoRegistry implements ActionVideoController {
  private readonly videos = new Map<string, HTMLVideoElement>();
  private active: ActivePlayback | null = null;

  register(elementId: string, video: HTMLVideoElement): () => void {
    const previous = this.videos.get(elementId);
    if (previous && previous !== video) {
      if (this.active?.video === previous) this.cancel();
      previous.dataset.videoState = 'unregistered';
    }

    this.videos.set(elementId, video);
    video.dataset.videoState = 'registered';

    return () => {
      if (this.videos.get(elementId) !== video) return;
      if (this.active?.video === video) this.cancel();
      this.videos.delete(elementId);
      video.dataset.videoState = 'unregistered';
    };
  }

  isRegistered(elementId: string): boolean {
    return this.videos.has(elementId);
  }

  play(elementId: string): Promise<VideoPlaybackResult> {
    const video = this.videos.get(elementId);
    if (!video) return Promise.resolve('missing');

    this.cancel();
    video.muted = true;
    try {
      video.currentTime = 0;
    } catch {
      // Some streams are not seekable before metadata loads; play from the
      // browser-selected start position in that case.
    }
    video.dataset.videoState = 'playing';

    return new Promise((resolve) => {
      let settled = false;
      const settle = (result: Exclude<VideoPlaybackResult, 'missing'>) => {
        if (settled) return;
        settled = true;
        video.removeEventListener('ended', handleEnded);
        video.removeEventListener('error', handleError);
        if (this.active?.settle === settle) this.active = null;
        video.dataset.videoState =
          result === 'ended' ? 'completed' : 'failed';
        resolve(result);
      };
      const handleEnded = () => settle('ended');
      const handleError = () => settle('failed');

      this.active = { video, settle };
      video.addEventListener('ended', handleEnded);
      video.addEventListener('error', handleError);
      video.play().catch(handleError);
    });
  }

  cancel(): void {
    const active = this.active;
    if (!active) return;
    this.active = null;
    active.video.pause();
    active.settle('failed');
  }

  dispose(): void {
    this.cancel();
    for (const video of this.videos.values()) {
      video.dataset.videoState = 'unregistered';
    }
    this.videos.clear();
  }
}
