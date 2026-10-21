import { remarkBriefLayout } from './briefLayout';
import {useRef,type ReactNode} from 'react';
import {useBalancedBrief} from './useBalancedBrief';
import ReactMarkdown from 'react-markdown';
import type { ExerciseArtifact, ExerciseTask } from './types';
import type { ProjectStep, ProjectCheck } from './projectTypes';
import { algorithmExample, type StatementExample } from './problemStatement';

function ProblemText({step}: {step:{instructionsMarkdown:string;objective:string}}) {
  return <ReactMarkdown skipHtml components={{h1:({children})=><h4>{children}</h4>,h2:({children})=><h4>{children}</h4>,h3:({children})=><h4>{children}</h4>}}>
    {step.instructionsMarkdown?.trim()?step.instructionsMarkdown:step.objective}
  </ReactMarkdown>;
}

function Statement({children,example}: {children:ReactNode;example?:StatementExample}) {
  return <div className="pbl-statement">
    <section className="pbl-problem-reading" aria-label="任务要求">{children}</section>
    {example&&<section className="pbl-statement-example" aria-label="输入输出示例">
      <h3>示例</h3>
      <div className="pbl-example-values">
        <div><strong>输入：</strong><code>{example.input}</code></div>
        <div><strong>输出：</strong><code>{example.output}</code></div>
      </div>
    </section>}
  </div>;
}

export function AlgorithmBrief({artifact,step}: {artifact:ExerciseArtifact;step:ExerciseTask}) {
  return <Statement example={algorithmExample(step,artifact.testCases)}>
    <ProblemText step={step}/>
  </Statement>;
}

export function ProjectBrief({step,checks,deliverable}: {step:ProjectStep;checks:ProjectCheck[];deliverable?:string}) {
  const currentChecks=checks.filter(check=>step.checkIds.includes(check.id));
  const brief=useRef<HTMLDivElement>(null);
  useBalancedBrief(brief,JSON.stringify([step.instructionsMarkdown,step.objective,deliverable,currentChecks.map(check=>check.label)]));
  return <div ref={brief} className="pbl-statement pbl-project-statement pbl-problem-reading">
    <ReactMarkdown skipHtml remarkPlugins={[[remarkBriefLayout,{deliverable:deliverable||step.objective,checks:currentChecks.map(check=>check.label)}]]}>
      {step.instructionsMarkdown?.trim()||step.objective}
    </ReactMarkdown>
  </div>;
}
