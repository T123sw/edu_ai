// Only this host is bundled in Node. Learner files execute in Sandpack/Nodebox.
import {useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {SandpackProvider,SandpackLayout,SandpackPreview,SandpackConsole,useSandpack} from '@codesandbox/sandpack-react';
import {projectSetup,type ProjectRuntime} from '../projectRuntime';
import {BUNDLER_URL} from '../bridge';
function Status(){const {sandpack,listen}=useSandpack();useEffect(()=>listen(message=>{if(['stdout','action'].includes(message.type))console.log('PBL_RUNTIME:'+JSON.stringify(message))}),[listen]);Object.defineProperty(window,'pblPreviewState',{configurable:true,get:()=>({status:sandpack.status,error:sandpack.error?.message,clients:Object.values(sandpack.clients).map(c=>c.status)})});return null}
function Preview({files,runtime}:{files:Record<string,string>;runtime:ProjectRuntime}){
 const setup=projectSetup(files,runtime);
 return <SandpackProvider template={setup.template} files={setup.files} customSetup={setup.customSetup} options={{bundlerTimeOut:60000,...(runtime.template==='node'||runtime.template==='static'?{}:{bundlerURL:BUNDLER_URL}),autorun:true,autoReload:false}}><SandpackLayout style={{height:'100vh',width:'100vw',border:0}}><Status/><SandpackPreview showOpenInCodeSandbox={false} showRefreshButton={false} style={{height:'100vh',width:'100vw'}}/></SandpackLayout><SandpackConsole/></SandpackProvider>;
}
declare global{interface Window{startPblPreview(input:{files:Record<string,string>;runtime:ProjectRuntime}):void;pblPreviewState?:{status:string;error?:string;clients:string[]}}}
const root=createRoot(document.getElementById('root')!);
window.startPblPreview=input=>root.render(<Preview {...input}/>);
