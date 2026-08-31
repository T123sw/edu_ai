import type { Action } from '@openmaic/dsl';

const RUNTIME_ERROR_SHIM = `<script data-edu-runtime-error-shim>
(function () {
  function send(errorKind, message) {
    try {
      window.parent.postMessage({
        __eduClassroomInteractive: true,
        kind: 'runtime-error',
        errorKind: errorKind,
        message: String(message || 'interactive runtime error').slice(0, 1200)
      }, '*');
    } catch (ignored) {}
  }
  window.addEventListener('error', function (event) {
    if (event && event.message) send('error', event.message);
  }, true);
  window.addEventListener('unhandledrejection', function (event) {
    var reason = event && event.reason;
    send('unhandledrejection', (reason && (reason.stack || reason.message)) || reason);
  });
  try {
    var originalError = window.console && window.console.error;
    if (originalError) {
      window.console.error = function () {
        try {
          send('console.error', Array.prototype.map.call(arguments, String).join(' '));
        } catch (ignored) {}
        return originalError.apply(window.console, arguments);
      };
    }
  } catch (ignored) {}
})();
</script>`;

const USER_INTERACTION_SHIM = `<script data-edu-user-interaction-shim>
(function () {
  function notify(event) {
    try {
      var target = event && event.target;
      window.parent.postMessage({
        __eduClassroomInteractive: true,
        kind: 'user-interaction',
        actionId: target && (target.id || target.name) || undefined
      }, '*');
    } catch (ignored) {}
  }
  ['pointerdown', 'change', 'input'].forEach(function (type) {
    document.addEventListener(type, notify, true);
  });
})();
</script>`;

const STORAGE_SHIM = `<script data-edu-storage-shim>
(function () {
  function makeStore() {
    var data = Object.create(null);
    return {
      getItem: function (key) {
        key = String(key);
        return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
      },
      setItem: function (key, value) { data[String(key)] = String(value); },
      removeItem: function (key) { delete data[String(key)]; },
      clear: function () { data = Object.create(null); },
      key: function (index) { return Object.keys(data)[index] || null; },
      get length() { return Object.keys(data).length; }
    };
  }
  ['localStorage', 'sessionStorage'].forEach(function (name) {
    try {
      var store = window[name];
      store.getItem('__edu_probe__');
    } catch (error) {
      try {
        Object.defineProperty(window, name, {
          value: makeStore(),
          configurable: true
        });
      } catch (ignored) {}
    }
  });
})();
</script>`;

const IFRAME_STYLE = `<style data-edu-iframe-style>
html, body {
  width: 100%;
  height: 100%;
  min-height: 100%;
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  overflow-y: auto;
}
body { min-height: 100vh; }
</style>`;

export function patchInteractiveHtml(html: string): string {
  const compatibleHtml = patchLegacyWidgetScope(html);
  const injection = `${RUNTIME_ERROR_SHIM}\n${USER_INTERACTION_SHIM}\n${STORAGE_SHIM}\n${IFRAME_STYLE}\n`;
  const headMatch = /<head(?:\s[^>]*)?>/i.exec(compatibleHtml);
  if (!headMatch || headMatch.index === undefined) {
    return injection + compatibleHtml;
  }
  const insertAt = headMatch.index + headMatch[0].length;
  return (
    compatibleHtml.slice(0, insertAt) +
    injection +
    compatibleHtml.slice(insertAt)
  );
}

/**
 * Some OpenMAIC-generated widgets register their message bridge in one script
 * and keep `simState`/`handleCardClick` inside a later IIFE. Expose only those
 * two established bridge symbols when that legacy pattern is present.
 */
function patchLegacyWidgetScope(html: string): string {
  if (!/\bfunction\s+applyStateFromMessage\s*\(/.test(html)) return html;
  return html
    .replace(/\b(?:const|let)\s+simState\s*=/, 'window.simState =')
    .replace(
      /\bfunction\s+handleCardClick\s*\(/,
      'window.handleCardClick = function(',
    );
}

type WidgetMessageSender = (
  type: string,
  payload: Record<string, unknown>,
) => void;

export class WidgetMessageBuffer {
  private sender: WidgetMessageSender | null = null;
  private pending: Array<{
    type: string;
    payload: Record<string, unknown>;
  }> = [];

  postMessage(type: string, payload: Record<string, unknown>): void {
    if (this.sender) {
      this.sender(type, payload);
      return;
    }
    this.pending.push({ type, payload });
  }

  setSender(sender: WidgetMessageSender | null): void {
    this.sender = sender;
    if (!sender || !this.pending.length) return;
    const pending = this.pending;
    this.pending = [];
    pending.forEach((message) => sender(message.type, message.payload));
  }
}

export type WidgetActionMessage = {
  type:
    | 'SET_WIDGET_STATE'
    | 'HIGHLIGHT_ELEMENT'
    | 'ANNOTATE_ELEMENT'
    | 'REVEAL_ELEMENT';
  payload: Record<string, unknown>;
};

export function widgetMessageForAction(
  action: Action,
): WidgetActionMessage | null {
  switch (action.type) {
    case 'widget_setState':
      return {
        type: 'SET_WIDGET_STATE',
        payload: { state: action.state, content: action.content },
      };
    case 'widget_highlight':
      return {
        type: 'HIGHLIGHT_ELEMENT',
        payload: { target: action.target, content: action.content },
      };
    case 'widget_annotation':
      return {
        type: 'ANNOTATE_ELEMENT',
        payload: { target: action.target, content: action.content },
      };
    case 'widget_reveal':
      return {
        type: 'REVEAL_ELEMENT',
        payload: { target: action.target, content: action.content },
      };
    default:
      return null;
  }
}
