# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: pbl-scroll.spec.ts >> 长代码的滚动条和末行始终位于代码面板内（文件列表关闭）
- Location: tests/live-learning/pbl-scroll.spec.ts:103:44

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 384
Received: 527
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - link "返回首页" [ref=e5] [cursor=pointer]:
      - /url: "#/"
      - generic [ref=e6]: Edu AI
    - navigation "主导航" [ref=e11]:
      - link "AI 课堂" [ref=e12] [cursor=pointer]:
        - /url: "#/"
      - link "互动实验" [ref=e13] [cursor=pointer]:
        - /url: "#/practice"
      - link "考试模拟" [ref=e14] [cursor=pointer]:
        - /url: "#/exam"
      - link "我的资源" [ref=e15] [cursor=pointer]:
        - /url: "#/my-resources"
    - generic [ref=e16]:
      - button "后台任务" [ref=e17] [cursor=pointer]
      - button "页面配色" [ref=e23] [cursor=pointer]
      - link "个人中心" [ref=e30] [cursor=pointer]:
        - /url: "?account=1#profile"
        - text: p
  - main [ref=e31]:
    - generic [ref=e32]:
      - generic [ref=e33]:
        - link "返回互动实验" [ref=e34] [cursor=pointer]:
          - /url: "#/practice"
          - text: ←
        - heading "动手实现计数器" [level=1] [ref=e35]
        - generic [ref=e36]: 第 1 / 2 步
      - heading "构建按钮" [level=2] [ref=e38]
      - generic [ref=e40]:
        - region "成果与代码约定" [ref=e41]:
          - generic [ref=e42]:
            - heading "完成成果" [level=3] [ref=e43]
            - paragraph [ref=e44]: 按钮
        - region "要求与验收" [ref=e45]:
          - generic [ref=e46]:
            - heading "任务要求" [level=3] [ref=e47]
            - paragraph [ref=e48]: 创建一个按钮，文字为「增加」。
          - region "本步验收" [ref=e49]:
            - heading "本步验收" [level=3] [ref=e50]
            - paragraph [ref=e51]: 自动检查以下项目；未列出的布局与外观请在预览中确认。
            - list [ref=e52]:
              - listitem [ref=e53]: 增加按钮可以点击
    - region "编程工作区" [ref=e54]:
      - generic [ref=e55]:
        - button "↑ 返回题目" [ref=e56] [cursor=pointer]
        - generic [ref=e57]: 工作区
        - generic [ref=e58]:
          - button "AI 辅导" [ref=e59] [cursor=pointer]
          - status [ref=e60]: 完成后检查本步
          - button "检查本步" [ref=e61] [cursor=pointer]
          - button "下一步 →" [ref=e62] [cursor=pointer]
          - group [ref=e63]:
            - generic "工程操作 ▾" [ref=e64] [cursor=pointer]
      - generic [ref=e67]:
        - navigation "练习步骤" [ref=e68]:
          - generic [ref=e69]:
            - heading "练习步骤" [level=2] [ref=e70]
            - generic [ref=e71]: 0 / 2 已通过
          - list [ref=e72]:
            - listitem [ref=e73]:
              - button "构建按钮 当前步骤 · 待检查" [ref=e74] [cursor=pointer]:
                - generic [ref=e75]: "1"
                - generic [ref=e76]:
                  - strong [ref=e77]: 构建按钮
                  - generic [ref=e78]: 当前步骤 · 待检查
            - listitem [ref=e79]:
              - button "实现递增 待检查" [ref=e80] [cursor=pointer]:
                - generic [ref=e81]: "2"
                - generic [ref=e82]:
                  - strong [ref=e83]: 实现递增
                  - generic [ref=e84]: 待检查
        - generic [ref=e87]:
          - navigation "工作区视图" [ref=e88]:
            - button "代码" [pressed] [ref=e89] [cursor=pointer]
            - button "预览与验收" [ref=e90] [cursor=pointer]
          - region "代码编辑区" [ref=e93]:
            - strong [ref=e95]: 代码
            - generic [ref=e97]:
              - tablist "Select active file" [ref=e99]:
                - tab [selected] [ref=e100]:
                  - button "App.jsx" [ref=e101] [cursor=pointer]
                - tab [ref=e102]:
                  - button "styles.css" [ref=e103] [cursor=pointer]
              - tabpanel "App.jsx" [ref=e104]:
                - textbox "Code Editor for App.jsx" [ref=e105]:
                  - generic [ref=e107]:
                    - generic [ref=e109]:
                      - generic [ref=e110]: "99"
                      - generic [ref=e111]: "100"
                      - generic [ref=e112]: "101"
                      - generic [ref=e113]: "102"
                      - generic [ref=e114]: "103"
                      - generic [ref=e115]: "104"
                      - generic [ref=e116]: "105"
                      - generic [ref=e117]: "106"
                      - generic [ref=e118]: "107"
                      - generic [ref=e119]: "108"
                      - generic [ref=e120]: "109"
                      - generic [ref=e121]: "110"
                      - generic [ref=e122]: "111"
                      - generic [ref=e123]: "112"
                      - generic [ref=e124]: "113"
                      - generic [ref=e125]: "114"
                      - generic [ref=e126]: "115"
                      - generic [ref=e127]: "116"
                      - generic [ref=e128]: "117"
                      - generic [ref=e129]: "118"
                      - generic [ref=e130]: "119"
                      - generic [ref=e131]: "120"
                      - generic [ref=e132]: "121"
                      - generic [ref=e133]: "122"
                      - generic [ref=e134]: "123"
                      - generic [ref=e135]: "124"
                      - generic [ref=e136]: "125"
                      - generic [ref=e137]: "126"
                      - generic [ref=e138]: "127"
                      - generic [ref=e139]: "128"
                      - generic [ref=e140]: "129"
                      - generic [ref=e141]: "130"
                      - generic [ref=e142]: "131"
                      - generic [ref=e143]: "132"
                      - generic [ref=e144]: "133"
                      - generic [ref=e145]: "134"
                      - generic [ref=e146]: "135"
                      - generic [ref=e147]: "136"
                      - generic [ref=e148]: "137"
                      - generic [ref=e149]: "138"
                      - generic [ref=e150]: "139"
                      - generic [ref=e151]: "140"
                      - generic [ref=e152]: "141"
                      - generic [ref=e153]: "142"
                      - generic [ref=e154]: "143"
                      - generic [ref=e155]: "144"
                      - generic [ref=e156]: "145"
                      - generic [ref=e157]: "146"
                      - generic [ref=e158]: "147"
                      - generic [ref=e159]: "148"
                      - generic [ref=e160]: "149"
                      - generic [ref=e161]: "150"
                      - generic [ref=e162]: "151"
                      - generic [ref=e163]: "152"
                      - generic [ref=e164]: "153"
                      - generic [ref=e165]: "154"
                      - generic [ref=e166]: "155"
                      - generic [ref=e167]: "156"
                      - generic [ref=e168]: "157"
                      - generic [ref=e169]: "158"
                      - generic [ref=e170]: "159"
                      - generic [ref=e171]: "160"
                      - generic [ref=e172]: "161"
                    - textbox "Code Editor for App.jsx" [ref=e173]:
                      - generic [ref=e175]: // 滚动检查 97
                      - generic [ref=e176]: // 滚动检查 98
                      - generic [ref=e177]: // 滚动检查 99
                      - generic [ref=e178]: // 滚动检查 100
                      - generic [ref=e179]: // 滚动检查 101
                      - generic [ref=e180]: // 滚动检查 102
                      - generic [ref=e181]: // 滚动检查 103
                      - generic [ref=e182]: // 滚动检查 104
                      - generic [ref=e183]: // 滚动检查 105
                      - generic [ref=e184]: // 滚动检查 106
                      - generic [ref=e185]: // 滚动检查 107
                      - generic [ref=e186]: // 滚动检查 108
                      - generic [ref=e187]: // 滚动检查 109
                      - generic [ref=e188]: // 滚动检查 110
                      - generic [ref=e189]: // 滚动检查 111
                      - generic [ref=e190]: // 滚动检查 112
                      - generic [ref=e191]: // 滚动检查 113
                      - generic [ref=e192]: // 滚动检查 114
                      - generic [ref=e193]: // 滚动检查 115
                      - generic [ref=e194]: // 滚动检查 116
                      - generic [ref=e195]: // 滚动检查 117
                      - generic [ref=e196]: // 滚动检查 118
                      - generic [ref=e197]: // 滚动检查 119
                      - generic [ref=e198]: // 滚动检查 120
                      - generic [ref=e199]: // 滚动检查 121
                      - generic [ref=e200]: // 滚动检查 122
                      - generic [ref=e201]: // 滚动检查 123
                      - generic [ref=e202]: // 滚动检查 124
                      - generic [ref=e203]: // 滚动检查 125
                      - generic [ref=e204]: // 滚动检查 126
                      - generic [ref=e205]: // 滚动检查 127
                      - generic [ref=e206]: // 滚动检查 128
                      - generic [ref=e207]: // 滚动检查 129
                      - generic [ref=e208]: // 滚动检查 130
                      - generic [ref=e209]: // 滚动检查 131
                      - generic [ref=e210]: // 滚动检查 132
                      - generic [ref=e211]: // 滚动检查 133
                      - generic [ref=e212]: // 滚动检查 134
                      - generic [ref=e213]: // 滚动检查 135
                      - generic [ref=e214]: // 滚动检查 136
                      - generic [ref=e215]: // 滚动检查 137
                      - generic [ref=e216]: // 滚动检查 138
                      - generic [ref=e217]: // 滚动检查 139
                      - generic [ref=e218]: // 滚动检查 140
                      - generic [ref=e219]: // 滚动检查 141
                      - generic [ref=e220]: // 滚动检查 142
                      - generic [ref=e221]: // 滚动检查 143
                      - generic [ref=e222]: // 滚动检查 144
                      - generic [ref=e223]: // 滚动检查 145
                      - generic [ref=e224]: // 滚动检查 146
                      - generic [ref=e225]: // 滚动检查 147
                      - generic [ref=e226]: // 滚动检查 148
                      - generic [ref=e227]: // 滚动检查 149
                      - generic [ref=e228]: // 滚动检查 150
                      - generic [ref=e229]: // 滚动检查 151
                      - generic [ref=e230]: // 滚动检查 152
                      - generic [ref=e231]: // 滚动检查 153
                      - generic [ref=e232]: // 滚动检查 154
                      - generic [ref=e233]: // 滚动检查 155
                      - generic [ref=e234]: // 滚动检查 156
                      - generic [ref=e235]: // 滚动检查 157
                      - generic [ref=e236]: // 滚动检查 158
                      - generic [ref=e237]: // 滚动检查 159
```

# Test source

```ts
  23  |   return {get:()=>workspace,offline:(v:boolean)=>{failSave=v;}};
  24  | }
  25  | 
  26  | test('滚轮平滑进入整屏工作区并返回，半屏预览不吞滚轮',async({page})=>{
  27  |   await fixture(page);await page.emulateMedia({reducedMotion:'no-preference'});
  28  |   await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  29  |   await page.setViewportSize({width:1920,height:911});await page.goto('/#/practice/code/pbl_project_fixture');
  30  |   const stage=page.locator('.pbl-workbench-stage');await expect(stage).toHaveAttribute('data-focused','false');
  31  |   await expect(page.locator('.sp-editor')).toBeVisible();
  32  |   // The reading area grows with the requirements and acceptance instructions.
  33  |   const initial=await stage.boundingBox();expect(initial!.y).toBeGreaterThan(911*.4);expect(initial!.y).toBeLessThan(911*.8);
  34  |   await page.screenshot({path:'/tmp/pbl-scroll-before-1920.png'});
  35  |   const editor=await page.locator('.cm-content').elementHandle(),frame=await page.locator('.sp-preview iframe').elementHandle();
  36  |   const samples=page.evaluate(()=>new Promise<number[]>(resolve=>{const values:number[]=[];const start=performance.now();const tick=()=>{values.push(document.querySelector('.sl-app')!.scrollTop);if(performance.now()-start>1000)resolve(values);else requestAnimationFrame(tick);};tick();}));
  37  |   await page.mouse.move(900,240);await page.mouse.wheel(0,120);
  38  |   await expect(stage).toHaveAttribute('data-focused','true');
  39  |   const positions=await samples,end=await page.locator('.sl-app').evaluate(el=>el.scrollTop);
  40  |   expect(new Set(positions.filter(n=>n>1&&n<end-1)).size).toBeGreaterThan(3);
  41  |   await expect(page.getByRole('heading',{name:'构建按钮',exact:true})).not.toBeInViewport();await expect(page.locator('.sl-header')).not.toBeInViewport();
  42  |   expect(Math.abs((await stage.boundingBox())!.y)).toBeLessThan(1);
  43  |   await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});
  44  |   await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
  45  |   const toolbar=page.locator('.pbl-stage-toolbar');
  46  |   await expect(toolbar.getByRole('button',{name:'检查本步',exact:true})).toBeVisible();
  47  |   await expect(page.locator('.pbl-project-footer')).toHaveCount(0);
  48  |   await expect(page.getByRole('button',{name:'问 AI',exact:true})).toHaveCount(0);
  49  |   await expect(page.getByRole('button',{name:'收起 AI 辅导'})).toHaveCount(0);
  50  |   await expect(page.getByTestId('save-status')).toBeHidden();
  51  |   await toolbar.getByText('工程操作',{exact:true}).click();
  52  |   const menu=page.locator('.pbl-project-tools>div');await expect(menu.getByRole('button',{name:'同步',exact:true})).toBeVisible();
  53  |   expect((await menu.boundingBox())!.y).toBeGreaterThan((await toolbar.boundingBox())!.y);
  54  |   await toolbar.getByText('工程操作',{exact:true}).click();
  55  |   const body=await page.locator('.pbl-workbench-body').boundingBox();
  56  |   expect(911-body!.y-body!.height).toBeLessThanOrEqual(13);
  57  |   await page.screenshot({path:'/tmp/pbl-scroll-after-1920.png'});
  58  |   await page.mouse.move(900,28);await page.mouse.wheel(0,-120);
  59  |   await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(0);
  60  |   await page.waitForTimeout(750); // End the return gesture before starting a fresh gesture over the preview.
  61  |   await page.mouse.move(1000,650);await page.mouse.wheel(0,120);await expect(stage).toHaveAttribute('data-focused','true');
  62  |   expect(await editor!.evaluate(el=>el.isConnected)).toBe(true);expect(await frame!.evaluate(el=>el.isConnected)).toBe(true);
  63  | });
  64  | 
  65  | test('工作区内独立滚动并保留草稿，缩放和手机切换不挤出操作区',async({page})=>{
  66  |   await fixture(page);await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  67  |   await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  68  |   await edit(page,solution+'\n'+Array.from({length:100},(_,i)=>`// 保留代码 ${i}`).join('\n'));
  69  |   if(await page.locator('#pbl-tutor-toggle').getAttribute('aria-expanded')!=='true')await page.locator('#pbl-tutor-toggle').click();await page.getByLabel('向编程辅导提问').fill('翻页前的草稿');
  70  |   const outer=await page.locator('.sl-app').evaluate(el=>el.scrollTop),codeScroll=page.locator('.cm-scroller');
  71  |   await codeScroll.evaluate(el=>{el.scrollTop=100;});const before=await codeScroll.evaluate(el=>el.scrollTop);
  72  |   await codeScroll.hover();await page.mouse.wheel(0,180);await expect.poll(()=>codeScroll.evaluate(el=>el.scrollTop)).toBeGreaterThan(before);
  73  |   expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
  74  |   await codeScroll.evaluate(el=>{el.scrollTop=0;});await page.mouse.wheel(0,-180);await page.waitForTimeout(250);expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
  75  |   await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await enterWorkbench(page);
  76  |   await expect(page.getByLabel('向编程辅导提问')).toHaveValue('翻页前的草稿');await expect(page.locator('.cm-content')).toContainText('保留代码');
  77  |   for(const width of [1440,1024,768,390,320]){
  78  |     await page.setViewportSize({width,height:844});await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');
  79  |     if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
  80  |     await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});await expect(page.getByRole('button',{name:'检查本步',exact:true})).toBeInViewport();
  81  |     if(width<=760)await page.getByRole('button',{name:'预览与验收',exact:true}).click();
  82  |     await expect(page.locator('.sp-preview')).toBeInViewport({ratio:1});
  83  |     expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  84  |     if([1440,390].includes(width))await page.screenshot({path:`/tmp/pbl-scroll-after-${width}.png`});
  85  |   }
  86  | });
  87  | 
  88  | test('长题目可以完整阅读，切到短题目后工作区保持满屏',async({page})=>{
  89  |   await fixture(page);await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  90  |   const long=structuredClone(artifact);long.tasks[0].instructionsMarkdown=Array.from({length:25},(_,i)=>`第 ${i+1} 条要求：先观察按钮，再编写对应的事件。`).join('\n\n');
  91  |   await page.route('**/api/pbl/pbl_project_fixture',route=>route.fulfill({json:{artifact:long,job:null}}));
  92  |   await page.goto('/#/practice/code/pbl_project_fixture');await expect(page.locator('.pbl-problem-reading')).toContainText('第 25 条要求');
  93  |   await page.mouse.move(600,350);await page.mouse.wheel(0,120);await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
  94  |   await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','false');
  95  |   await enterWorkbench(page);await page.getByRole('button',{name:'下一步 →',exact:true}).click();
  96  |   await page.getByRole('button',{name:'检查本步',exact:true}).click();await expect(page.getByTestId('task-status')).toHaveText('还需要调整');
  97  |   await expect(page.locator('.pbl-workbench-stage')).toHaveAttribute('data-focused','true');await expect(page.locator('.sp-editor')).toBeInViewport({ratio:1});
  98  |   await page.getByRole('button',{name:'↑ 返回题目',exact:true}).click();await expect.poll(()=>page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(0);
  99  |   await expect(page.getByRole('heading',{name:'实现递增',exact:true})).toBeInViewport();
  100 | });
  101 | 
  102 | 
  103 | for(const withExplorer of [false,true])test(`长代码的滚动条和末行始终位于代码面板内（文件列表${withExplorer?'开启':'关闭'}）`,async({page},testInfo)=>{
  104 |   await fixture(page);
  105 |   await page.route('https://2-19-8-sandpack.codesandbox.io/**',route=>route.abort());
  106 |   if(withExplorer)await page.route('**/api/pbl/pbl_project_fixture',route=>route.fulfill({json:{artifact:{...artifact,runtime:{template:'react',entry:'/src/App.jsx',dependencies:{react:'18.3.1','react-dom':'18.3.1'},moduleType:'commonjs'}},job:null}}));
  107 |   await page.setViewportSize({width:1440,height:900});
  108 |   await page.goto('/#/practice/code/pbl_project_fixture');await enterWorkbench(page);
  109 |   await edit(page,solution+'\n'+Array.from({length:160},(_,i)=>`// 滚动检查 ${i}`).join('\n'));
  110 |   if(withExplorer)await page.locator('.pbl-file-explorer summary').click();
  111 |   const scroller=page.locator('.cm-scroller');
  112 |   for(const width of [1440,390,320]){
  113 |     await page.setViewportSize({width,height:900});
  114 |     if(width<=760)await page.getByRole('button',{name:'代码',exact:true}).click();
  115 |     await expect(scroller).toBeInViewport({ratio:1});
  116 |     expect(await scroller.evaluate(el=>el.scrollHeight-el.clientHeight)).toBeGreaterThan(100);
  117 |     await scroller.evaluate(el=>{el.scrollTop=el.scrollHeight;});
  118 |     await expect(page.locator('.cm-line').filter({hasText:'// 滚动检查 159'})).toBeInViewport();
  119 |     await page.screenshot({path:testInfo.outputPath(`editor-${width}.png`)});
  120 |     const outer=await page.locator('.sl-app').evaluate(el=>el.scrollTop);
  121 |     await scroller.hover();await page.mouse.wheel(0,-250);
  122 |     await expect.poll(()=>scroller.evaluate(el=>el.scrollHeight-el.clientHeight-el.scrollTop)).toBeGreaterThan(100);
> 123 |     expect(await page.locator('.sl-app').evaluate(el=>el.scrollTop)).toBe(outer);
      |                                                                      ^ Error: expect(received).toBe(expected) // Object.is equality
  124 |   }
  125 | });
  126 | 
```