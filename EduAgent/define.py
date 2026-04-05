from pathlib import Path
import tomllib
ROOT_DIR = Path(__file__).resolve().parent

PPT_DIR = ROOT_DIR / 'files/ppt'
PDF_DIR = ROOT_DIR / 'files/pdf'
DOC_DIR = ROOT_DIR / 'files/line'
CONFIG_PATH = ROOT_DIR / 'config.toml'



def get_config_dict()->dict:

    global CONFIG_PATH
    with CONFIG_PATH.open('rb') as f:
        config_dict = tomllib.load(f)

    return config_dict


__all__ = [
    'PPT_DIR',
    'PDF_DIR',
    'DOC_DIR',
    'CONFIG_PATH',
    'ROOT_DIR',
    'get_config_dict'
]