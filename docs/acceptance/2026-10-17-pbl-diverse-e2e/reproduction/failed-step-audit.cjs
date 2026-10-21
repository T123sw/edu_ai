const fs=require('node:fs'),{withFiles}=require('./runtime.cjs');
const root=__dirname+'/fixtures',out=__dirname+'/replay';
const read=p=>JSON.parse(fs.readFileSync(p));
(async()=>{const {checkProject}=await import('../../../../frontend/scripts/check-pbl-project.mjs');const results=[];
 for(const name of ['quiz','expense']){const cp=read(root+'/matrix_'+name+'/private.json').checkpoint,candidate=cp.lastCandidate,files=candidate.referenceFiles,checks=[...cp.completed.flatMap(s=>s.candidate.checks),...candidate.checks];const scenarios=[];const result={name,generationFailed:true,issues:cp.failureContext.issues};
 try{await withFiles(files,async(p,e)=>{const t=id=>p.getByTestId(id);
 if(name==='quiz'){
  await e(t('submit')).toBeDisabled();scenarios.push('未选择时提交按钮禁用');
  await t('option').nth(0).click();await e(t('submit')).toBeEnabled();await t('submit').click();await e(t('feedback')).toHaveText('回答错误');await e(t('correct-answer')).toHaveText('正确答案：5');await e(t('submit')).toBeDisabled();scenarios.push('错误答案反馈及提交后禁止重复提交');
  await t('option').nth(1).click();await e(t('option').nth(0)).toHaveAttribute('aria-checked','true');await e(t('option').nth(1)).toHaveAttribute('aria-checked','false');scenarios.push('提交后选项锁定');
 }else{
  await t('note-input').fill('   ');await t('amount-input').fill('10');await t('add-button').click();await e(t('expense-item')).toHaveCount(0);await e(t('error-message')).toBeVisible();scenarios.push('空白备注拒绝');
  await t('note-input').fill('测试');for(const amount of ['0','-5','1.234','abc','']){await t('amount-input').fill(amount);await t('add-button').click();await e(t('expense-item')).toHaveCount(0);await e(t('error-message')).toBeVisible();scenarios.push('金额拒绝 '+JSON.stringify(amount));}
  await t('note-input').fill('  午餐  ');await t('amount-input').fill('12.50');await t('category-select').selectOption('餐饮');await t('add-button').click();await e(t('expense-item')).toHaveText(['午餐12.50餐饮']);scenarios.push('合法输入去空格并保留金额分类');
 }
 await p.screenshot({path:out+'/'+name+'-failed-step-correct-code.png',fullPage:true});});result.independentCurrentStepPassed=true;}
 catch(e){result.independentCurrentStepPassed=false;result.independentError=e.stack;}
 result.scenarios=scenarios;result.directCumulativeBrowserReport=await checkProject({files,checks});results.push(result);fs.writeFileSync(out+'/failed-step-audit.json',JSON.stringify(results,null,2));console.log(name,result.independentCurrentStepPassed,'direct runtime',result.directCumulativeBrowserReport.passed);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
