// RAG API服务
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
const AUTH_STORAGE_KEY = 'edu-ai-auth';

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as { token?: string };
    return parsed.token || null;
  } catch {
    return null;
  }
}

export interface RAGQueryRequest {
  question: string;
  top_k?: number;
}

export interface RAGSource {
  content: string;
  source: string;
  page: number;
  distance?: number;
  modality?: 'text' | 'image' | string;
  image_path?: string;
  image_url?: string;
  image_name?: string;
  image_alt?: string;
  image_width?: number;
  image_height?: number;
}

export interface RAGQueryResponse {
  question: string;
  answer: string;
  sources: RAGSource[];
}

export interface RAGImportResponse {
  status: 'success' | 'skipped' | 'error';
  message: string;
  file?: string;
  file_path?: string;
  chunk_count?: number;
  image_url?: string;
}

export interface RAGStats {
  document_count: number;
  indexed_files: number;
  indexed_files_list: string[];
}

export interface KnowledgeDocument {
  file_path: string;
  file_name: string;
  include_in_search: boolean;
  chunk_count: number;
  image_chunk_count?: number;
  imported_at?: string;
  summary?: string;
  summary_updated_at?: string;
  summary_title?: string;
  summary_title_updated_at?: string;
  file_size?: number;
  page_count?: number;
  hash?: string;
  owner?: string;
  // 网页来源相关字段
  source_url?: string;
  source_title?: string;
  source_domain?: string;
  source_site_name?: string;
  doc_kind?: string;
  modality?: string;
  image_url?: string;
  source_icon_url?: string;
  course_id?: string;
  library_type?: 'course' | 'personal' | string;
  scope_type?: string;
  scope_id?: string;
  knowledge_node_id?: string;
  course_document_id?: string;
}

export interface DocumentSample {
  content: string;
  page?: number;
  id?: string;
  modality?: 'text' | 'image' | string;
  image_path?: string;
}

export interface DocumentDetail extends KnowledgeDocument {
  samples: DocumentSample[];
}

export interface DocumentChunk {
  id: number;
  content: string;
  page?: number;
  metadata: Record<string, any>;
}

export interface DocumentContent {
  file_path: string;
  file_name: string;
  content: string; // 完整文本内容
  chunks: DocumentChunk[]; // 所有chunks的详细信息
  total_chunks: number;
}

export interface DocumentSummaryResponse {
  file_path: string;
  summary: string;
  summary_updated_at?: string;
}

export interface UploadTempResponse {
  job_id: string;
  temp_file_path: string;
  filename: string;
}

export const IMAGE_FILE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'];

export function isImageFileName(fileName: string): boolean {
  const lower = String(fileName || '').toLowerCase();
  return IMAGE_FILE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function resolvePreviewMediaRequestUrl(mediaUrl: string): string {
  const raw = String(mediaUrl || '').trim();
  if (!raw) {
    throw new Error('媒体地址不能为空');
  }

  if (raw.startsWith('/api/')) {
    return `${API_BASE_URL}${raw}`;
  }

  try {
    const parsed = new URL(raw);
    if (parsed.pathname.startsWith('/api/rag/')) {
      return `${API_BASE_URL}${parsed.pathname}${parsed.search}`;
    }
    return parsed.toString();
  } catch {
    const normalized = raw.startsWith('/') ? raw : `/${raw}`;
    return `${API_BASE_URL}${normalized}`;
  }
}

export async function loadPreviewMediaUrl(mediaUrl: string): Promise<string> {
  const requestUrl = resolvePreviewMediaRequestUrl(mediaUrl);
  const token = getAuthToken();
  const response = await fetch(requestUrl, {
    method: 'GET',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new Error(errorText || `加载媒体预览失败: ${response.statusText}`);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export function revokePreviewMediaUrl(objectUrl?: string | null): void {
  if (objectUrl && objectUrl.startsWith('blob:')) {
    URL.revokeObjectURL(objectUrl);
  }
}

export interface ImportProgress {
  job_id: string;
  status: string;
  progress: number;
  stage: string;
  message?: string;
  file?: string;
}

/**
 * RAG问答
 * @param question 问题
 * @param top_k 检索的文档数量（默认5）
 * @returns RAG问答结果
 */
export async function ragQuery(
  question: string,
  top_k: number = 5
): Promise<RAGQueryResponse> {
  if (!question || question.trim() === '') {
    throw new Error('问题不能为空');
  }

  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        top_k,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'RAG问答失败' }));
      throw new Error(errorData.detail || `RAG问答失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('RAG问答失败，请稍后重试');
  }
}

/**
 * 上传并导入文档到知识库
 * @param file 支持的文件类型：PDF、Word（.doc/.docx）、文本（.txt/.md）
 * @param forceReimport 是否强制重新导入
 * @param onProgress 上传进度回调
 * @returns 导入结果
 */
export async function importDocument(
  file: File,
  forceReimport: boolean = false,
  onProgress?: (progress: number) => void
): Promise<RAGImportResponse> {
  if (!file) {
    throw new Error('请选择文件');
  }

  // 支持的文件类型
  const allowedExtensions = ['.pdf', '.doc', '.docx', '.txt', '.md', '.markdown'];
  const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
  
  if (!allowedExtensions.includes(fileExt)) {
    throw new Error(`不支持的文件类型: ${fileExt}，支持的类型: ${allowedExtensions.join(', ')}`);
  }

  try {
    // 第一步：上传到临时目录（进度 0-50，完全按真实上传百分比映射）
    const uploadResponse = await uploadTempWithProgress(file, (uploadPercent) => {
      if (onProgress) {
        // uploadPercent 为 0-100，直接线性映射到整体进度的前 50%
        const overall = Math.round(uploadPercent * 0.5);
        onProgress(overall);
      }
    });

    // 第二步：后台解析+导入（进度 50-100，使用轮询）
    const { job_id, temp_file_path } = uploadResponse;

    // 启动导入请求（不等待进度）
    const importPromise = startImportFromTemp(job_id, temp_file_path, forceReimport);

    // 轮询进度
    const pollInterval = 800;
    let timer: number | undefined;

    const startPolling = () => {
      timer = window.setInterval(async () => {
        try {
          const progress = await getImportProgress(job_id);
          if (onProgress) {
            const backend = Math.max(0, Math.min(100, progress.progress || 0));
            // 后台进度占整体的后 50%
            const overall = 50 + Math.round(backend * 0.5);
            onProgress(Math.min(overall, 99));
          }
        } catch {
          // 忽略单次进度查询失败
        }
      }, pollInterval);
    };

    startPolling();

    try {
      const result = await importPromise;
      if (onProgress) {
        onProgress(100);
      }
      return result;
    } finally {
      if (timer !== undefined) {
        window.clearInterval(timer);
      }
    }
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('导入文档失败，请稍后重试');
  }
}

/**
 * 上传并导入图片到 RAG v2 图片索引。
 */
export async function importImageDocument(
  file: File,
  onProgress?: (progress: number) => void
): Promise<RAGImportResponse> {
  if (!file) {
    throw new Error('请选择图片');
  }
  if (!isImageFileName(file.name)) {
    throw new Error(`不支持的图片类型，支持的类型: ${IMAGE_FILE_EXTENSIONS.join(', ')}`);
  }

  const formData = new FormData();
  formData.append('file', file);

  return new Promise<RAGImportResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200 || xhr.status === 201) {
        try {
          if (onProgress) {
            onProgress(100);
          }
          resolve(JSON.parse(xhr.responseText) as RAGImportResponse);
        } catch {
          reject(new Error('解析图片上传响应失败'));
        }
      } else {
        try {
          const errorData = JSON.parse(xhr.responseText);
          reject(new Error(errorData.detail || `图片上传失败: ${xhr.statusText}`));
        } catch {
          reject(new Error(`图片上传失败: ${xhr.statusText}`));
        }
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('网络错误，请检查连接'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('图片上传已取消'));
    });

    const token = getAuthToken();
    xhr.open('POST', `${API_BASE_URL}/api/rag/import_image`);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    xhr.send(formData);
  });
}

async function uploadTempWithProgress(
  file: File,
  onUploadProgress?: (percent: number) => void
): Promise<UploadTempResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return new Promise<UploadTempResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onUploadProgress) {
        const percent = Math.round((e.loaded / e.total) * 100);
        onUploadProgress(percent);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        try {
          const result = JSON.parse(xhr.responseText) as UploadTempResponse;
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

    const token = getAuthToken();
    xhr.open('POST', `${API_BASE_URL}/api/rag/upload_temp`);
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    xhr.send(formData);
  });
}

async function startImportFromTemp(
  jobId: string,
  tempFilePath: string,
  forceReimport: boolean
): Promise<RAGImportResponse> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/rag/import/path`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      file_path: tempFilePath,
      force_reimport: forceReimport,
      job_id: jobId,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '导入失败' }));
    throw new Error(errorData.detail || `导入失败: ${response.statusText}`);
  }

  return (await response.json()) as RAGImportResponse;
}

export async function getImportProgress(jobId: string): Promise<ImportProgress> {
  const params = new URLSearchParams({ job_id: jobId });
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/rag/import/progress?${params.toString()}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: '获取进度失败' }));
    throw new Error(errorData.detail || `获取进度失败: ${response.statusText}`);
  }

  return (await response.json()) as ImportProgress;
}

/**
 * 从服务器路径导入文档
 * @param filePath 文件路径
 * @param forceReimport 是否强制重新导入
 * @returns 导入结果
 */
export async function importDocumentFromPath(
  filePath: string,
  forceReimport: boolean = false
): Promise<RAGImportResponse> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }

  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/import/path`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        file_path: filePath,
        force_reimport: forceReimport,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '导入失败' }));
      throw new Error(errorData.detail || `导入失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('导入文档失败，请稍后重试');
  }
}

/**
 * 获取知识库统计信息
 * @returns 统计信息
 */
export async function getRAGStats(): Promise<RAGStats> {
  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/stats`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '获取统计信息失败' }));
      throw new Error(errorData.detail || `获取统计信息失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取统计信息失败，请稍后重试');
  }
}

/**
 * 删除文档
 * @param filePath 文件路径
 * @returns 删除结果
 */
export async function deleteDocument(filePath: string): Promise<{ status: string; message: string }> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }

  try {
    // URL编码文件路径
    const encodedPath = encodeURIComponent(filePath);
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/document/${encodedPath}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '删除失败' }));
      throw new Error(errorData.detail || `删除失败: ${response.statusText}`);
    }

    return await response.json();
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

/**
 * 获取已导入的文档列表
 */
export async function renameDocument(filePath: string, newName: string): Promise<KnowledgeDocument> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }
  const name = (newName || '').trim();
  if (!name) {
    throw new Error('新名称不能为空');
  }

  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/document/rename`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        file_path: filePath,
        new_name: name,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '重命名失败' }));
      throw new Error(errorData.detail || `重命名失败: ${response.statusText}`);
    }

    return (await response.json()) as KnowledgeDocument;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('重命名文档失败，请稍后重试');
  }
}

/**
 * 获取已导入的文档列表
 */
export async function listDocuments(): Promise<KnowledgeDocument[]> {
  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/documents`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
 * 更新文档是否参与检索
 */
export async function updateDocumentParticipation(
  filePath: string,
  includeInSearch: boolean
): Promise<KnowledgeDocument> {
  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/document/participation`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        file_path: filePath,
        include_in_search: includeInSearch,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '更新失败' }));
      throw new Error(errorData.detail || `更新失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('更新文档状态失败，请稍后重试');
  }
}

/**
 * 获取文档详情
 */
export async function getDocumentDetails(filePath: string): Promise<DocumentDetail> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }

  try {
    const params = new URLSearchParams({ file_path: filePath });
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/document/details?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '获取详情失败' }));
      throw new Error(errorData.detail || `获取详情失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取文档详情失败，请稍后重试');
  }
}

/**
 * 获取或生成文档摘要
 */
export async function getDocumentSummary(
  filePath: string,
  forceRefresh: boolean = false
): Promise<DocumentSummaryResponse> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }

  try {
    const token = getAuthToken();
    const url = `${API_BASE_URL}/api/rag/document/summary`;
    const requestBody = {
      file_path: filePath,
      force_refresh: forceRefresh,
    };
    
    console.log('getDocumentSummary: 发送请求', { url, filePath, forceRefresh });
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(requestBody),
    });

    console.log('getDocumentSummary: 响应状态', response.status, response.statusText);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '获取摘要失败' }));
      console.error('getDocumentSummary: 请求失败', errorData);
      throw new Error(errorData.detail || `获取摘要失败: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('getDocumentSummary: 请求成功', result);
    return result;
  } catch (error) {
    console.error('getDocumentSummary: 异常', error);
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取文档摘要失败，请稍后重试');
  }
}

/**
 * 获取文档完整内容
 * @param filePath 文件路径
 * @returns 文档完整内容
 */
export async function getDocumentContent(filePath: string): Promise<DocumentContent> {
  if (!filePath) {
    throw new Error('文件路径不能为空');
  }

  try {
    const params = new URLSearchParams({ file_path: filePath });
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/rag/document/content?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '获取文档内容失败' }));
      throw new Error(errorData.detail || `获取文档内容失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取文档内容失败，请稍后重试');
  }
}


