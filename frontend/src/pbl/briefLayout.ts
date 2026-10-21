// Group parsed Markdown blocks, so code fences, lists and reference links stay intact.
type Block = {type:string;value?:string;depth?:number;children?:Block[];data?:Record<string,unknown>};
type Options = {deliverable?:string;checks:string[]};
const content=(node:Block):string=>node.value??node.children?.map(content).join('')??'';
const heading=(title:string):Block=>({type:'heading',depth:3,children:[{type:'text',value:title}]});
const paragraph=(value:string):Block=>({type:'paragraph',children:[{type:'text',value}]});
const container=(children:Block[],className:string,label?:string):Block=>({
  type:'briefGroup',children,data:{hName:label?'section':'div',hProperties:{className,...(label?{'aria-label':label}:{})}},
});

export function remarkBriefLayout({deliverable,checks}:Options) {
  return (root:Block)=>{
    const left:Block[]=[],right:Block[]=[],definitions:Block[]=[];
    let group:Block[]=[],side=right,sectionDepth=0,hasOutcome=false;
    const flush=()=>{if(group.length)side.push(container(group,'pbl-brief-block'));group=[];};
    for(const node of root.children??[]){
      if(node.type==='definition'){definitions.push(node);continue;}
      const boldTitle=node.type==='paragraph'&&node.children?.length===1&&node.children[0].type==='strong';
      const title=node.type==='heading'||boldTitle?content(node).trim():'';
      if(title){
        const depth=node.depth??2;
        const outcome=/成果|完成效果|交付|产出|预期效果/.test(title);
        const context=outcome||/起点|已有|起始|代码约定|接口约定|文件约定|命名约定|标记约定/.test(title);
        const requirement=/要求|验收|检查|约束|边界|注意|步骤|任务/.test(title);
        // Explicit sections choose a column; nested headings otherwise stay with their parent.
        if(context||requirement||!sectionDepth||depth<=sectionDepth){
          flush();side=context?left:right;sectionDepth=depth;hasOutcome||=outcome;
        }
        group.push(boldTitle?heading(title):node);
      }else group.push(node);
    }
    flush();
    const introduction=right[0]?.children;
    if(introduction?.length&&introduction[0].type!=='heading')introduction.unshift(heading('任务要求'));
    if(deliverable?.trim()&&!hasOutcome)left.unshift(container([heading('完成成果'),paragraph(deliverable)],'pbl-brief-block'));
    if(checks.length)right.push(container([
      heading('本步验收'),
      paragraph('自动检查以下项目；未列出的布局与外观请在预览中确认。'),
      {type:'list',children:checks.map(label=>({type:'listItem',children:[paragraph(label)]}))},
    ],'pbl-brief-block pbl-brief-acceptance','本步验收'));
    // Keep the main deliverable and conventions first. Supporting sections follow
    // the introduction, so the columns can balance without splitting paragraphs.
    const supporting=(block:Block)=>/起点|已有|起始|完成效果|预期效果/.test(content(block.children?.[0]??block));
    const primary=left.filter(block=>!supporting(block));
    right.splice(Math.min(1,right.length),0,...left.filter(supporting));
    root.children=[...definitions,container([
      ...(primary.length?[container(primary,'pbl-brief-context','成果与代码约定')]:[]),
      ...(right.length?[container(right,'pbl-brief-requirements','要求与验收')]:[]),
    ],'pbl-brief-columns')];
  };
}
