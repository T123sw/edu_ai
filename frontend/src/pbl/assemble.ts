import { runtimeFiles } from './runtime/template';
import type { ExerciseArtifact, Workspace } from './types';
export function assembleSandpackFiles(artifact: Pick<ExerciseArtifact, 'starterCode' | 'testCases' | 'artifactVersion'>, workspace?: Pick<Workspace, 'files' | 'artifactVersion'>) {
  return {
    ...Object.fromEntries(Object.entries(runtimeFiles).map(([path,code]) => [path,{code,hidden:true,readOnly:true}])),
    '/src/cases.json': {code:JSON.stringify(artifact.testCases),hidden:true,readOnly:true},
    '/src/algorithm.js': {code:workspace?.artifactVersion === artifact.artifactVersion ? workspace.files['/src/algorithm.js'] ?? artifact.starterCode : artifact.starterCode,active:true},
  };
}
