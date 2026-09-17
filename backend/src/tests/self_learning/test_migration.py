import json
from app.self_learning.migration import LearningImporter
from tests.self_learning.test_session_repository import repository


def test_scan_repeat_import_and_unknown_versions_are_auditable(repository,tmp_path):
    turns=[{'turn_id':f'old-{i}','question':str(i),'answer_text':'回答'+str(i)} for i in range(150)]
    (tmp_path/'session.json').write_text(json.dumps({'owner_user_id':'alice','course_id':'course','turns':turns}))
    source=tmp_path/'export.json'
    source.write_text(json.dumps({'sessions':[{'owner':'alice','course_id':'course','topic_id':'a','path':'session.json'}],
        'unversioned_progress':[{'resource_id':'old','completed':True}]}))
    report=LearningImporter.scan(source)
    assert report['sessions'][0]['turn_count']==150 and report['unversioned_progress']
    assert repository.find('alice','course','a') is None
    importer=LearningImporter(repository)
    assert importer.import_records(report)['created']==1
    assert importer.import_records(report)['created']==0
    assert importer.reconcile(report)['unexplained_differences']==[]


def test_small_history_orphans_and_placeholder_notes_remain_auditable(repository,tmp_path):
    turns=[{'turn_id':f'small-{i}','question':str(i),'answer_text':'保留原文'} for i in range(3)]
    (tmp_path/'small.json').write_text(json.dumps({'turns':turns}))
    source=tmp_path/'export.json'
    source.write_text(json.dumps({'sessions':[{'owner':'alice','course_id':'course','topic_id':'a','path':'small.json'}],
        'unversioned_progress':[{'resource_id':'orphan','completed':True}],
        'orphan_resources':[{'resource_id':'orphan','reason':'missing_material'}],
        'placeholder_notes':[{'resource_id':'pending:a','note':'placeholder'}]}))
    report=LearningImporter.scan(source)
    assert report['orphan_resources'][0]['resource_id']=='orphan'
    assert report['placeholder_notes'][0]['resource_id']=='pending:a'
    importer=LearningImporter(repository)
    assert importer.import_records(report)['created']==1
    assert importer.import_records(report)['created']==0
    assert importer.reconcile(report)['unexplained_differences']==[]
