import test from 'node:test';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {runUiCheck} from './pbl-ui-check.mjs';

test('清空后的零尺寸文字目标可检查，缺失、重复、隐藏和未清空仍失败',async()=>{
  const browser=await chromium.launch();
  const page=await browser.newPage();page.setDefaultTimeout(1500);
  const check={id:'empty',actions:[{type:'assert',target:{testId:'result'},assertion:'text',expected:''}]};
  try{
    await page.setContent('<button onclick="document.querySelector(\'span\').textContent=\'\'">清空</button><span data-testid="result">value</span>');
    assert.equal((await runUiCheck(page,check)).status,'failed');
    assert.equal((await runUiCheck(page,{...check,actions:[{type:'click',target:{role:'button',name:'清空'}},...check.actions]})).status,'passed');
    assert.equal(await page.getByTestId('result').isVisible(),false);
    for(const html of ['', '<span data-testid="result"></span><span data-testid="result"></span>', '<span data-testid="result" hidden></span>', '<div style="display:none"><span data-testid="result"></span></div>', '<span data-testid="result" style="visibility:hidden"></span>', '<div style="content-visibility:hidden"><span data-testid="result"></span></div>']){
      await page.setContent(html);assert.equal((await runUiCheck(page,check)).status,'failed',html);
    }
    await page.setContent('<span data-testid="result"></span>');
    assert.equal((await runUiCheck(page,{...check,actions:[{...check.actions[0],assertion:'visible',expected:true}]})).status,'failed');
    await page.setContent('<div style="visibility:hidden"><span data-testid="result" style="visibility:visible"></span></div>');
    assert.equal((await runUiCheck(page,check)).status,'passed');
  }finally{await browser.close()}
});
