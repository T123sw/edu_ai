"""Independent numerical and partition invariants; never accepts client completion flags."""
from collections import Counter
import math

def verify(manifest,state):
    for step,attempt in state['attempts'].items():
        m=attempt['model']
        if manifest['kind']=='quicksort':
            if Counter(m['array'])!=Counter(m['initial']): raise ValueError('排序丢失或增加了元素')
            if any(not isinstance(m[k],int) or m[k]<0 for k in ('comparisons','swaps')): raise ValueError('算法计数无效')
            if m['phase']=='done' and m['array']!=sorted(m['initial']): raise ValueError('排序结果不正确')
            if m['phase'] in ('range','done'):
                p=m['selected']; pivot=m['array'][p]
                if any(v>pivot for v in m['array'][m['lo']:p]) or any(v<=pivot for v in m['array'][p+1:m['hi']+1]): raise ValueError('分区结果不正确')
            expected=(m['phase']=='scan') if step=='pivot' else m['phase'] in ('range','done') if step=='partition' else m['phase']=='done'
        else:
            t=m['time'];v=m['velocity'];mu=m['mu'];stop=v/(mu*9.8)
            if not 0<=t<=stop+1e-9: raise ValueError('运动时间不正确')
            expected_distance=v*t-.5*mu*9.8*t*t
            if not math.isclose(m['distance'],expected_distance,abs_tol=1e-8): raise ValueError('滑行距离不正确')
            if m['phase']=='done' and not math.isclose(m['distance'],v*v/(2*mu*9.8),abs_tol=1e-8): raise ValueError('停车距离不正确')
            expected=m['phase']=='done' and (step=='baseline' or m['changed'])
        if step!='explore' and attempt['complete'] and not expected: raise ValueError('步骤完成条件不满足')
