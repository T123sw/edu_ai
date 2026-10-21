import {createContext,useContext,useSyncExternalStore} from 'react';
import {createRecentOpenStore,recentFirst} from './store';
export const RecentOpenContext=createContext(createRecentOpenStore());
export function useRecentOpens() {
  const store=useContext(RecentOpenContext);
  const opened=useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot);
  return {mark:store.mark,sort:<T,>(items:readonly T[],key:(item:T)=>string,fallback?:(a:T,b:T)=>number)=>recentFirst(items,key,opened,fallback)};
}
