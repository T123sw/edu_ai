import { expect, test } from './fixtures/teacherApp';

test('revision is tracked by the global task manager and returns version controls', async ({teacherPage: page}) => {
  let submitted=false;
  const ref={artifact_id:'report-1',artifact_type:'report',version_id:'v2',source_course_id:'course-physics',title:'数组报告'};
  const result={message:{role:'assistant',content:'已保存《数组报告》第 2 版，原第 1 版副本已保留。'},conversation:{conversation_id:'conv-revision'},action:{name:'artifact.revise'},sources:[],artifacts:[],trace:{path:'fast'},artifact_revision:{status:'completed',message:'已保存新版本',artifact_reference:ref,base_version_id:'v1',summary:'已修改 1 处内容',changes:[],operation_id:'op-1'}};
  const job={schema_version:2,version:2,edu_job_id:'revision-job',kind:'revise_artifact',status:'succeeded',step:'completed',progress:100,message:result.message.content,owner_user_id:'teacher-a',course_id:'course-physics',scope_type:'course',input_summary:{title:'数组报告'},result_ref:{resource_type:'artifact_revision',course_id:'course-physics',material_type:'report',material_id:'report-1',version:2,base_version:1},retryable:false,cancelable:false,created_at:'2026-09-07T10:00:00Z',updated_at:'2026-09-07T10:00:10Z'};
  await page.route('**/api/personal-knowledge/documents**', r=>r.fulfill({json:[]}));
  await page.route('**/api/jobs**', r=>r.fulfill({json:new URL(r.request().url()).pathname.endsWith('/jobs') ? {items:submitted?[job]:[],next_cursor:null,server_time:'2026-09-07T10:00:10Z'} : job}));
  await page.route('**/api/chat/tasks/revision-job',r=>r.fulfill({json:{task_id:'revision-job',workflow_type:'artifact_revision',status:'succeeded',result}}));
  await page.route('**/api/chat/v2/stream', async r=>{
    submitted=true;
    const events=[{type:'metadata',payload:{conversation_id:'conv-revision'}},{type:'task_submitted',payload:{task_id:'revision-job',workflow_type:'artifact_revision'}},{type:'done',payload:{conversation_id:'conv-revision'}}];
    await r.fulfill({contentType:'text/event-stream',body:events.map(e=>`data: ${JSON.stringify(e)}\n\n`).join('')});
  });
  await page.goto('/#ai?course_id=course-physics');
  const input=page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await expect(input).toBeVisible({timeout:20000});
  await input.fill('修改上次的报告，增加案例');
  await input.press('Enter');
  await expect(page.getByText(result.message.content,{exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByText('正在修改：《数组报告》 · 第 2 版')).toBeVisible();
  await page.getByRole('button',{name:'查看新版',exact:true}).click();
  await expect(page).toHaveURL(/material_id=report-1/);
});

test('resource page exposes the retained original version', async ({teacherPage:page}) => {
  const material={material_id:'report-1',material_type:'report',course_id:'course-physics',owner_user_id:'teacher-a',visibility:'private',version:2,title:'数组报告',content:'新版正文',scope_type:'course'};
  await page.route('**/api/courses/*/materials**',r=>r.fulfill({json:new URL(r.request().url()).pathname.endsWith('/materials')?[material]:material}));
  await page.route('**/api/chat/v2/artifacts/revisions/read',async r=>{
    expect(r.request().postDataJSON().version).toBe(1);
    await r.fulfill({json:{...material,version:1,content:'原版副本保留的独特正文'}});
  });
  await page.goto('/#resources?course_id=course-physics&material_type=report&material_id=report-1');
  await page.getByRole('button',{name:'历史版本与原版副本'}).click();
  await page.getByRole('button',{name:'查看此版本'}).click();
  await expect(page.getByText('原版副本保留的独特正文')).toBeVisible();
});
