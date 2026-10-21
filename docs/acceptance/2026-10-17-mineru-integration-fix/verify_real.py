import hashlib,io,json,os,time
from pathlib import Path
from core.config import Config
os.environ['PGOPTIONS']='-c default_transaction_read_only=on -c statement_timeout=10000'
from app.integrations.pdf import get_pdf_parser
from app.integrations.pdf.configuration import resolve_pdf_config
from app.services.runtime_config_resolver import runtime_config_resolver
from app.course_preparation.adapters.documents import DocumentParser
from app.exam_generation.sources import GenerationSources
from app.exam_generation.snapshots import SnapshotCodec
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
ROOT=Path('/home/zxqs_ep/Edu_AI'); OUT=ROOT/'docs/acceptance/2026-10-17-mineru-integration-fix';OUT.mkdir(exist_ok=True,parents=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',30)
scans=[]
for i in range(2):
 im=Image.new('RGB',(1240,1754),'white');d=ImageDraw.Draw(im)
 lines=['Sorting mock examination',f'Page {i+1}', '1. Compare the three bars in the chart below.' if i==0 else '2. Read the table and identify the largest count.', 'Choose the correct answer and explain your reasoning.']
 for y,s in enumerate(lines):d.text((80,80+y*65),s,font=font,fill='black')
 if i==0:
  d.line((150,1000,1050,1000),fill='black',width=4);d.line((150,400,150,1000),fill='black',width=4)
  for x,h,label in [(260,250,'A: 25'),(520,450,'B: 45'),(780,350,'C: 35')]:
   d.rectangle((x,1000-h,x+120,1000),fill=(60,100,180));d.text((x,1030),label,font=font,fill='black')
 else:
  for y in range(4):d.line((180,500+y*120,1040,500+y*120),fill='black',width=3)
  for x in (180,610,1040):d.line((x,500,x,860),fill='black',width=3)
  for j,row in enumerate([('Algorithm','Count'),('Quick sort','25'),('Merge sort','45')]):
   for k,t in enumerate(row):d.text((210+k*430,530+j*120),t,font=font,fill='black')
 scans.append(im)
scans[0].save(OUT/'scanned-paper.pdf',save_all=True,append_images=scans[1:],resolution=150)
source=ROOT/'docs/acceptance/2026-10-17-deeptutor-migration-m3/sample-paper.pdf'
writer=PdfWriter();reader=PdfReader(source)
writer.add_page(reader.pages[0]);writer.add_blank_page(595,842);writer.add_page(reader.pages[1]);writer.write(OUT/'blank-middle-page.pdf')
codec=SnapshotCodec(); owner='mineru-integration-validation'; encrypted=codec.capture(owner); config=codec.read(owner,encrypted)['pdf_parser']
summary={'production_writes':False,'config':{k:config[k] for k in ('provider_id','base_url','timeout_seconds')},'cases':[]}
for filename in (source,OUT/'scanned-paper.pdf',OUT/'blank-middle-page.pdf'):
 data=filename.read_bytes();receipts=[];start=time.monotonic()
 try:
  parsed=DocumentParser().parse(data,filename=filename.name,canceled=lambda:False,on_remote_task=receipts.append,deadline=time.monotonic()+180)
  case={'file':filename.name,'parser':parsed.parser,'revision':parsed.parser_revision,'defects':parsed.defects,'characters':len(parsed.content),'assets':len(parsed.assets),'layout':len(parsed.layout),'remote_task':parsed.remote_task,'receipts':receipts,'seconds':round(time.monotonic()-start,2)}
  (OUT/(filename.stem+'.md')).write_text(parsed.content)
  # Persist evidence from synthetic inputs only.
  from dataclasses import asdict
  (OUT/(filename.stem+'-parsed.json')).write_text(json.dumps(asdict(parsed),ensure_ascii=False,indent=2))
 except Exception as e:case={'file':filename.name,'error':str(e),'type':type(e).__name__}
 summary['cases'].append(case);print(json.dumps(case,ensure_ascii=False),flush=True)
# Real default exam parser selection, no injected parser or native PDF fallback.
data=source.read_bytes()
class Reader:
 def read_bytes(self,who,doc):
  assert who==owner
  return {'filename':'sample-paper.pdf'},data
sources=GenerationSources(reader=Reader()); refs=sources.freeze(owner,[{'document_id':'synthetic','role':'template'}])
try:
 parsed=sources.parse(owner,refs,config,canceled=lambda:False,on_remote_task=lambda t:None)
 summary['exam_sources']={'ok':True,'provider':parsed[0]['parser'],'layout':len(parsed[0]['content_list']),'characters':len(parsed[0]['content'])}
except Exception as e:summary['exam_sources']={'ok':False,'error':str(e),'type':type(e).__name__}
(OUT/'real-parsing.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print('exam',summary['exam_sources'],flush=True)
