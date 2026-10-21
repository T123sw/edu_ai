"""Scoped, expiring capabilities for immutable native classroom projects."""
import mimetypes
import time
import os
from urllib.parse import quote, urlsplit
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from core.auth import auth_manager
from app.auth import get_current_user
from app.api.self_learning import service
from app.self_learning.service import LearningService
from app.self_learning.contracts import ResourceRef
from app.self_learning.resource_reader import exact_material
from app.self_learning.hyperframes_context import native_content
from app.integrations.hyperframes.contracts import validate_content, safe_path
from app.integrations.hyperframes.projects import ProjectStore

router = APIRouter(tags=['hyperframes'])
AUDIENCE = 'hyperframes-project-files-v1'
TTL = 3600


def project_store():
    return ProjectStore()


def ticket_learning():
    return LearningService()


def issue_ticket(owner, ref, project, *, now=None):
    now = int(time.time() if now is None else now)
    return jwt.encode({'aud':AUDIENCE, 'sub':owner, 'ref':ref.model_dump(),
        'project':project, 'iat':now, 'exp':now+TTL}, auth_manager.secret_key,
        algorithm=auth_manager.algorithm), now+TTL


def decode_ticket(ticket):
    try:
        return jwt.decode(ticket, auth_manager.secret_key, algorithms=[auth_manager.algorithm],
            audience=AUDIENCE, options={'require':['aud','sub','ref','project','iat','exp']})
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, '课堂播放链接已失效，请刷新播放会话') from exc


@router.post('/api/self-learning/courses/{course_id}/materials/classroom/{material_id}/versions/{version}/playback')
def playback(course_id: str, material_id: str, version: int,
             user=Depends(get_current_user), svc=Depends(service), store=Depends(project_store)):
    if version < 1:
        raise HTTPException(422, '版本必须为正整数')
    ref = ResourceRef(course_id=course_id, material_type='classroom', material_id=material_id, version=version)
    material = exact_material(svc, user['username'], ref)
    content = native_content(material)
    if not content:
        raise HTTPException(409, '该记录是历史课堂归档，请重新生成 HyperFrames 课堂')
    try:
        validate_content(content)
        store.file(content['project'], content['project']['entry'])
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(409, '课堂工程文件缺失或校验失败') from exc
    ticket, expires = issue_ticket(user['username'], ref, content['project'])
    base = '/api/hyperframes/projects/' + ticket + '/'
    return {'project_url':base+quote(content['project']['entry']), 'expires_at':expires,
        'project_digest':content['project']['digest'], 'duration':content['timeline']['duration'],
        'exports':{kind:base+quote(path)+'?download=true' for kind,path in content.get('exports',{}).items()}}


def project_csp(request, ticket):
    parsed = urlsplit(str(request.url))
    origin = parsed.scheme+'://'+parsed.netloc
    # Limit requests to the capability-protected asset endpoint, not general APIs.
    # Repeating the long JWT in seven CSP directives exceeded nginx's default
    # upstream header buffer and turned every production asset request into 502.
    # Each asset still independently verifies the ticket, membership and digest.
    prefixes = {'', str(request.scope.get('root_path','')).rstrip('/')}
    configured = urlsplit(os.environ.get('VITE_API_BASE_URL','')).path.rstrip('/')
    if configured.startswith('/') and all(c.isalnum() or c in '/_-' for c in configured): prefixes.add(configured)
    sources = ' '.join(origin+p+'/api/hyperframes/projects/' for p in sorted(prefixes))
    return ("sandbox allow-scripts; default-src 'none'; script-src "+sources+" 'unsafe-inline' 'unsafe-eval'; "
        "style-src "+sources+" 'unsafe-inline'; img-src "+sources+" data: blob:; media-src "+sources+" blob:; "
        "font-src "+sources+" data:; connect-src "+sources+"; frame-src "+sources+"; base-uri 'none'; form-action 'none'")


@router.get('/api/hyperframes/projects/{ticket}/{path:path}')
def project_file(ticket: str, path: str, request: Request, download: bool = Query(False),
                 learning=Depends(ticket_learning), store=Depends(project_store)):
    claims = decode_ticket(ticket)
    try:
        ref = ResourceRef.model_validate(claims['ref'])
        if ref.material_type != 'classroom':
            raise ValueError('Not a classroom')
        safe_path(path)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(404, '工程文件不存在') from exc
    scoped = learning.for_scope(claims['sub'], ref.course_id)
    material = exact_material(scoped, claims['sub'], ref)
    content = native_content(material)
    if not content or content['project'] != claims['project']:
        raise HTTPException(409, '课堂工程版本不匹配')
    try:
        target = store.file(content['project'], path)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, '工程文件不存在或完整性校验失败') from exc
    # Sandbox applies even when generated HTML is opened directly. Opaque-frame
    # requests need CORS for local modules/fonts, but never credentialed access.
    headers = {'Cache-Control':'private, no-store', 'Referrer-Policy':'no-referrer',
        'X-Content-Type-Options':'nosniff', 'Access-Control-Allow-Origin':'*',
        'Content-Security-Policy':project_csp(request,ticket)}
    return FileResponse(target, media_type=mimetypes.guess_type(path)[0] or 'application/octet-stream',
        filename=target.name if download else None, headers=headers)
