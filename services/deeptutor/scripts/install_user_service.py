"""Configure matching private credentials and install the supported user unit."""
import os,secrets,subprocess
from pathlib import Path
from dotenv import dotenv_values,set_key
ROOT=Path(__file__).resolve().parents[3]
def main():
    env=ROOT/'.env';values=dotenv_values(env)
    token=values.get('EDU_DEEPTUTOR_TOKEN') or secrets.token_urlsafe(48)
    if len(token)<32:raise ValueError('Existing service token is too short; update it before deployment')
    set_key(str(env),'EDU_DEEPTUTOR_TOKEN',token)
    set_key(str(env),'EDU_DEEPTUTOR_URL','http://127.0.0.1:8026')
    runtime=ROOT/'services/deeptutor/.runtime';runtime.mkdir(exist_ok=True,mode=0o700)
    path=runtime/'service.env'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write('EDU_DEEPTUTOR_TOKEN='+token+'\nDEEPTUTOR_HOME='+str(runtime)+'\n')
    unit=Path.home()/'.config/systemd/user/edu-ai-deeptutor.service';unit.parent.mkdir(parents=True,exist_ok=True)
    unit.write_text((ROOT/'deploy/systemd/edu-ai-deeptutor.service').read_text().replace('/home/zxqs_ep/Edu_AI',str(ROOT)))
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','--now','edu-ai-deeptutor.service'],check=True)
    print('DeepTutor user service enabled. Restart the main backend to load its matching credential.')
if __name__=='__main__':main()
