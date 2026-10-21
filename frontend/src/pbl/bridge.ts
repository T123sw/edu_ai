export const CHANNEL = 'edu-pbl-v1';
export const BUNDLER_URL = 'https://2-19-8-sandpack.codesandbox.io';
export interface RuntimeMessage { channel: string; sessionId: string; type: string; [key: string]: unknown }
export function connectPreview(getFrame: () => HTMLIFrameElement | null, receive: (message: RuntimeMessage) => void) {
  let port: MessagePort | undefined;
  let sessionId = '';
  const listener = (event: MessageEvent) => {
    if (event.data?.channel !== CHANNEL || event.data.type !== 'runtime-announcement') return;
    const frame = getFrame();
    if (!frame?.contentWindow || event.origin !== new URL(BUNDLER_URL).origin || event.source !== frame.contentWindow) return;
    port?.close(); sessionId = crypto.randomUUID();
    const connection = new MessageChannel(); port = connection.port1;
    port.onmessage = ({data}) => {
      if (data?.channel === CHANNEL && data.sessionId === sessionId && typeof data.type === 'string') receive(data);
    };
    port.start();
    frame.contentWindow.postMessage({channel:CHANNEL,type:'connect',sessionId},event.origin,[connection.port2]);
  };
  window.addEventListener('message',listener);
  return {
    send(type: string, fields: Record<string, unknown> = {}) { port?.postMessage({channel:CHANNEL,sessionId,type,...fields}); },
    close() { window.removeEventListener('message',listener); port?.close(); port = undefined; },
  };
}
