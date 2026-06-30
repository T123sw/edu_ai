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

export function resolveVideoSource(node) {
  if (!node) return '';

  const directSrc =
    node.currentSrc ||
    node.src ||
    (typeof node.getAttribute === 'function' ? node.getAttribute('src') : '') ||
    '';
  if (directSrc) return directSrc;

  const sourceNode =
    typeof node.querySelector === 'function' ? node.querySelector('source[src]') : null;
  const nestedSrc =
    (sourceNode && typeof sourceNode.getAttribute === 'function'
      ? sourceNode.getAttribute('src')
      : '') ||
    (sourceNode ? sourceNode.src : '') ||
    '';

  if (nestedSrc) {
    if (typeof node.setAttribute === 'function') {
      node.setAttribute('src', nestedSrc);
    }
    try {
      node.src = nestedSrc;
    } catch {
      // Some DOM implementations expose src as read-only; the attribute is enough for browsers.
    }
    if (typeof sourceNode.remove === 'function') {
      sourceNode.remove();
    } else if (sourceNode.parentNode && typeof sourceNode.parentNode.removeChild === 'function') {
      sourceNode.parentNode.removeChild(sourceNode);
    }
  }

  return nestedSrc;
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

function waitForVideoEvent(node, eventName, predicate, timeoutMs = 3000) {
  if (predicate()) return Promise.resolve(true);

  return new Promise((resolve) => {
    let done = false;
    const finish = (result) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      node.removeEventListener(eventName, onEvent);
      node.removeEventListener('error', onError);
      resolve(result);
    };
    const onEvent = () => finish(true);
    const onError = () => finish(false);
    const timer = setTimeout(() => finish(false), timeoutMs);

    node.addEventListener(eventName, onEvent, { once: true });
    node.addEventListener('error', onError, { once: true });
  });
}

function drawMediaToCanvas({ media, targetW, targetH, mediaW, mediaH, radii, objectFit, objectPosition }) {
  const width = Math.max(Math.ceil(targetW), 1);
  const height = Math.max(Math.ceil(targetH), 1);
  const canvas = document.createElement('canvas');
  const scale = 2;
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  ctx.scale(scale, scale);

  let r = { tl: 0, tr: 0, br: 0, bl: 0, ...radii };
  const factor = Math.min(
    width / (r.tl + r.tr) || Infinity,
    height / (r.tr + r.br) || Infinity,
    width / (r.br + r.bl) || Infinity,
    height / (r.bl + r.tl) || Infinity
  );

  if (factor < 1) {
    r = { tl: r.tl * factor, tr: r.tr * factor, br: r.br * factor, bl: r.bl * factor };
  }

  ctx.beginPath();
  ctx.moveTo(r.tl, 0);
  ctx.lineTo(width - r.tr, 0);
  ctx.arcTo(width, 0, width, r.tr, r.tr);
  ctx.lineTo(width, height - r.br);
  ctx.arcTo(width, height, width - r.br, height, r.br);
  ctx.lineTo(r.bl, height);
  ctx.arcTo(0, height, 0, height - r.bl, r.bl);
  ctx.lineTo(0, r.tl);
  ctx.arcTo(0, 0, r.tl, 0, r.tl);
  ctx.closePath();
  ctx.clip();

  const fitted = fitRectWithinBox(width, height, mediaW, mediaH);
  let renderX = fitted.x;
  let renderY = fitted.y;
  let renderW = fitted.w;
  let renderH = fitted.h;

  if (objectFit && objectFit !== 'contain') {
    const wRatio = width / mediaW;
    const hRatio = height / mediaH;
    const fitScale = objectFit === 'cover' ? Math.max(wRatio, hRatio) : Math.min(wRatio, hRatio);
    renderW = mediaW * fitScale;
    renderH = mediaH * fitScale;

    const parsePos = (value) => {
      if (value === 'left' || value === 'top') return 0;
      if (value === 'right' || value === 'bottom') return 1;
      if (String(value).includes('%')) return parseFloat(value) / 100;
      return 0.5;
    };
    const parts = String(objectPosition || '50% 50%').split(' ');
    const posX = parsePos(parts[0]);
    const posY = parsePos(parts[1] || parts[0]);
    renderX = (width - renderW) * posX;
    renderY = (height - renderH) * posY;
  }

  ctx.drawImage(media, renderX, renderY, renderW, renderH);
  return canvas.toDataURL('image/png');
}

async function captureVideoFirstFrame(node, widthPx, heightPx, radii, objectFit, objectPosition) {
  if (!node) return null;

  try {
    node.preload = 'auto';
    if (node.readyState === 0 && typeof node.load === 'function') {
      node.load();
    }
    node.pause();

    const hasMetadata = await waitForVideoEvent(
      node,
      'loadedmetadata',
      () => node.readyState >= 1 && node.videoWidth > 0 && node.videoHeight > 0
    );
    if (!hasMetadata) return null;

    if (Math.abs(node.currentTime || 0) > 0.001) {
      node.currentTime = 0;
      const seeked = await waitForVideoEvent(
        node,
        'seeked',
        () => Math.abs(node.currentTime || 0) <= 0.001
      );
      if (!seeked) return null;
    }

    const hasFrame = await waitForVideoEvent(node, 'loadeddata', () => node.readyState >= 2);
    if (!hasFrame) return null;

    return drawMediaToCanvas({
      media: node,
      targetW: widthPx,
      targetH: heightPx,
      mediaW: node.videoWidth,
      mediaH: node.videoHeight,
      radii,
      objectFit,
      objectPosition,
    });
  } catch {
    return null;
  }
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

export async function resolveVideoCoverData({
  posterSrc,
  widthPx,
  heightPx,
  radii,
  objectFit,
  objectPosition,
  node,
  captureElementImage,
  captureVideoFirstFrame: captureFirstFrame = captureVideoFirstFrame,
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

  const firstFrameData = await captureFirstFrame(
    node,
    widthPx,
    heightPx,
    radii,
    objectFit,
    objectPosition
  );
  if (firstFrameData) return firstFrameData;

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
  const videoSrc = resolveVideoSource(node);
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
