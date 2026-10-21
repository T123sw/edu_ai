import type { ProjectReport, ProjectStep, UiAction, ProjectCheck, UiTarget } from './projectTypes';
import { isJestCheck } from './nativeTests';

function targetLabel(target?:UiTarget): string {
  if(target?.within)return `${targetLabel(target.within)}中的${targetLabel({...target,within:undefined})}`;
  if(target?.index!=null)return `第 ${target.index+1} 个${targetLabel({...target,index:undefined})}`;
  if(target?.name)return target.name;
  if(target?.testId)return `标记为 ${target.testId} 的部件`;
  if(target?.role==='button')return '按钮';
  if(target?.role==='textbox')return '输入框';
  return '指定控件';
}

function describeAction(action: UiAction) {
  const target=targetLabel(action.target);
  if(action.type==='click')return `点击「${target}」`;
  if(action.type==='fill')return `在「${target}」输入 ${action.value}`;
  if(action.type==='press')return `在「${target}」按 ${action.value}`;
  if(action.assertion==='visible')return `「${target}」${action.expected===false?'不可见':'可见'}`;
  if(action.assertion==='enabled')return `「${target}」${action.expected===false?'禁用':'可操作'}`;
  if(action.assertion==='checked')return `「${target}」${action.expected===false?'未选中':'已选中'}`;
  if(action.assertion==='count')return `「${target}」数量为 ${action.expected}`;
  if(action.assertion==='above')return `「${target}」位于「${targetLabel(action.relativeTo)}」上方`;
  if(action.assertion==='not_overlapping')return `「${target}」之间互不重叠`;
  if(action.assertion==='within_viewport')return `「${target}」完整显示在检查窗口内`;
  return `「${target}」${action.assertion==='value'?'的值':'显示'}为 ${action.expected}`;
}
export function ProjectChecks({checks,step,report,currentHash,running,error,complete,onAsk}: {
  checks:ProjectCheck[];step:ProjectStep;report?:ProjectReport;currentHash:string;running:boolean;error:string;complete:boolean;onAsk(name:string):void;
}) {
  const current=Boolean(report&&report.codeHash===currentHash);
  const passed=current?checks.filter(c=>report?.results.some(r=>r.caseId===c.id&&r.status==='passed')).length:0;
  return <section className="pbl-checks-panel" aria-label="步骤验收">
    <header><div><h3>本步验收</h3><p>本步与之前的功能，共 {checks.length} 项</p></div><span>{running?'检查中':current?`${passed} / ${checks.length} 通过`:'待检查'}</span></header>
    <p className="pbl-checks-note">点击顶部“检查本步”，系统会独立运行当前工程并核对页面行为或接口响应。</p>
    {error&&<p role="alert" className="pbl-alert">{error}</p>}
    {report&&!current&&<p className="pbl-alert">代码已修改，以下是修改前的记录，请重新检查。</p>}
    {running&&<p role="status" className="pbl-checks-running">正在运行本步及前序检查…</p>}
    {checks.map(c=>{const result=report?.results.find(r=>r.caseId===c.id);return <article key={c.id} className={`pbl-check-card ${current?result?.status || '':''}`}>
      <div className="pbl-check-card-title"><strong>{c.label}</strong><span>{!current?'待检查':result?.status==='passed'?'通过':result?'未通过':'待检查'}</span></div>
      {!step.checkIds.includes(c.id)&&<small>前序回归</small>}
      {!isJestCheck(c)&&c.viewport&&<small>{c.viewport==='mobile'?'手机窗口（390 × 844）':'桌面窗口（1280 × 800）'}</small>}
      {isJestCheck(c)?<details><summary>测试代码</summary><pre>{c.source}</pre></details>:'engine' in c&&c.engine==='http'?<details><summary>接口请求与预期</summary><ol>{c.requests.map((request,index)=><li key={index}>{request.method} {request.path} → {request.status}<pre>{JSON.stringify(request.jsonBody??request.text??'',null,2)}</pre></li>)}</ol></details>:<details><summary>操作与预期</summary><ol>{c.actions.map((action,index)=><li key={index}>{describeAction(action)}</li>)}</ol></details>}
      {result&&<div className="pbl-check-evidence"><strong>{current?'实际执行记录':'历史执行记录'}</strong><pre>{result.message}</pre>{current&&result.status==='failed'&&<button onClick={()=>onAsk(c.label)}>请 AI 分析失败原因</button>}</div>}
    </article>;})}
    {complete&&<p role="status" className="pbl-project-complete">项目全部功能已在当前代码中通过检查。</p>}
  </section>;
}
