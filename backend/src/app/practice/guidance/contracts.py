from __future__ import annotations
import hashlib
import json
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=80)
    type: Literal['action', 'enter', 'retry']
    action: str | None = Field(default=None, max_length=40)
    value: Any = None
    step: str | None = Field(default=None, max_length=80)
    attempt: str | None = Field(default=None, max_length=80)

class EventBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    batch_id: str = Field(min_length=1, max_length=80)
    revision: str = Field(min_length=1, max_length=64)
    expected_seq: int = Field(ge=0)
    commands: list[Command] = Field(min_length=1, max_length=100)

STEPS = {
 'quicksort': [
  dict(id='pivot', title='选择基准', instruction='点击一个元素作为基准，再确认。本实验按小于等于基准与大于基准分区。', question='基准确定后，其他元素应该如何分类？', actions=['select','confirm'], parameters=[]),
  dict(id='partition', title='完成一次分区', instruction='判断高亮元素与基准的关系，再执行基准归位。错误判断可以重新尝试。', question='分区完成是否意味着两侧内部也已经有序？', actions=['left','right','advance'], parameters=[]),
  dict(id='recurse', title='处理子区间', instruction='选择待处理子区间，单步或播放，观察较小区间如何继续分区。', question='为什么只剩一个元素的区间无需继续拆分？', actions=['range','advance','run'], parameters=['speed']),
 ],
 'friction': [
  dict(id='baseline', title='观察基线滑行', instruction='运行小车，观察恒定滑动摩擦下的速度与停车距离。', question='速度减小时，单位时间内前进的距离如何变化？', actions=['advance','run'], parameters=['speed']),
  dict(id='change_mu', title='改变摩擦系数', instruction='只改变摩擦系数，保持初速度不变，再运行并比较停车距离。', question='停车距离的变化与摩擦系数有什么关系？', actions=['advance','run'], parameters=['mu','speed']),
  dict(id='change_velocity', title='改变初速度', instruction='保持摩擦系数不变，只改变初速度，再运行并比较停车距离。', question='初速度翻倍，停车距离是否也只翻倍？', actions=['advance','run'], parameters=['velocity','speed']),
 ]}

def make_manifest(kind):
    if kind not in STEPS:
        return None
    from .bundle import engine_digest, bundle
    bundle('replay')
    value = {'engine':engine_digest(),'version':2,'kind':kind,'initial':[5,3,8,4,2,7,1,6],'steps':STEPS[kind]}
    value['revision'] = hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return value
