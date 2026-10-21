export function workerSource(inspectSource) {
  return `
const inspectResult = ${inspectSource};
// Do not forward unbounded student logs through Sandpack's console bridge.
for (const name of ['log','info','warn','error','debug','trace','table','dir']) console[name] = () => {};
const emit = self.postMessage.bind(self);
self.postMessage = () => {};
self.onmessage = async ({data}) => {
  const send = result => emit({...result, completionToken:data.completionToken});
  let moduleUrl;
  try {
    moduleUrl = URL.createObjectURL(new Blob([data.code], {type:'text/javascript'}));
    const module = await import(moduleUrl);
    if (typeof module.quickSort !== 'function') throw new Error('EXPORT_MISSING');
    const result = inspectResult(module.quickSort, data.input, data.expected);
    try { send(result); }
    catch { send({passed:false,error:{code:'INVALID_RESULT',message:'不可序列化的结果'}}); }
  } catch (error) {
    const code = error instanceof SyntaxError ? 'SYNTAX_ERROR' :
      error && (error.message === 'NOT_IMPLEMENTED' || error.message === 'EXPORT_MISSING') ? error.message : 'RUNTIME_ERROR';
    send({passed:false,error:{code,message:code}});
  } finally { if (moduleUrl) URL.revokeObjectURL(moduleUrl); }
};`;
}
