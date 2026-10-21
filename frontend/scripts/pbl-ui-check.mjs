import {observeLayout} from './pbl-layout-validation.mjs';
const clipped = (value, limit=160) => {
  const text=typeof value==='string'?JSON.stringify(value):String(value);
  return text.length>limit?text.slice(0,limit)+'…':text;
};
function describe(action) {
  const label=t=>(t.index==null?'':`第 ${t.index+1} 个 `)+clipped(t.name || t.testId || t.role || '控件',100);
  const target=(action.target.within?`${label(action.target.within)} 中的 `:'')+label(action.target);
  if(action.type==='click') return `点击 ${target}`;
  if(action.type==='fill') return `在 ${target} 输入 ${clipped(action.value)}`;
  if(action.type==='press') return `在 ${target} 按 ${clipped(action.value)}`;
  if(action.assertion==='above') return `检查 ${target} 位于 ${clipped(action.relativeTo?.name || action.relativeTo?.testId || action.relativeTo?.role || '指定控件',100)} 上方`;
  return `检查 ${target} 的${({visible:'可见状态',enabled:'可操作状态',count:'数量',text:'显示文字',value:'输入值',not_overlapping:'排列（互不重叠）',within_viewport:'位置（完整位于检查窗口内）'})[action.assertion] || '结果'}`;
}
function evidence(lines, final) {
  let body=lines.join('\n');
  if(body.length>1500){
    const recent=[];let length=0;
    for(const line of [...lines].reverse()){if(length+line.length>1450)break;recent.unshift(line);length+=line.length+1;}
    body='（较早的操作已省略）\n'+recent.join('\n');
  }
  return [body,final].filter(Boolean).join('\n').slice(0,2000);
}
async function observe(locator, assertion) {
  if(assertion==='count')return locator.count();
  if(assertion==='visible')return locator.isVisible();
  // An empty inline result naturally has no area. Reading its empty text is
  // valid even though Playwright's geometric visibility check returns false.
  // Explicitly hidden elements and non-unique targets still cannot pass.
  if(assertion==='text'&&await locator.count()===1){
    const empty=await locator.evaluate(element=>{
      if((element.textContent||'').trim()!=='')return false;
      for(let node=element;node;node=node.parentElement){
        const style=getComputedStyle(node);
        if(style.display==='none'||(node===element&&['hidden','collapse'].includes(style.visibility))||style.contentVisibility==='hidden')return false;
      }
      return element.isConnected;
    });
    if(empty)return '';
  }
  if(!(await locator.isVisible()))return '目标不可见或不存在';
  if(assertion==='enabled')return locator.isEnabled();
  if(assertion==='checked')return locator.isChecked();
  if(assertion==='text')return (await locator.textContent() || '').trim();
  if(assertion==='value')return locator.inputValue();
  throw new Error('未知断言');
}

export async function runUiCheck(page,check,load=async()=>{},errors=[]) {
      let actionIndex=0, description='加载页面', failure='页面加载未完成';
      const trace=[];
      try {
        await load();
        if(!Array.isArray(check.actions)||!check.actions.length||check.actions.length>100||!check.actions.some(a=>a.type==='assert')) throw new Error('无有效断言');
        for(const action of check.actions){
          actionIndex++;
          description=describe(action);
          failure='操作未完成：目标控件缺失、重复、不可见或无法操作。';
          const t=action.target;
          const select=async(root,t)=>{
            const matched=t.testId ? root.getByTestId(t.testId) : root.getByRole(t.role,t.name == null ? {} : {name:t.name,exact:true});
            if(t.index==null)return matched;
            const count=await matched.count();
            if(!Number.isInteger(t.index)||t.index<0||t.index>=count){failure=`目标索引 ${t.index} 越界：实际匹配 ${count} 个元素，索引从 0 开始。`;throw new Error(failure);}
            return matched.nth(t.index);
          };
          const locate=async t=>{
            if(!t.within)return select(page,t);
            const scope=await select(page,t.within);
            const count=await scope.count();
            if(count!==1){failure=`定位容器缺失或重复：实际匹配 ${count} 个。容器须唯一；顺序确定时可用 within.index 选一项，否则提供唯一名称或标记。`;throw new Error(failure);}
            return select(scope,t);
          };
          const locator = await locate(t);
          if(action.type!=='assert'||['visible','enabled','checked','text','value'].includes(action.assertion)){
            const count=await locator.count();
            if(count!==1)failure=`操作未完成：目标实际匹配 ${count} 个元素，单目标动作需要 1 个。${t.within?'within 只查找容器的后代，不包含其兄弟或父级；核对容器边界，顺序确定时也可直接用 target.index。':'顺序确定时可用 index，否则使用唯一名称或容器范围。'}`;
          }
          if(action.type === 'click') await locator.click();
          else if(action.type === 'fill') await locator.fill(action.value);
          else if(action.type === 'press') await locator.press(action.value);
          else if(action.type === 'assert'){
            const layout=['above','not_overlapping','within_viewport'].includes(action.assertion);
            const expected=layout?true:['visible','enabled','checked'].includes(action.assertion)?(action.expected??true):action.assertion==='count'?action.expected:String(action.expected);
            const deadline=Date.now()+1200;
            let actual;
            do {
              actual=layout?await observeLayout(page,locator,action.assertion,action.relativeTo?await locate(action.relativeTo):undefined):await observe(locator,action.assertion);
              if(actual===expected)break;
              await page.waitForTimeout(50);
            } while(Date.now()<deadline);
            failure=`预期：${clipped(expected,220)}\n实际：${clipped(actual,220)}`;
            if(actual!==expected)throw new Error('断言未通过');
            trace.push(`✓ ${actionIndex}. ${description}\n   实际：${clipped(actual,180)}`);
            continue;
          } else throw new Error('未知操作');
          trace.push(`✓ ${actionIndex}. ${description}`);
        }
        if(errors.length){description='页面运行';failure='检测到页面 JavaScript 运行错误，请查看预览中的错误提示。';throw new Error('页面运行错误');}
        return {caseId:check.id,status:'passed',message:evidence(trace,'本项操作与预期全部通过。')};
      } catch {
        return {caseId:check.id,status:'failed',message:evidence(trace,`× ${actionIndex || 1}. ${description}\n${failure}`)};
      }
}
