"""python -m app.database.migrate_self_learning_cli scan --source export.json --output scan.json"""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine
from app.self_learning.migration import LearningImporter
from app.self_learning.postgres_repository import SessionRepository


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['scan','import','reconcile'],nargs='?',default='scan')
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.operation=='scan': result=LearningImporter.scan(args.source)
    else:
        url=os.getenv('DATABASE_URL','')
        if not url.startswith(('postgresql:', 'postgresql+')): raise ValueError('DATABASE_URL must identify the migration database')
        importer=LearningImporter(SessionRepository(create_engine(url)))
        report=json.loads(Path(args.source).read_text())
        result=importer.import_records(report) if args.operation=='import' else importer.reconcile(report)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'operation':args.operation,'output':str(Path(args.output).resolve())}))


if __name__=='__main__': main()
