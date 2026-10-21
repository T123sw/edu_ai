export type OpenTimes = Readonly<Record<string, number>>;
type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;
export const recentKey = (kind:string,id:string) => JSON.stringify([kind,id]);
export const materialRecentKey = (type:string,id:string,courseId?:string) => recentKey('resource',JSON.stringify([courseId||'personal',type,id]));
export const recentStorageKey = (owner:string) => `edu-ai:recent-opens:v1:${encodeURIComponent(owner)}`;

export function recentFirst<T>(items:readonly T[],key:(item:T)=>string,opened:OpenTimes,fallback?:(a:T,b:T)=>number):T[] {
  return [...items].sort((a,b)=>(opened[key(b)]||0)-(opened[key(a)]||0)||(fallback?.(a,b)||0));
}

export function createRecentOpenStore(storage?:StorageLike,storageKey='',now=Date.now) {
  const read=():OpenTimes|undefined=>{
    try {
      const value=JSON.parse(storage?.getItem(storageKey)||'{}');
      if(!value||typeof value!=='object'||Array.isArray(value))return {};
      return Object.fromEntries(Object.entries(value).filter((entry):entry is [string,number]=>typeof entry[1]==='number'&&Number.isFinite(entry[1])&&entry[1]>0));
    }catch{return undefined;}
  };
  let snapshot:OpenTimes=read()||{};
  const listeners=new Set<()=>void>();
  const emit=()=>listeners.forEach(listener=>listener());
  return {
    getSnapshot:()=>snapshot,
    subscribe:(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};},
    sync:()=>{const next=read();if(next&&JSON.stringify(next)!==JSON.stringify(snapshot)){snapshot=next;emit();}},
    mark:(key:string)=>{
      if(!key)return;
      const merged={...snapshot};
      for(const [id,time] of Object.entries(read()||{}))merged[id]=Math.max(merged[id]||0,time);
      const latest=Object.values(merged).reduce((max,value)=>Math.max(max,value),0);
      snapshot={...merged,[key]:Math.max(now(),latest+1)};
      try{storage?.setItem(storageKey,JSON.stringify(snapshot));}catch{/* Keep this session usable when browser storage is unavailable. */}
      emit();
    },
  };
}
export type RecentOpenStore = ReturnType<typeof createRecentOpenStore>;
