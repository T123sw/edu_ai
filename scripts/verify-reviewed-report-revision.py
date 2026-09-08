"""Revise an isolated smoke report through the production writer/reviewer.

Feedback is external review, never a hand-edited replacement body.
"""
import argparse,json,os,sys
from pathlib import Path
from types import SimpleNamespace
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'backend/src'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from core.config import Config
    import dotenv
    dotenv.load_dotenv=lambda *a,**k:False
    for key in ('USER','JOB','TASK','MATERIAL','COURSE','COURSE_MEMBERSHIP','KNOWLEDGE','APP_STATE','CONVERSATION','LEARNING'):
        os.environ[key+'_PERSISTENCE_MODE']='json'
    os.environ['DATABASE_URL']=''
    args.output.mkdir(parents=True,exist_ok=False)
    Config.STORAGE_ROOT=args.output/'storage'
    Config.RUNTIME_CONFIG_ROOT=args.output/'runtime'
    from app.chat.tasks.task_store import TaskStore
    from app.chat.harness.reviewed_report import generate_reviewed_report,verified_review
    smoke=json.loads((args.input/'smoke.json').read_text())
    job_id=smoke[3]['result']['task_id']
    task=TaskStore(db_path=str(args.input/'tasks.sqlite')).get_durable(job_id)
    payload=SimpleNamespace(**task.command['config'])
    body=(args.input/'report.md').read_text()
    feedback=[
      '不要把示例中参数n减小泛化成所有递归参数都必须减小；一般条件是存在良基的规模度量。本报告只讨论非负整数n且每次n-1。',
      '纠正“递归深度随每次调用而减少”：调用栈深度在下降递归过程中增加，减少的是问题规模和到达基线所需的剩余步数。',
      '终止充分条件必须包含递归调用保持合法输入域且不跳过基线；仅n严格递减和基线为0并不足够，例如奇数n每次减2会跳过0。',
      '在数学上的无限递归与Python因递归深度限制抛出RecursionError之间作区分，不声称Python实际永远运行。',
      '给出短小完整的非负整数阶乘或倒计时代码和具体检查题。不要给出未经来源验证的默认递归深度数值。'
    ]
    revised,state=generate_reviewed_report(payload,initial_body=body,initial_feedback=feedback)
    assert verified_review({'content':revised,'generation_state':state})
    (args.output/'report.md').write_text(revised)
    (args.output/'review.json').write_text(json.dumps(state['report_review'],ensure_ascii=False,indent=2))
    print('Reviewed revision generated: '+str(args.output))
if __name__=='__main__':main()
