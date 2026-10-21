import type { RefObject } from 'react';
import { Icon } from './ui';
export function AgentComposer({value,onChange,onSend,disabled,placeholder,onFocus,inputRef}: {value:string;onChange:(s:string)=>void;onSend:()=>void;disabled?:boolean;placeholder:string;onFocus?:()=>void;inputRef?:RefObject<HTMLTextAreaElement>}) {
  return <form className="sl-chat-composer" onSubmit={e=>{e.preventDefault();onSend();}}><textarea ref={inputRef} aria-label="向学习 Agent 提问" placeholder={placeholder} value={value} maxLength={1000} onChange={e=>onChange(e.target.value)} onFocus={onFocus} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(!disabled&&value.trim())onSend();}}}/><button className="sl-send" aria-label="发送问题" disabled={disabled||!value.trim()}><Icon name="arrow" size={18}/></button></form>;
}
