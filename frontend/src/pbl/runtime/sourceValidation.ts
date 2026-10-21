import { parse } from 'acorn';
export interface SourceIssue {code: string; message: string}
interface AstNode {type: string; [key: string]: unknown}
const forbiddenNames = new Set(['postMessage','close','addEventListener','removeEventListener','dispatchEvent','onmessage','window','document','globalThis','self','fetch','XMLHttpRequest','WebSocket','Worker','SharedWorker','navigator','location','importScripts','eval','Function','setTimeout','setInterval','requestAnimationFrame']);
export function validateSource(code: string): {ok: boolean; issues: SourceIssue[]} {
  const issues: SourceIssue[] = [];
  const issue = (message: string, kind = 'UNSUPPORTED_SOURCE') => { if (!issues.some(i=>i.message===message)) issues.push({code:kind,message}); };
  if (new TextEncoder().encode(code).length > 128 * 1024) return {ok:false,issues:[{code:'UNSUPPORTED_SOURCE',message:'源码超过 128 KiB'}]};
  let tree: AstNode;
  try { tree = parse(code,{ecmaVersion:'latest',sourceType:'module'}) as unknown as AstNode; }
  catch { return {ok:false,issues:[{code:'SYNTAX_ERROR',message:'JavaScript 语法错误'}]}; }
  let hasExport = false;
  for (const statement of tree.body as AstNode[]) {
    const declaration = statement.type==='ExportNamedDeclaration' ? statement.declaration as AstNode | null : statement;
    if (statement.type==='ExportNamedDeclaration') {
      if (declaration?.type==='FunctionDeclaration' && (declaration.id as AstNode)?.name==='quickSort') hasExport=true;
      for (const spec of (statement.specifiers as AstNode[] || [])) if ((spec.exported as AstNode)?.name==='quickSort') hasExport=true;
    }
    if (!declaration || !['FunctionDeclaration','VariableDeclaration','EmptyStatement'].includes(declaration.type)) issue('顶层只允许函数和常量声明');
    if (declaration?.type==='VariableDeclaration') {
      for (const d of declaration.declarations as AstNode[]) {
        if ((d.id as AstNode)?.type !== 'Identifier') issue('顶层声明不能使用解构或默认表达式');
        const init=d.init as AstNode | null;
        if (init && !['Literal','ArrowFunctionExpression','FunctionExpression'].includes(init.type)) issue('顶层声明不可执行调用或表达式');
      }
    }
  }
  function walk(node: AstNode) {
    if (['ImportDeclaration','ImportExpression','ExportAllDeclaration','AwaitExpression','YieldExpression','ThisExpression','NewExpression'].includes(node.type)) {
      if (!(node.type==='NewExpression' && (node.callee as AstNode)?.type==='Identifier' && ['Error','Array'].includes(String((node.callee as AstNode).name)))) issue('不支持导入、异步、全局访问或动态构造');
    }
    if (node.async || node.generator) issue('不支持异步函数或生成器');
    if (node.type==='Identifier' && forbiddenNames.has(String(node.name))) issue('不支持 DOM、网络、计时器或动态执行');
    if (node.type==='MemberExpression') {
      const property=node.property as AstNode;
      const name=property?.name ?? property?.value;
      if (['constructor','__proto__','prototype'].includes(String(name))) issue('不支持原型或构造器访问');
      if (['sort','toSorted'].includes(String(name))) issue('请使用快速排序；内置排序不能证明实现了指定算法','IMPLEMENTATION_HINT');
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) { for (const child of value) { if (child && typeof child==='object' && 'type' in child) walk(child as AstNode); } }
      else if (value && typeof value==='object' && 'type' in value) walk(value as AstNode);
    }
  }
  walk(tree);
  if (!hasExport) issue('请导出 quickSort 函数','EXPORT_MISSING');
  return {ok:!issues.some(i=>i.code!=='IMPLEMENTATION_HINT'),issues};
}
