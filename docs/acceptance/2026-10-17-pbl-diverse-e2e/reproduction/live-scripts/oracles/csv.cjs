module.exports=async(p,e,s)=>{
 const t=id=>p.getByTestId(id),analyze=async text=>{await t('score-input').fill(text);await t('analyze-button').click();};
 await analyze('  小明  ,0\n\n小明,100\n坏行\n,40\n小红,101\n小绿,\n小蓝,50.5');
 await e(t('valid-table').locator('tbody tr')).toHaveCount(3);e(await t('valid-table').locator('tbody tr').first().locator('td').first().textContent()).toBe('小明');await e(t('stat-count')).toHaveText('3');await e(t('stat-average')).toHaveText('50.17');await e(t('stat-max')).toHaveText('100');s.push('混合合法非法行、空行、重复姓名、边界0/100及两位小数平均');
 const invalid=await t('invalid-item').allTextContents();e(invalid.length).toBe(4);for(const [index,line] of [4,5,6,7].entries())e(invalid[index]).toMatch(new RegExp('第\\s*'+line+'\\s*行'));s.push('错误保留原始行号');
 await analyze('新同学,80');await e(t('stat-count')).toHaveText('1');await e(t('stat-average')).toHaveText('80.00');await e(t('stat-max')).toHaveText('80');await e(t('invalid-item')).toHaveCount(0);s.push('重新分析完全替换旧有效和无效结果');
 await analyze('小明,abc');await e(t('stat-count')).toHaveText('0');await e(t('stat-average')).toHaveText('—');await e(t('stat-max')).toHaveText('—');s.push('无有效记录时空统计');
 await t('clear-button').click();await e(t('score-input')).toHaveValue('');await e(t('valid-table')).toHaveCount(0);await e(t('stats-panel')).toHaveCount(0);await e(t('invalid-item')).toHaveCount(0);s.push('清空输入与全部结果');
};
