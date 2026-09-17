"""Opt-in real provider tasks; ordinary test runs do not spend model tokens."""
import os
from pathlib import Path
import subprocess
import sys
import pytest

@pytest.mark.live_integration
@pytest.mark.skipif(os.getenv('LEARNING_LIVE_ACCEPTANCE')!='1',reason='requires explicit real model acceptance flag')
def test_real_model_boundaries():
    root=Path(__file__).resolve().parents[4]
    result=subprocess.run([sys.executable,str(root/'backend/src/scripts/verify_learning_live.py')],cwd=root,
        env={**os.environ,'PYTHONPATH':str(root/'backend/src')},capture_output=True,text=True,timeout=500)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
