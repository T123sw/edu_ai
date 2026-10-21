import pytest
from app.integrations.hyperframes.projects import ProjectStore

@pytest.mark.parametrize('name',['../x','/x','a/../../x','a\\x','a/%2e%2e/x','a//x','./x'])
def test_traversal(tmp_path,name):
    with pytest.raises(ValueError): ProjectStore(tmp_path).publish('hf_a',{'index.html':'ok',name:'bad'})

def test_immutable_digest_and_tamper(tmp_path):
    store=ProjectStore(tmp_path)
    a=store.publish('hf_a',{'index.html':'first','sub/a.css':'a'})
    b=store.publish('hf_a',{'index.html':'second'})
    assert a['digest']!=b['digest']
    assert store.file(a,'index.html').read_text()=='first'
    assert store.publish('hf_a',{'index.html':'first','sub/a.css':'a'})==a
    store.file(a,'index.html').write_text('tampered')
    with pytest.raises(ValueError): store.file(a,'index.html')
    with pytest.raises(FileNotFoundError): store.file(b,'secret')

def test_symlinks_and_manifest(tmp_path):
    store=ProjectStore(tmp_path/'store')
    target=tmp_path/'target'; target.write_text('data')
    link=tmp_path/'link'; link.symlink_to(target)
    with pytest.raises(ValueError): store.publish('hf_a',{'index.html':link})
    project=store.publish('hf_a',{'index.html':'ok'})
    (store._directory(project)/'manifest.json').write_text('{}')
    with pytest.raises(ValueError): store.file(project,'index.html')
