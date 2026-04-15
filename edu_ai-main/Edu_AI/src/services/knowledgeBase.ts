// 知识库文档 API 服务
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface KnowledgeBaseDocument {
  id: string;
  name: string;
  type: 'file' | 'web';
  file_path?: string;
  url?: string;
  course_id: string;
  created_at: string;
  updated_at?: string;
}

/**
 * 获取课程的知识库文档列表
 * @param courseId 课程ID
 * @param token 认证token
 * @returns 文档列表
 */
export async function getKnowledgeBaseDocuments(
  courseId: string,
  token: string
): Promise<KnowledgeBaseDocument[]> {
  if (!courseId) {
    throw new Error('课程ID不能为空');
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/knowledge-base/documents`, {
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

/**
 * 将RAG系统的文档添加到课程知识库
 * @param courseId 课程ID
 * @param ragFilePath RAG系统中的文件路径
 * @param token 认证token
 */
export async function addRAGDocumentToCourseKB(
  courseId: string,
  ragFilePath: string,
  token: string
): Promise<KnowledgeBaseDocument> {
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
 * 上传文档到课程知识库（保留此接口用于直接上传到课程知识库的场景）
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
  onProgress?: (progress: number) => void
): Promise<KnowledgeBaseDocument> {
  if (!courseId || !file) {
    throw new Error('课程ID和文件不能为空');
  }

  try {
    const formData = new FormData();
    formData.append('file', file);

    return new Promise<KnowledgeBaseDocument>((resolve, reject) => {
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
        if (xhr.status === 200 || xhr.status === 201) {
          try {
            const result = JSON.parse(xhr.responseText) as KnowledgeBaseDocument;
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

