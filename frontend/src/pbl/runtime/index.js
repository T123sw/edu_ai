import { createExecution } from './runner.js';
import './styles.css';
const channel = 'edu-pbl-v1';
const templateVersion = 'js-function-v1';
let port, sessionId, execution, activeRun;
const root = document.getElementById('app');
root.innerHTML = '<label for="input">输入数组</label><textarea id="input" spellcheck="false">[3,1,2]</textarea><p class="help">运行一次观察输入输出，检查练习验证全部用例。</p><div class="actions"><button id="sample">运行一次</button><button id="check">检查练习</button><button id="stop" disabled>停止</button></div><section id="result" aria-live="polite"><p class="empty">尚未运行 · 完成左侧代码后开始验证</p></section>';
const input = document.getElementById('input');
const result = document.getElementById('result');
const errorLabels = {NOT_IMPLEMENTED:'请先完成函数实现',INPUT_INVALID:'输入应为数字数组',SYNTAX_ERROR:'代码语法错误',EXPORT_MISSING:'缺少 quickSort 导出',RUNTIME_ERROR:'运行时发生错误',INVALID_RESULT:'返回值必须是有限数字数组',OUTPUT_MISMATCH:'输出与预期不一致',INPUT_MUTATED:'原输入数组被修改',RETURNED_INPUT:'需要返回一个新数组',TIMEOUT:'运行超时，请检查递归终止条件',CANCELED:'已停止',RUNTIME_UNAVAILABLE:'运行环境暂不可用'};
function busy(value) { document.getElementById('sample').disabled=value; document.getElementById('check').disabled=value; document.getElementById('stop').disabled=!value; }
function showReport(report, cases) {
  result.textContent='';
  const title=document.createElement('h3');
  const passed=report.results.filter(item=>item.status==='passed').length;
  title.textContent=report.status==='canceled'?'已停止运行':report.status==='timeout'?'运行超时':report.status==='passed'?'检查通过':'还需要调整';
  result.appendChild(title);
  const summary=document.createElement('p');summary.className='summary';summary.textContent=passed+' / '+cases.length+' 个用例通过 · '+report.durationMs+' ms';result.appendChild(summary);
  report.results.forEach(item=>{
    const testCase=cases.find(c=>c.id===item.caseId);
    const card=document.createElement('article');card.className='case '+(item.status==='passed'?'passed':'failed');
    const name=document.createElement('strong');name.textContent=(item.status==='passed'?'✓ ':'× ')+(testCase?testCase.label:item.caseId);card.appendChild(name);
    const detail=document.createElement('pre');detail.textContent='输入  '+JSON.stringify(testCase?testCase.input:[])+'\n预期  '+JSON.stringify(item.expected)+'\n实际  '+(item.actual?JSON.stringify(item.actual):'未得到有效结果');card.appendChild(detail);
    if(item.error){const error=document.createElement('p');error.textContent=errorLabels[item.error.code] || '执行失败';card.appendChild(error);}
    result.appendChild(card);
  });
}

const send = (type, fields = {}) => port && port.postMessage({channel,sessionId,type,...fields});
for (const mode of ['sample', 'check']) document.getElementById(mode).onclick = () => send('run-intent',{mode,customInputText:input.value});
input.oninput = () => send('input-changed',{customInputText:input.value});
document.getElementById('stop').onclick = () => { if (execution) execution.stop(); send('stop-request',{runId:activeRun}); };
function close() { busy(false); activeRun=null; if (execution) execution.stop(); execution = null; if (port) port.close(); port = null; }
window.addEventListener('pagehide',close);
window.addEventListener('message', event => {
  const data = event.data;
  // The host starts a challenge addressed to the specific preview window.
  if ((data && data.channel) !== channel || data.type !== 'connect' || typeof data.sessionId !== 'string' || event.ports.length !== 1) return;
  if (event.source !== window.parent && event.source !== window.top) return;
  close();
  sessionId = data.sessionId; port = event.ports[0];
  const connectedSession = sessionId;
  const connectedPort = port;
  const sendCurrent = (type, fields = {}) => { if (connectedSession === sessionId && connectedPort === port) connectedPort.postMessage({channel,sessionId:connectedSession,type,...fields}); };
  port.onmessage = async ({data}) => {
    if ((data && data.channel) !== channel || data.sessionId !== sessionId) return;
    if (data.type === 'request-check') { sendCurrent('run-intent',{mode:'check',customInputText:input.value}); return; }
    if (data.type === 'set-input' && typeof data.customInputText === 'string') input.value=data.customInputText;
    if (data.type === 'stop-request' && data.runId === activeRun) if (execution) execution.stop();
    if (data.type !== 'run-request' || typeof data.runId !== 'string' || typeof data.code !== 'string' || !Array.isArray(data.cases)) return;
    if (execution) execution.stop();
    activeRun = data.runId;
    const currentRun = activeRun;
    busy(true); result.textContent = '正在运行，请观察结果…';
    sendCurrent('run-started',{runId:data.runId,codeHash:data.codeHash});
    execution = createExecution(data, item => sendCurrent('case-result',{runId:data.runId,codeHash:data.codeHash,...item}));
    const report = await execution.result;
    if (connectedSession !== sessionId || connectedPort !== port || activeRun !== currentRun) return;
    busy(false); showReport(report,data.cases);
    sendCurrent('run-finished',report);
  };
  port.start();
  send('runtime-ready',{templateVersion, origin:location.origin});
});
// Announcement is discovery only. Host validates source/origin and establishes a port.
const announce = () => window.top.postMessage({channel,type:'runtime-announcement',templateVersion}, '*');
announce();
const announceTimer = setInterval(() => { if (!port) announce(); },1000);
window.addEventListener('pagehide',() => clearInterval(announceTimer));
