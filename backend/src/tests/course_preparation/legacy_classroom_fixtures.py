"""Test-only builders for persisted pre-HyperFrames classroom records.

Never imported by production generation. Keep historical validation coverage
without restoring the removed OpenMAIC adapter.
"""
from datetime import datetime,timezone
import html
import json
import re
from typing import Annotated
from pydantic import Field
from app.course_preparation.schemas import Contract


class TeachingSlide(Contract):
    title: str=Field(min_length=1,max_length=40)
    points: tuple[Annotated[str,Field(min_length=1,max_length=60)],...]=Field(min_length=1,max_length=3)
    narration: str=Field(min_length=80,max_length=1000)


class TeachingScript(Contract):
    slides: tuple[TeachingSlide,...]=Field(min_length=2,max_length=6)


def native_classroom(script,title,resource_id):
    now=int(datetime.now(timezone.utc).timestamp()*1000)
    stage={'id':resource_id,'name':title,'createdAt':now,'updatedAt':now}
    scenes=[]
    theme={'backgroundColor':'#ffffff','themeColors':['#2563eb'],'fontColor':'#172033','fontName':'sans-serif'}
    for i,slide in enumerate(script.slides):
        def text(element_id,content,top,height,size):
            return {'id':element_id,'type':'text','left':60,'top':top,'width':880,'height':height,'rotate':0,
                'content':f'<div style="font-size:{size}px;line-height:1.4">{content}</div>',
                'defaultFontName':'sans-serif','defaultColor':'#172033','lineHeight':1.4}
        scene_id=resource_id+':scene'+str(i+1)
        elements=[text(scene_id+':title',html.escape(slide.title),35,100,36),
                  text(scene_id+':body',''.join('<p>'+html.escape(p)+'</p>' for p in slide.points),155,350,28)]
        scenes.append({'id':scene_id,'stageId':resource_id,'type':'slide','title':slide.title,'order':i,
            'content':{'type':'slide','canvas':{'id':scene_id+':canvas','viewportSize':1000,'viewportRatio':0.5625,
                'theme':theme,'background':{'type':'solid','color':'#ffffff'},'elements':elements}},
            'actions':[{'id':scene_id+':speech','type':'speech','text':slide.narration}],
            'createdAt':now,'updatedAt':now})
    return {'stage':stage,'scenes':scenes}
