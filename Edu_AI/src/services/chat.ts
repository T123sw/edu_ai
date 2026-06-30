// 聊天API服务
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

export interface ChatRequest {
  question: string;
  conversation_id?: string;
  model_id?: string;
  temperature?: number;
  max_tokens?: number;
  use_rag?: boolean;
  selected_doc_ids?: string[];
}

export interface Source {
  index: number;
  source: string;
  page: string | number;
  content: string;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  title?: string;  // 对话标题
  model_id?: string;
  sources: Source[];
  query_type?: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  model_name?: string;
}

export interface Conversation {
  conversation_id: string;
  title?: string;
  history: Array<{
    role: string;
    content: string;
    timestamp?: string;
  }>;
  message_count?: number;
}

/**
 * 发送聊天消息
 */
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  // 设置超时（60秒）
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查服务器连接或稍后重试');
    }
    throw error;
  }
}

/**
 * 获取对话历史
 */
export async function getConversationHistory(conversationId: string): Promise<Conversation> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`);

  if (!response.ok) {
    throw new Error(`获取对话历史失败: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 获取所有对话列表
 */
export async function listConversations(): Promise<{ 
  conversations: Array<{
    conversation_id: string;
    title: string;
    created_at?: string;
    message_count?: number;
  }>; 
  count: number;
  total_messages: number;
}> {
  const response = await fetch(`${API_BASE_URL}/conversations`);

  if (!response.ok) {
    throw new Error(`获取对话列表失败: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 删除对话
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`删除对话失败: ${response.statusText}`);
  }
}

/**
 * 截断对话消息（用于重发功能）
 */
export async function truncateConversation(conversationId: string, keepCount: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/truncate?keep_count=${keepCount}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`截断对话失败: ${response.statusText}`);
  }
}

/**
 * 删除指定索引的消息对
 */
export async function deleteMessagePair(conversationId: string, messageIndex: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/${messageIndex}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(`删除消息失败: ${response.statusText}`);
  }
}

/**
 * 获取可用模型列表
 */
export async function listModels(): Promise<ModelInfo[]> {
  const response = await fetch(`${API_BASE_URL}/models`);

  if (!response.ok) {
    throw new Error(`获取模型列表失败: ${response.statusText}`);
  }

  return response.json();
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<{ status: string; message: string; knowledge_base_ready: boolean }> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`健康检查失败: ${response.statusText}`);
  }

  return response.json();
}

