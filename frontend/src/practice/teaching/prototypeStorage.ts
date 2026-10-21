import { createPrototype, reducePrototype, type PrototypeAction } from './domains/bubbleSort';
export const STORAGE_KEY = 'edu-bubble-teaching-prototype-v1';
export function restorePrototype(raw: string | null) {
  if (!raw) return { state: createPrototype(), actions: [] as PrototypeAction[], warning: '' };
  try {
    const data = JSON.parse(raw);
    if (data.version !== 1 || !Array.isArray(data.actions) || data.actions.length > 4000) throw Error('Invalid history');
    for (const action of data.actions) {
      if (!action || typeof action !== 'object') throw Error('Invalid action');
      if (action.type === 'phase') { if (!['demo', 'practice'].includes(action.phase)) throw Error('Invalid phase'); }
      else if (action.type === 'select') { if (!Number.isInteger(action.index)) throw Error('Invalid selection'); }
      else if (action.type === 'decide') { if (typeof action.swap !== 'boolean') throw Error('Invalid decision'); }
      else if (!['compare', 'finish-round', 'keep-example', 'clear', 'hint', 'reset'].includes(action.type)) throw Error('Unknown action');
    }
    const actions: PrototypeAction[] = data.actions;
    return { state: actions.reduce(reducePrototype, createPrototype()), actions, warning: '' };
  } catch { return { state: createPrototype(), actions: [] as PrototypeAction[], warning: '上次原型记录无法恢复，已从起点开始。' }; }
}
