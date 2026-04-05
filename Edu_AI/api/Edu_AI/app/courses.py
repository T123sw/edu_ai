"""课程管理 API

负责：
- 提供课程列表、课程详情的接口
- 使用 course_storage 统一管理课程基础信息、知识库与生成资料目录
- 在首次启动时写入默认的六门课程
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from core.course_storage import CourseStorageManager, storage_manager
from core.auth import auth_manager
from new_rag.api import get_rag_system

security = HTTPBearer()


router = APIRouter(prefix="/api/courses", tags=["课程"])


class CourseInfo(BaseModel):
    """与前端 `Course` 接口对齐的基础信息模型（不包含知识库与文件）"""

    id: str = Field(..., description="课程ID")
    title: str = Field(..., description="课程名称")
    description: str = Field(..., description="课程简介")
    icon: str = Field(..., description="课程图标（前端图标名）")
    color: str = Field(..., description="主题颜色")
    objectives: Optional[List[str]] = Field(
        default=None, description="教学目标，每个元素是一条目标"
    )
    knowledgeGraph: Optional[str] = Field(
        default=None, description="课程知识图谱（JSON字符串或URL）"
    )


class KnowledgeBaseDocument(BaseModel):
    """知识库文档模型"""
    id: str = Field(..., description="文档ID")
    name: str = Field(..., description="文档名称")
    type: str = Field(..., description="文档类型：file或web")
    file_path: Optional[str] = Field(None, description="文件路径（仅file类型）")
    url: Optional[str] = Field(None, description="URL（仅web类型）")
    course_id: str = Field(..., description="课程ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class AddRAGDocumentRequest(BaseModel):
    """将RAG文档添加到课程知识库的请求模型"""
    rag_file_path: str = Field(..., description="RAG系统中的文件路径")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """获取当前用户（依赖注入）"""
    token = credentials.credentials
    return auth_manager.get_current_user(token)


def _get_manager() -> CourseStorageManager:
    # 目前直接复用全局实例，后续可按需扩展
    return storage_manager


DEFAULT_COURSES: List[CourseInfo] = [
    CourseInfo(
        id="computational-thinking",
        title="计算思维",
        description="培养计算思维，学习问题分解、模式识别、抽象和算法设计",
        icon="CommentOutlined",
        color="#1890ff",
        objectives=[
            "理解计算思维的核心概念和方法",
            "掌握问题分解和模式识别的技巧",
            "培养抽象思维和算法设计能力",
            "通过实践项目提升计算思维能力",
        ],
        knowledgeGraph="",
    ),
    CourseInfo(
        id="data-structures",
        title="数据结构",
        description="深入学习各种数据结构及其应用，掌握算法设计与分析",
        icon="DatabaseOutlined",
        color="#52c41a",
    ),
    CourseInfo(
        id="operating-systems",
        title="操作系统",
        description="理解操作系统原理，学习进程管理、内存管理和文件系统",
        icon="CloudServerOutlined",
        color="#fa8c16",
    ),
    CourseInfo(
        id="computer-networks",
        title="计算机网络",
        description="掌握网络协议、网络架构和网络安全等核心知识",
        icon="FileTextOutlined",
        color="#722ed1",
    ),
    CourseInfo(
        id="computer-organization",
        title="计算机组成原理",
        description="学习计算机硬件组成、指令系统、存储系统和I/O系统",
        icon="CloudServerOutlined",
        color="#13c2c2",
    ),
    CourseInfo(
        id="database-principles",
        title="数据库原理",
        description="掌握数据库设计、SQL语言、事务处理和数据库管理系统",
        icon="DatabaseOutlined",
        color="#eb2f96",
    ),
]


def ensure_default_courses():
    """确保默认六门课程已写入存储目录"""

    mgr = _get_manager()
    for course in DEFAULT_COURSES:
        existing = mgr.get_course_info(course.id)
        if existing is None:
            # 创建目录结构并写入 course_info.json
            mgr.create_course_structure(course.id)
            mgr.save_course_info(course.id, course.model_dump())


@router.on_event("startup")
def _init_default_courses():
    # FastAPI 启动时自动确保默认课程存在
    ensure_default_courses()


@router.get("", response_model=List[CourseInfo], summary="获取课程列表")
def list_courses() -> List[CourseInfo]:
    """返回所有课程的基础信息"""

    mgr = _get_manager()
    results: List[CourseInfo] = []

    if not mgr.courses_dir.exists():
        ensure_default_courses()

    for course_dir in mgr.courses_dir.iterdir():
        if not course_dir.is_dir():
            continue
        info = mgr.get_course_info(course_dir.name)
        if not info:
            continue
        try:
            results.append(CourseInfo(**info))
        except Exception:
            # 忽略不合法的数据
            continue

    if not results:
        # 如果目录为空，再尝试写入默认课程
        ensure_default_courses()
        for course in DEFAULT_COURSES:
            results.append(course)

    return results


@router.get("/{course_id}", response_model=CourseInfo, summary="获取课程详情")
def get_course(course_id: str) -> CourseInfo:
    """根据ID获取课程基础信息"""

    mgr = _get_manager()
    info = mgr.get_course_info(course_id)
    if not info:
        raise HTTPException(status_code=404, detail="课程不存在")
    try:
        return CourseInfo(**info)
    except Exception as exc:  # pragma: no cover - 容错
        raise HTTPException(
            status_code=500, detail=f"课程数据格式错误: {exc}"
        ) from exc


@router.put("/{course_id}", response_model=CourseInfo, summary="更新课程信息")
def update_course(course_id: str, payload: CourseInfo) -> CourseInfo:
    """更新课程基础信息（前端课程编辑页使用）"""

    if payload.id != course_id:
        raise HTTPException(status_code=400, detail="课程ID不一致")

    mgr = _get_manager()
    mgr.create_course_structure(course_id)
    ok = mgr.save_course_info(course_id, payload.model_dump())
    if not ok:
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.post("", response_model=CourseInfo, summary="新建课程")
def create_course(payload: CourseInfo) -> CourseInfo:
    """新建课程（ID 由前端传入，保持与前端一致）"""

    mgr = _get_manager()
    if mgr.get_course_info(payload.id) is not None:
        raise HTTPException(status_code=400, detail="课程ID已存在")

    mgr.create_course_structure(payload.id)
    ok = mgr.save_course_info(payload.id, payload.model_dump())
    if not ok:
        raise HTTPException(status_code=500, detail="保存课程信息失败")
    return payload


@router.delete("/{course_id}", summary="删除课程")
def delete_course(course_id: str):
    """删除课程及其所有关联文件"""

    mgr = _get_manager()
    ok = mgr.delete_course(course_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除课程失败")
    return {"message": "课程已删除"}


@router.get("/{course_id}/materials", summary="获取课程生成资料列表")
def get_course_materials(
    course_id: str,
    material_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """获取课程生成资料列表"""
    _ = current_user
    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    materials = mgr.list_generated_materials(course_id, material_type=material_type)
    return materials


# 课程知识库文档相关接口
@router.get("/{course_id}/knowledge-base/documents", response_model=List[KnowledgeBaseDocument], summary="获取课程知识库文档列表")
def get_knowledge_base_documents(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取课程的知识库文档列表"""
    mgr = _get_manager()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 获取知识库索引
    index = mgr.get_knowledge_base_index(course_id)
    
    # 转换为API响应格式
    documents = []
    for item in index:
        doc_type = 'file'  # 默认是文件类型
        if 'url' in item:
            doc_type = 'web'
        
        documents.append(KnowledgeBaseDocument(
            id=item.get('id', f"doc-{datetime.now().timestamp()}"),
            name=item.get('filename', item.get('name', '未知文档')),
            type=doc_type,
            file_path=item.get('path') if doc_type == 'file' else None,
            url=item.get('url') if doc_type == 'web' else None,
            course_id=course_id,
            created_at=item.get('uploaded_at', datetime.now().isoformat()),
            updated_at=item.get('updated_at')
        ))
    
    return documents


@router.post("/{course_id}/knowledge-base/documents", response_model=KnowledgeBaseDocument, summary="上传文档到课程知识库")
async def upload_knowledge_base_document(
    course_id: str,
    file: UploadFile = File(..., description="文档文件（PDF、DOCX等）"),
    current_user: dict = Depends(get_current_user)
):
    """上传文档到课程知识库，并导入到RAG系统"""
    mgr = _get_manager()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 读取文件数据
    file_data = await file.read()
    
    # 保存到课程知识库
    relative_path = mgr.save_knowledge_base_file(course_id, file_data, file.filename)
    if not relative_path:
        raise HTTPException(status_code=500, detail="保存文件失败")
    
    # 获取课程目录的完整路径
    course_dir = mgr.get_course_dir(course_id)
    full_file_path = course_dir / relative_path
    
    # 导入到RAG系统
    try:
        rag_system = get_rag_system()
        rag_system.import_document(str(full_file_path), force_reimport=False)
    except Exception as e:
        # RAG导入失败不影响文件保存，只记录错误
        print(f"Warning: Failed to import document to RAG system: {e}")
    
    # 获取知识库索引以返回最新文档信息
    index = mgr.get_knowledge_base_index(course_id)
    latest_doc = None
    for item in reversed(index):  # 从后往前找最新的
        if item.get('filename') == file.filename:
            latest_doc = item
            break
    
    if not latest_doc:
        raise HTTPException(status_code=500, detail="获取文档信息失败")
    
    return KnowledgeBaseDocument(
        id=latest_doc.get('id', f"doc-{datetime.now().timestamp()}"),
        name=latest_doc.get('filename', file.filename),
        type='file',
        file_path=latest_doc.get('path'),
        course_id=course_id,
        created_at=latest_doc.get('uploaded_at', datetime.now().isoformat()),
        updated_at=None
    )


@router.post("/{course_id}/knowledge-base/documents/add-from-rag", response_model=KnowledgeBaseDocument, summary="将RAG系统的文档添加到课程知识库")
def add_rag_document_to_course_kb(
    course_id: str,
    request: AddRAGDocumentRequest,
    current_user: dict = Depends(get_current_user)
):
    """将RAG系统的文档添加到课程知识库"""
    mgr = _get_manager()
    rag_system = get_rag_system()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    rag_file_path = request.rag_file_path
    
    # 从RAG系统获取文档信息
    all_docs = rag_system.list_documents()
    rag_doc = None
    for doc in all_docs:
        if doc.get('file_path') == rag_file_path:
            rag_doc = doc
            break
    
    if not rag_doc:
        raise HTTPException(status_code=404, detail="RAG系统中未找到该文档")
    
    # 读取RAG系统中的文件
    from pathlib import Path
    rag_path = Path(rag_file_path)
    if not rag_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 读取文件内容
    with open(rag_path, 'rb') as f:
        file_data = f.read()
    
    # 获取文件名
    filename = rag_path.name
    
    # 保存到课程知识库
    relative_path = mgr.save_knowledge_base_file(course_id, file_data, filename)
    if not relative_path:
        raise HTTPException(status_code=500, detail="保存文件失败")
    
    # 获取课程目录的完整路径
    course_dir = mgr.get_course_dir(course_id)
    full_file_path = course_dir / relative_path
    
    # 导入到RAG系统（如果文件不在RAG系统中，则导入）
    try:
        # 检查文件是否已经在RAG系统中
        file_exists_in_rag = any(doc.get('file_path') == str(full_file_path) for doc in all_docs)
        if not file_exists_in_rag:
            rag_system.import_document(str(full_file_path), force_reimport=False)
    except Exception as e:
        # RAG导入失败不影响文件保存，只记录错误
        print(f"Warning: Failed to import document to RAG system: {e}")
    
    # 获取知识库索引以返回最新文档信息
    index = mgr.get_knowledge_base_index(course_id)
    latest_doc = None
    for item in reversed(index):  # 从后往前找最新的
        if item.get('filename') == filename:
            latest_doc = item
            break
    
    if not latest_doc:
        raise HTTPException(status_code=500, detail="获取文档信息失败")
    
    return KnowledgeBaseDocument(
        id=latest_doc.get('id', f"doc-{datetime.now().timestamp()}"),
        name=latest_doc.get('filename', filename),
        type='file',
        file_path=latest_doc.get('path'),
        course_id=course_id,
        created_at=latest_doc.get('uploaded_at', datetime.now().isoformat()),
        updated_at=None
    )


@router.delete("/{course_id}/knowledge-base/documents/{document_id}", summary="删除课程知识库文档")
def delete_knowledge_base_document(
    course_id: str,
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除课程知识库文档"""
    mgr = _get_manager()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 获取知识库索引
    index = mgr.get_knowledge_base_index(course_id)
    
    # 查找并删除文档
    doc_to_delete = None
    for item in index:
        if item.get('id') == document_id:
            doc_to_delete = item
            break
    
    if not doc_to_delete:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 删除物理文件
    if doc_to_delete.get('path'):
        file_path = mgr.get_file_path(course_id, doc_to_delete['path'])
        if file_path.exists():
            file_path.unlink()
            
            # 尝试从RAG系统删除
            try:
                rag_system = get_rag_system()
                rag_system.delete_document(str(file_path))
            except Exception as e:
                print(f"Warning: Failed to delete document from RAG system: {e}")
    
    # 从索引中移除
    index = [item for item in index if item.get('id') != document_id]
    mgr.save_knowledge_base_index(course_id, index)
    
    return {"message": "文档已删除"}


# 知识图谱相关接口
class KnowledgeGraphData(BaseModel):
    """知识图谱数据模型"""
    root: dict = Field(..., description="根节点数据")


def _find_kg_node(root: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    """在知识图谱树中按 id 查找节点并返回该节点（含 children）。"""

    if not isinstance(root, dict):
        return None

    if str(root.get("id")) == node_id:
        return root

    children = root.get("children")
    if not isinstance(children, list):
        return None

    for child in children:
        if not isinstance(child, dict):
            continue
        found = _find_kg_node(child, node_id)
        if found is not None:
            return found

    return None


@router.get("/{course_id}/knowledge-graph", response_model=KnowledgeGraphData, summary="获取课程知识图谱")
def get_knowledge_graph(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取课程的知识图谱数据"""
    mgr = _get_manager()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 获取知识图谱数据
    graph_data = mgr.get_knowledge_graph(course_id)
    
    if graph_data is None:
        # 如果不存在，返回空结构
        return KnowledgeGraphData(root={
            "id": "root",
            "label": "知识图谱",
            "data": {
                "level": 0,
                "summary": "课程知识图谱",
                "hasChildren": False,
                "type": "concept"
            },
            "children": []
        })
    
    return KnowledgeGraphData(root=graph_data)


@router.get(
    "/{course_id}/knowledge-graph/nodes/{node_id}",
    response_model=KnowledgeGraphData,
    summary="按节点ID获取知识图谱子树",
)
def get_knowledge_graph_subtree(
    course_id: str,
    node_id: str,
    current_user: dict = Depends(get_current_user),
):
    """按 node_id 获取知识图谱子树（返回格式仍为 root=节点）。"""

    mgr = _get_manager()

    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")

    graph_data = mgr.get_knowledge_graph(course_id)
    if graph_data is None:
        raise HTTPException(status_code=404, detail="课程知识图谱不存在")

    node = _find_kg_node(graph_data, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="知识图谱节点不存在")

    return KnowledgeGraphData(root=node)


@router.put("/{course_id}/knowledge-graph", response_model=KnowledgeGraphData, summary="保存课程知识图谱")
def save_knowledge_graph(
    course_id: str,
    payload: KnowledgeGraphData,
    current_user: dict = Depends(get_current_user)
):
    """保存课程的知识图谱数据"""
    mgr = _get_manager()
    
    # 检查课程是否存在
    if not mgr.get_course_info(course_id):
        raise HTTPException(status_code=404, detail="课程不存在")
    
    # 保存知识图谱数据
    ok = mgr.save_knowledge_graph(course_id, payload.root)
    
    if not ok:
        raise HTTPException(status_code=500, detail="保存知识图谱失败")
    
    return payload


