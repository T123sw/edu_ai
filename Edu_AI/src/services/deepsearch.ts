/**
 * 深度搜索和爬取服务
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001';
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

export interface DeepSearchRequest {
  query: string;
  max_urls?: number;
  crawl_timeout?: number;
}

export interface DeepSearchResponse {
  ok: boolean;
  message?: string;
  batch_id?: string;
  query?: string;
  total_urls?: number;
  success_count?: number;
  failed_count?: number;
  links?: string[];
  created_at?: string;
  results?: CrawlResult[];  // 可选：如果后端直接返回结果
}

export interface CrawlResult {
  url: string;
  title: string;
  content?: string;
  content_type: string;
  status: 'success' | 'failed';
  error_message?: string;
  metadata?: Record<string, any>;
  file_path?: string;
}

export interface CrawlResultsResponse {
  ok: boolean;
  message?: string;
  batch_id?: string;
  query?: string;
  total_urls?: number;
  success_count?: number;
  failed_count?: number;
  created_at?: string;
  results?: CrawlResult[];
}

export interface CrawlHistoryItem {
  batch_id: string;
  query: string;
  total_urls: number;
  success_count: number;
  failed_count: number;
  created_at: string;
}

export interface CrawlHistoryResponse {
  ok: boolean;
  batches?: CrawlHistoryItem[];
}

/**
 * 深度搜索并爬取URL内容
 */
export async function deepSearchAndCrawl(
  request: DeepSearchRequest,
  options?: { signal?: AbortSignal }
): Promise<DeepSearchResponse> {
  try {
    const token = getAuthToken();
    const response = await fetch(`${API_BASE_URL}/agent/deepsearch-and-crawl`, {
      method: 'POST',
      signal: options?.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `HTTP error! status: ${response.status}`;
      try {
        const errorJson = JSON.parse(errorText);
        errorMessage = errorJson.detail || errorJson.message || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error: any) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    throw error;
  }
}

/**
 * 获取爬取结果
 */
export async function getCrawlResults(
  batchId: string,
  options?: { signal?: AbortSignal }
): Promise<CrawlResultsResponse> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/agent/crawl-results/${batchId}`, {
    signal: options?.signal,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      return { ok: false, message: '批次不存在' };
    }
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
}

/**
 * 获取爬取历史
 */
export async function getCrawlHistory(
  limit: number = 20,
  options?: { signal?: AbortSignal }
): Promise<CrawlHistoryResponse> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/agent/crawl-history?limit=${limit}`, {
    signal: options?.signal,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.json();
}

