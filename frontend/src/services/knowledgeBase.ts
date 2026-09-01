// 知识库文档 API 服务
import type { JobRecord } from '../jobs/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

export interface KnowledgeBaseDocument {
  id: string;
  name: string;
  display_name?: string | null;
  type: 'file' | 'web';
  file_path?: string;
  url?: string;
  course_id: string;
  scope_type?: 'course' | 'knowledge_point';
  scope_id?: string;
  library_type?: 'course' | 'personal';
  owner_user_id?: string;
  promoted_from_document_id?: string;
  status:
    | 'received'
    | 'parsing'
    | 'chunking'
    | 'embedding'
    | 'indexing'
    | 'ready'
    | 'partially_ready'
    | 'failed';
  active_index_version?: string | null;
  pending_index_version?: string | null;
  page_count: number;
  chunk_count: number;
  failed_units: number;
  parser_name?: string | null;
  embedding_profile_id?: string | null;
  indexed_at?: string | null;
  last_job_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CourseKnowledgeBaseDocumentContent {
  document_id: string;
  file_path: string;
  file_name: string;
  content: string;
  chunks: Array<{
    id: number;
    content: string;
    page?: number;
    metadata: Record<string, any>;
  }>;
  total_chunks: number;
}

export interface KnowledgeBaseDocumentUploadResponse {
  document: KnowledgeBaseDocument;
  job: JobRecord;
}

export interface KnowledgeBaseRetrievalHit {
  chunk_id: string;
  content: string;
  score: number;
  page?: number | null;
  timestamp?: string | null;
  reranked: boolean;
}

export interface KnowledgeBaseRetrievalTestResponse {
  document_id: string;
  index_version: string;
  query: string;
  hits: KnowledgeBaseRetrievalHit[];
  elapsed_ms: number;
}

export interface KnowledgeBaseScopeOptions {
  scopeType?: 'course' | 'knowledge_point';
  scopeId?: string;
  aggregate?: boolean;
  libraryType?: 'course' | 'personal';
  includeDescendants?: boolean;
  limit?: number;
  offset?: number;
  promotedFromDocumentId?: string;
  status?: KnowledgeBaseDocument['status'];
  search?: string;
  sort?: 'created_desc' | 'created_asc' | 'name_asc' | 'name_desc';
}

/**
 * 获取课程的知识库文档列表
 * @param courseId 课程ID
 * @param token 认证token
 * @returns 文档列表
 */
export async function getKnowledgeBaseDocuments(
  courseId: string,
  token: string,
  options?: KnowledgeBaseScopeOptions,
): Promise<KnowledgeBaseDocument[]> {
  if (!courseId) {
    throw new Error('课程ID不能为空');
  }

  try {
    const params = new URLSearchParams();
    if (options?.scopeType) {
      params.set('scope_type', options.scopeType);
    }
    if (options?.scopeId) {
      params.set('scope_id', options.scopeId);
    }
    if (typeof options?.aggregate === 'boolean') {
      params.set('aggregate', options.aggregate ? 'true' : 'false');
    }
    if (options?.libraryType) {
      params.set('library_type', options.libraryType);
    }
    if (typeof options?.includeDescendants === 'boolean') {
      params.set('include_descendants', options.includeDescendants ? 'true' : 'false');
    }
    if (typeof options?.limit === 'number') {
      params.set('limit', String(options.limit));
    }
    if (typeof options?.offset === 'number') {
      params.set('offset', String(options.offset));
    }
    if (options?.status) {
      params.set('document_status', options.status);
    }
    if (options?.search) {
      params.set('search', options.search);
    }
    if (options?.sort) {
      params.set('sort', options.sort);
    }

    const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '获取文档列表失败' }));
      throw new Error(errorData.detail || `获取文档列表失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取文档列表失败，请稍后重试');
  }
}

export async function getKnowledgeBaseDocumentContent(
  courseId: string,
  documentId: string,
  token: string,
): Promise<CourseKnowledgeBaseDocumentContent> {
  if (!courseId || !documentId) {
    throw new Error('课程ID和文档ID不能为空');
  }
  const response = await fetch(
    `${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents/${documentId}/content`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取文档正文失败' }));
    throw new Error(errorData.detail || `获取文档正文失败: ${response.statusText}`);
  }
  return response.json();
}

/**
 * 将RAG系统的文档添加到课程知识库
 * @param courseId 课程ID
 * @param ragFilePath RAG系统中的文件路径
 * @param token 认证token
 */
export async function addRAGDocumentToCourseKB(
  courseId: string,
  ragFilePath: string,
  token: string,
  options?: KnowledgeBaseScopeOptions,
): Promise<KnowledgeBaseDocumentUploadResponse> {
  if (!courseId || !ragFilePath) {
    throw new Error('课程ID和文件路径不能为空');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents/add-from-rag`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        rag_file_path: ragFilePath,
        scope_type: options?.scopeType,
        scope_id: options?.scopeId,
        library_type: options?.libraryType,
        promoted_from_document_id: options?.promotedFromDocumentId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '添加到课程知识库失败' }));
      throw new Error(errorData.detail || `添加到课程知识库失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('添加到课程知识库失败，请稍后重试');
  }
}

/**
 * 上传用户资料；后端默认归入当前用户的个人知识库。
 * @param courseId 课程ID
 * @param file 文件对象
 * @param token 认证token
 * @param onProgress 上传进度回调（可选）
 * @returns 上传后的文档信息
 */
export async function uploadKnowledgeBaseDocument(
  courseId: string,
  file: File,
  token: string,
  onProgress?: (progress: number) => void,
  options?: KnowledgeBaseScopeOptions,
): Promise<KnowledgeBaseDocumentUploadResponse> {
  if (!courseId || !file) {
    throw new Error('课程ID和文件不能为空');
  }

  try {
    const formData = new FormData();
    formData.append('file', file);
    if (options?.scopeType) {
      formData.append('scope_type', options.scopeType);
    }
    if (options?.scopeId) {
      formData.append('scope_id', options.scopeId);
    }
    if (options?.libraryType) {
      formData.append('library_type', options.libraryType);
    }

    return new Promise<KnowledgeBaseDocumentUploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // 监听上传进度
      if (onProgress) {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            onProgress(percent);
          }
        });
      }

      xhr.addEventListener('load', () => {
        if (xhr.status === 200 || xhr.status === 201 || xhr.status === 202) {
          try {
            const result = JSON.parse(xhr.responseText) as KnowledgeBaseDocumentUploadResponse;
            resolve(result);
          } catch {
            reject(new Error('解析上传响应失败'));
          }
        } else {
          try {
            const errorData = JSON.parse(xhr.responseText);
            reject(new Error(errorData.detail || `上传失败: ${xhr.statusText}`));
          } catch {
            reject(new Error(`上传失败: ${xhr.statusText}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('网络错误，请检查连接'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('上传已取消'));
      });

      xhr.open('POST', `${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents`);
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);
    });
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('上传文档失败，请稍后重试');
  }
}

async function submitKnowledgeDocumentAction(
  courseId: string,
  documentId: string,
  token: string,
  action: 'retry' | 'reindex',
): Promise<JobRecord> {
  const response = await fetch(
    `${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents/${documentId}/${action}`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '提交任务失败' }));
    throw new Error(errorData.detail || `提交任务失败: ${response.statusText}`);
  }
  return response.json();
}

export function retryKnowledgeBaseDocument(
  courseId: string,
  documentId: string,
  token: string,
): Promise<JobRecord> {
  return submitKnowledgeDocumentAction(courseId, documentId, token, 'retry');
}

export function reindexKnowledgeBaseDocument(
  courseId: string,
  documentId: string,
  token: string,
): Promise<JobRecord> {
  return submitKnowledgeDocumentAction(courseId, documentId, token, 'reindex');
}

export async function testKnowledgeBaseDocumentRetrieval(
  courseId: string,
  documentId: string,
  token: string,
  query: string,
  topK = 5,
): Promise<KnowledgeBaseRetrievalTestResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents/${documentId}/test-retrieval`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, top_k: topK }),
    },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '检索测试失败' }));
    throw new Error(errorData.detail || `检索测试失败: ${response.statusText}`);
  }
  return response.json();
}

/**
 * 删除知识库文档
 * @param courseId 课程ID
 * @param documentId 文档ID
 * @param token 认证token
 */
export async function deleteKnowledgeBaseDocument(
  courseId: string,
  documentId: string,
  token: string
): Promise<void> {
  if (!courseId || !documentId) {
    throw new Error('课程ID和文档ID不能为空');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents/${documentId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '删除文档失败' }));
      throw new Error(errorData.detail || `删除文档失败: ${response.statusText}`);
    }
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('删除文档失败，请稍后重试');
  }
}

