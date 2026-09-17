"""Explicit scoped migration CLI; the default action is a read-only scan.

python -m app.database.migrate_self_learning_cli --database-url ... --owner ...
  --course ... --output report.json
python -m app.database.migrate_self_learning_cli import --database-url ...
  --report report.json --output import.json

No schema creation, business-table migration or feature activation is implicit.
"""
import argparse
import json
from pathlib import Path
from sqlalchemy import create_engine

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',choices=['scan','import','reconcile','activate'],default='scan')
    parser.add_argument('--database-url',required=True)
    parser.add_argument('--storage-root',type=Path,help='Explicit JSON snapshot root (courses/, members.json, self_learning/); never changes configured business stores')
    parser.add_argument('--owner')
    parser.add_argument('--course')
    parser.add_argument('--source',type=Path,help='Explicit legacy source snapshot JSON; otherwise collect configured stores')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',type=int,default=5)
    args=parser.parse_args(argv)
    if args.action=='scan' and not args.source and not (args.owner and args.course):
        parser.error('scan requires --source or both --owner and --course')
    if args.action!='scan' and not args.report:
        parser.error('this action requires a reviewed --report')
    from app.self_learning.service import LearningService
    from app.self_learning.postgres_repository import SessionRepository
    from app.self_learning.progress_repository import ProgressRepository
    from app.self_learning.migration import LearningMigration
    engine=create_engine(args.database_url,pool_pre_ping=True)
    try:
        options={}
        if args.storage_root:
            import os
            for domain in ('APP_STATE','MATERIAL','KNOWLEDGE','COURSE','COURSE_MEMBERSHIP'):
                os.environ[domain+'_PERSISTENCE_MODE']='json'
            from core.course_storage import CourseStorageManager
            from app.self_learning.store import LearningStore
            from app.services.course_membership_store import CourseMembershipStore
            options={'manager':CourseStorageManager(root_path=str(args.storage_root/'courses')),
                'store':LearningStore(args.storage_root),'memberships':CourseMembershipStore(args.storage_root/'members.json')}
        learning=LearningService(session_repository=SessionRepository(engine),progress_repository=ProgressRepository(engine),**options)
        migration=LearningMigration(learning)
        if args.action=='scan':
            source=json.loads(args.source.read_text()) if args.source else migration.collect(args.owner,args.course)
            result=migration.scan(source)
        else:
            report=json.loads(args.report.read_text())
            if args.action=='import': result=migration.import_records(report)
            elif args.action=='reconcile': result=migration.reconcile(report)
            else: result=migration.activate(report,args.phase)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({'action':args.action,'output':str(args.output)},ensure_ascii=False))
        if args.action=='reconcile' and result['unexplained_differences']:
            return 1
        return 0
    except Exception as exc:
        # A failed import still produces an operator audit artifact; never emit
        # connection URLs or raw driver SQL/parameters into it.
        from fastapi import HTTPException
        detail = str(exc) if isinstance(exc, ValueError) else str(exc.detail) if isinstance(exc, HTTPException) else '操作失败，请核对数据库和导入冲突'
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({'action':args.action,'status':'failed','error_type':type(exc).__name__,'message':detail},ensure_ascii=False,indent=2))
        print(json.dumps({'action':args.action,'status':'failed','output':str(args.output)},ensure_ascii=False))
        return 1
    finally:
        engine.dispose()

if __name__=='__main__':
    raise SystemExit(main())
