"""Versioned Sandpack capabilities shared by generation and the browser host."""
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .schemas import StrictModel

MULTI_TEMPLATE = 'sandpack-project-v1'
CATALOG = json.loads((Path(__file__).resolve().parents[4] / 'shared/pbl-runtimes.json').read_text())


def file_path(path):
    if (not isinstance(path,str) or not path.startswith('/') or path.startswith('//')
        or '\\' in path or '..' in path.split('/') or str(PurePosixPath(path))!=path
        or any(part.startswith('.') for part in path.split('/') if part)
        or not re.fullmatch(r'/[A-Za-z0-9_@./-]+',path)
        or path in {'/package.json','/sandbox.config.json','/pblruntime.cjs'}
        or path.startswith(('/node_modules/','/__checks__/','/__pbl__/'))
        or not re.search(r'\.(?:[cm]?jsx?|tsx?|css|html|vue|svelte|json|svg|md)$',path)):
        raise ValueError('工程路径无效或属于宿主管理文件')
    return path


class ProjectRuntime(StrictModel):
    template: Literal['react','react-ts','vanilla','vanilla-ts','vue','svelte','static','node']
    entry: str = Field(description='完整入口路径，须在 editableFiles 中。Node 为服务启动文件，浏览器模板使用对应入口；宿主生成 package.json。')
    dependencies: dict[str,str] = Field(default_factory=dict,description='额外 npm 依赖及明确版本；模板已有依赖自动提供，不需要重复列出。禁止 URL、git、file 依赖。')
    moduleType: Literal['commonjs','module'] = 'commonjs'
    _entry=field_validator('entry')(file_path)

    @field_validator('dependencies')
    @classmethod
    def package_versions(cls,value):
        if len(value)>24: raise ValueError('依赖超过运行限制')
        for name,version in value.items():
            if not re.fullmatch(r'(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*',name) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?',version):
                raise ValueError('npm 依赖需合法包名及明确版本号')
        return value


def validate_files(files, expected=None):
    if not isinstance(files,dict) or not files or len(files)>32 or any(not isinstance(v,str) for v in files.values()):
        raise ValueError('工程需要 1–32 个文本文件')
    for path in files: file_path(path)
    if sum(len(k.encode())+len(v.encode()) for k,v in files.items())>524288:
        raise ValueError('工程超过 512KiB 运行限制')
    if expected is not None and set(files)!=set(expected): raise ValueError('工程文件与计划清单不一致')
    return files


def runtime_for(plan):
    value=plan.get('runtime')
    return ProjectRuntime.model_validate(value).model_dump() if value else None


def starter_files(plan,legacy):
    runtime=runtime_for(plan)
    if runtime is None:return dict(legacy)
    base=CATALOG[runtime['template']]['files']
    files={path:base.get(path,'') for path in plan['editableFiles']}
    if runtime['entry'] not in base:
        files[runtime['entry']]=base[CATALOG[runtime['template']]['entry']]
    for path in files:
        if files[path]:continue
        if path.endswith(('.jsx','.tsx')):files[path]='export default function App(){return <main>从本步开始实现。</main>}\n'
        elif path.endswith('.vue'):files[path]='<template><main>从本步开始实现。</main></template>\n'
        elif path.endswith('.svelte'):files[path]='<main>从本步开始实现。</main>\n'
        elif path.endswith('.json'):files[path]='{}\n'
    return files


def capabilities():
    return {name:{'entry':spec['entry'],'files':list(spec['files']),
        'dependencies':spec['dependencies'],'starterFiles':spec['files'],
        'limitations':(['仅无请求体 HTTP；请求体传输有上游缺陷，JSON POST/PUT/PATCH、表单和上传不能生成'] if name=='node' else ['纯 HTML/CSS；需要 JavaScript 交互时选择 vanilla'] if name=='static' else []),
        'checks':['http','ui'] if name=='node' else ['ui'] if name in {'static','vue','svelte'} else ['sandpack-jest','ui']}
        for name,spec in CATALOG.items()}
