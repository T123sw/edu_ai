import { describe, expect, it, vi } from 'vitest';
import { resolveVideoCoverData, resolveVideoSource } from './media-processor.js';

describe('resolveVideoSource', () => {
  it('uses and normalizes a nested source element when video has no src attribute', () => {
    const source = {
      getAttribute: vi.fn((name) => (name === 'src' ? './media/demo.mp4' : '')),
      remove: vi.fn(),
      src: 'http://127.0.0.1/media/demo.mp4',
    };
    const node = {
      currentSrc: '',
      src: '',
      getAttribute: vi.fn(() => ''),
      setAttribute: vi.fn(),
      querySelector: vi.fn((selector) => (selector === 'source[src]' ? source : null)),
    };

    const resolved = resolveVideoSource(node);

    expect(resolved).toBe('./media/demo.mp4');
    expect(node.querySelector).toHaveBeenCalledWith('source[src]');
    expect(node.setAttribute).toHaveBeenCalledWith('src', './media/demo.mp4');
    expect(node.src).toBe('./media/demo.mp4');
    expect(source.remove).toHaveBeenCalledOnce();
  });
});

describe('resolveVideoCoverData', () => {
  it('uses the first video frame as cover when no poster is provided', async () => {
    const captureVideoFirstFrame = vi.fn().mockResolvedValue('data:image/png;base64,first-frame');
    const captureElementImage = vi.fn().mockResolvedValue('data:image/png;base64;element-capture');

    const cover = await resolveVideoCoverData({
      posterSrc: '',
      widthPx: 640,
      heightPx: 360,
      radii: { tl: 0, tr: 0, br: 0, bl: 0 },
      objectFit: 'contain',
      objectPosition: '50% 50%',
      node: { currentTime: 0 },
      captureElementImage,
      captureVideoFirstFrame,
    });

    expect(cover).toBe('data:image/png;base64,first-frame');
    expect(captureVideoFirstFrame).toHaveBeenCalledOnce();
    expect(captureElementImage).not.toHaveBeenCalled();
  });

  it('falls back to element capture when first-frame capture fails', async () => {
    const captureVideoFirstFrame = vi.fn().mockResolvedValue(null);
    const captureElementImage = vi.fn().mockResolvedValue('data:image/png;base64;element-capture');

    const cover = await resolveVideoCoverData({
      posterSrc: '',
      widthPx: 640,
      heightPx: 360,
      radii: { tl: 0, tr: 0, br: 0, bl: 0 },
      objectFit: 'contain',
      objectPosition: '50% 50%',
      node: { currentTime: 0 },
      captureElementImage,
      captureVideoFirstFrame,
    });

    expect(cover).toBe('data:image/png;base64;element-capture');
    expect(captureVideoFirstFrame).toHaveBeenCalledOnce();
    expect(captureElementImage).toHaveBeenCalledOnce();
  });
});
