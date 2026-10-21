import {useEffect,useMemo,type ReactNode} from 'react';
import {RecentOpenContext} from './context';
import {createRecentOpenStore,recentStorageKey} from './store';
export function RecentOpenProvider({owner,children}:{owner:string;children:ReactNode}) {
  const key=recentStorageKey(owner);
  const store=useMemo(()=>{
    let storage:Storage|undefined;
    try{storage=window.localStorage;}catch{/* Private browsing can deny access. */}
    return createRecentOpenStore(storage,key);
  },[key]);
  useEffect(()=>{
    const sync=(event:StorageEvent)=>{if(event.key===key||event.key===null)store.sync();};
    window.addEventListener('storage',sync);
    return()=>window.removeEventListener('storage',sync);
  },[key,store]);
  return <RecentOpenContext.Provider value={store}>{children}</RecentOpenContext.Provider>;
}
