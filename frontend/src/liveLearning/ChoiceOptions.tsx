import { QuizMarkdown } from './QuizMarkdown';
export function ChoiceOptions({name,options,selected,multiple,onChange,disabled=false}: {name:string;options:{id:string;text:string}[];selected:string[];multiple:boolean;onChange:(values:string[])=>void;disabled?:boolean}) {
  return <>{options.map((option,index)=><label className="quiz-option" key={option.id}><input disabled={disabled} name={name} type={multiple?'checkbox':'radio'} checked={selected.includes(option.id)} onChange={e=>onChange(multiple?(e.target.checked?[...selected,option.id]:selected.filter(id=>id!==option.id)):[option.id])}/><span className="quiz-option-letter" aria-hidden="true">{String.fromCharCode(65+index)}.</span><QuizMarkdown content={option.text}/></label>)}</>;
}
