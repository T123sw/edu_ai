"""Exercise the bridge NDJSON helper over real loopback HTTP with a short read timeout."""
import asyncio,json,socket,time
from pathlib import Path
import httpx,uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from edu_deeptutor.api import event_lines
async def run(interval):
 app=FastAPI()
 @app.get('/')
 async def stream():
  async def events():
   await asyncio.sleep(.2)
   yield {'seq':42,'type':'done'}
  return StreamingResponse(event_lines(events(),heartbeat_seconds=interval),media_type='application/x-ndjson')
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(app,log_level='error',lifespan='off'))
 task=asyncio.create_task(server.serve(sockets=[sock]))
 while not server.started:await asyncio.sleep(.01)
 result={'heartbeat_seconds':interval,'read_timeout_seconds':.05,'idle_generation_seconds':.2,'blank_lines':0,'events':[]}
 try:
  async with httpx.AsyncClient(timeout=.05,trust_env=False) as client:
   async with client.stream('GET',f'http://127.0.0.1:{port}/') as response:
    async for line in response.aiter_lines():
     if line.strip():result['events'].append(json.loads(line))
     else:result['blank_lines']+=1
  result['completed']=True
 except httpx.ReadTimeout:result['completed']=False
 finally:
  server.should_exit=True;await task;sock.close()
 return result
async def main():
 rows=[await run(1),await run(.01)]
 assert not rows[0]['completed'] and rows[1]['completed']
 assert rows[1]['events']==[{'seq':42,'type':'done'}] and rows[1]['blank_lines']>=2
 Path(__file__).with_name('heartbeat-http.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
asyncio.run(main())
