import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

import { applyWhiteColorKeyTransparency, type WhiteColorKeyOptions } from "./avatarTransparency";

type TransparentAvatarCanvasProps = {
  sourceVideoRef: RefObject<HTMLVideoElement>;
  className?: string;
  processingWidth?: number;
  colorKey?: WhiteColorKeyOptions;
  style?: CSSProperties;
};

type VideoFrameCallback = (now: number, metadata: VideoFrameCallbackMetadata) => void;

type VideoFrameCallbackVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (callback: VideoFrameCallback) => number;
  cancelVideoFrameCallback?: (handle: number) => void;
};

export function TransparentAvatarCanvas({
  sourceVideoRef,
  className,
  processingWidth = 360,
  colorKey,
  style,
}: TransparentAvatarCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [aspectRatio, setAspectRatio] = useState("1 / 1");

  useEffect(() => {
    let stopped = false;
    let rafId = 0;
    let videoFrameId = 0;

    const draw = () => {
      if (stopped) return;

      const video = sourceVideoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
        scheduleNext();
        return;
      }

      const width = Math.max(1, Math.min(processingWidth, video.videoWidth));
      const height = Math.max(1, Math.round((video.videoHeight / video.videoWidth) * width));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        setAspectRatio(`${video.videoWidth} / ${video.videoHeight}`);
      }

      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        scheduleNext();
        return;
      }

      context.clearRect(0, 0, width, height);
      context.drawImage(video, 0, 0, width, height);
      const imageData = context.getImageData(0, 0, width, height);
      applyWhiteColorKeyTransparency(imageData.data, colorKey);
      context.putImageData(imageData, 0, 0);

      scheduleNext();
    };

    const scheduleNext = () => {
      if (stopped) return;
      const video = sourceVideoRef.current as VideoFrameCallbackVideo | null;
      if (video?.requestVideoFrameCallback) {
        videoFrameId = video.requestVideoFrameCallback(() => draw());
        return;
      }
      rafId = window.requestAnimationFrame(draw);
    };

    scheduleNext();

    return () => {
      stopped = true;
      if (rafId) window.cancelAnimationFrame(rafId);
      const video = sourceVideoRef.current as VideoFrameCallbackVideo | null;
      if (videoFrameId && video?.cancelVideoFrameCallback) {
        video.cancelVideoFrameCallback(videoFrameId);
      }
    };
  }, [colorKey, processingWidth, sourceVideoRef]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className}
      style={{ ...style, aspectRatio }}
    />
  );
}
