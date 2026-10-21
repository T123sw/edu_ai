import pytest
from app.integrations.hyperframes.contracts import validate_content, resolve_position

def content():
    return {'format':'hyperframes/v1','title':'Lesson','project':{'id':'hf_a','digest':'a'*64,'entry':'index.html'},'timeline':{'duration':3,'segments':[{'id':'a','title':'A','start':1,'end':3,'narration':'Hello','visual_description':'Text','audio_path':'assets/a.mp3','objective_ids':[],'source_ids':[],'events':[{'start':1,'end':2,'target':'a','description':'Show'}]}]},'exports':{}}

def test_intervals_gap_final_endpoint():
    c=content()
    assert resolve_position(c,0)['segment'] is None
    assert resolve_position(c,1)['events']
    assert not resolve_position(c,2)['events']
    assert resolve_position(c,3)['segment']['id']=='a'

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-1,True])
def test_invalid_times(bad):
    c=content(); c['timeline']['segments'][0]['start']=bad
    with pytest.raises(ValueError): validate_content(c)

def test_event_bounds_duplicate():
    c=content(); c['timeline']['segments'][0]['events'][0]['end']=4
    with pytest.raises(ValueError): validate_content(c)
    c=content(); c['timeline']['segments']*=2
    with pytest.raises(ValueError): validate_content(c)
