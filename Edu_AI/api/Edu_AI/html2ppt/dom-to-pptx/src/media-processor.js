import { getProcessedImage } from './image-processor.js';

async function fetchAsDataUrl(url) {
  if (!url) return null;
  if (url.startsWith('data:')) return url;

  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const blob = await response.blob();

    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function inferMediaExtension(url, dataUrl) {
  const fromUrl = (() => {
    if (!url) return null;
    const cleanUrl = url.split('?')[0].split('#')[0];
    const match = cleanUrl.match(/\.([a-z0-9]+)$/i);
    return match ? match[1].toLowerCase() : null;
  })();

  if (fromUrl) return fromUrl;

  if (!dataUrl || !dataUrl.startsWith('data:')) return null;
  const mime = dataUrl.slice(5, dataUrl.indexOf(';')).toLowerCase();
  if (mime === 'video/mp4') return 'mp4';
  if (mime === 'video/webm') return 'webm';
  if (mime === 'video/quicktime') return 'mov';
  return null;
}

function getVideoRadii(style) {
  return {
    tl: parseFloat(style.borderTopLeftRadius) || 0,
    tr: parseFloat(style.borderTopRightRadius) || 0,
    br: parseFloat(style.borderBottomRightRadius) || 0,
    bl: parseFloat(style.borderBottomLeftRadius) || 0,
  };
}

function fitRectWithinBox(boxW, boxH, mediaW, mediaH) {
  if (!boxW || !boxH || !mediaW || !mediaH) {
    return { x: 0, y: 0, w: boxW, h: boxH };
  }

  const mediaRatio = mediaW / mediaH;
  const boxRatio = boxW / boxH;

  let w = boxW;
  let h = boxH;

  if (mediaRatio > boxRatio) {
    h = boxW / mediaRatio;
  } else {
    w = boxH * mediaRatio;
  }

  return {
    x: (boxW - w) / 2,
    y: (boxH - h) / 2,
    w,
    h,
  };
}

async function loadImageDimensions(src) {
  if (!src) return null;

  return await new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous';
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

async function getVideoIntrinsicSize(node, posterSrc) {
  if (node.videoWidth > 0 && node.videoHeight > 0) {
    return { width: node.videoWidth, height: node.videoHeight };
  }

  const posterSize = await loadImageDimensions(posterSrc);
  if (posterSize) return posterSize;

  return null;
}

async function resolveVideoCoverData({
  posterSrc,
  widthPx,
  heightPx,
  radii,
  objectFit,
  objectPosition,
  node,
  captureElementImage,
}) {
  if (posterSrc) {
    const posterData = await getProcessedImage(
      posterSrc,
      widthPx,
      heightPx,
      radii,
      objectFit,
      objectPosition
    );
    if (posterData) return posterData;
  }

  return captureElementImage(node, widthPx, heightPx);
}

export function createVideoRenderItem({
  node,
  style,
  x,
  y,
  w,
  h,
  widthPx,
  heightPx,
  zIndex,
  domOrder,
  captureElementImage,
}) {
  const videoSrc = node.currentSrc || node.src || node.getAttribute('src') || '';
  const posterSrc = node.poster || node.getAttribute('poster') || '';
  const radii = getVideoRadii(style);

  const placeholder = { x, y, w, h };
  const item = {
    type: 'media',
    zIndex,
    domOrder,
    options: { type: 'video', x, y, w, h, data: null, cover: null },
  };

  const job = async () => {
    const mediaData = await fetchAsDataUrl(videoSrc);
    if (!mediaData) {
      item.skip = true;
      return;
    }

    item.options.data = mediaData;

    const extn = inferMediaExtension(videoSrc, mediaData);
    if (extn) item.options.extn = extn;

    const intrinsicSize = await getVideoIntrinsicSize(node, posterSrc);
    const fitted = intrinsicSize
      ? fitRectWithinBox(placeholder.w, placeholder.h, intrinsicSize.width, intrinsicSize.height)
      : { x: 0, y: 0, w: placeholder.w, h: placeholder.h };

    item.options.x = placeholder.x + fitted.x;
    item.options.y = placeholder.y + fitted.y;
    item.options.w = fitted.w;
    item.options.h = fitted.h;

    const coverData = await resolveVideoCoverData({
      posterSrc,
      widthPx: intrinsicSize ? (fitted.w / w) * widthPx : widthPx,
      heightPx: intrinsicSize ? (fitted.h / h) * heightPx : heightPx,
      radii,
      objectFit: 'contain',
      objectPosition: '50% 50%',
      node,
      captureElementImage,
    });

    if (coverData) {
      item.options.cover = coverData;
    }
  };

  return { items: [item], job, stopRecursion: true };
}
