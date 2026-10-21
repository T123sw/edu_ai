// Trusted host used by the anonymous server-side browser. Student files are
// passed to Sandpack's separate iframe, never evaluated by the Node process.
import { createRoot } from 'react-dom/client';
import { NativeTestRunner } from '../NativeProjectTests';
import { nativeTestResults } from '../nativeTests';
import type {ProjectRuntime} from '../projectRuntime';
import type { JestCheck } from '../projectTypes';

declare global {
  interface Window {
    startPblTests(input:{files:Record<string,string>;checks:JestCheck[];runtime?:ProjectRuntime|null}):void;
    pblTestReport?: {passed:boolean;results:ReturnType<typeof nativeTestResults>};
  }
}
const root=createRoot(document.getElementById('root')!);
window.startPblTests=({files,checks,runtime})=>{
  root.render(<NativeTestRunner runtime={runtime} files={files} checks={checks} onComplete={specs=>{
    const results=nativeTestResults(checks,specs);
    window.pblTestReport={passed:results.length>0&&results.every(result=>result.status==='passed'),results};
  }}/>);
};
