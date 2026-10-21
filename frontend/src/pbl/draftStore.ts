import type { RunRecord, WorkspacePatch } from './api';
import type { Workspace } from './types';
export interface Draft {workspace: Workspace; dirty: boolean; pendingPatch?: WorkspacePatch; pendingRuns: RunRecord[]; backup?: string}
let database: Promise<IDBDatabase> | undefined;
function open() {
  database ??= new Promise((resolve,reject) => {
    const request=indexedDB.open('edu-pbl-drafts',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('drafts');
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>{database=undefined;reject(request.error);};
  });
  return database;
}
export function draftKey(owner: string,id: string,version: number) {return JSON.stringify([owner,id,version]);}
export async function getDraft(key: string): Promise<Draft | undefined> {
  const db=await open();
  return new Promise((resolve,reject)=>{const r=db.transaction('drafts').objectStore('drafts').get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
}
export async function putDraft(key: string,draft: Draft): Promise<void> {
  const db=await open();
  return new Promise((resolve,reject)=>{const t=db.transaction('drafts','readwrite');t.objectStore('drafts').put(draft,key);t.oncomplete=()=>resolve();t.onerror=()=>reject(t.error);t.onabort=()=>reject(t.error);});
}
