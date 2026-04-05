// 数据采集管道 API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

export type TaskStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED';
export type TaskType = 'crawl' | 'parse' | 'chunk';

export interface Task {
  task_id: string;
  task_type: TaskType;
  status: TaskStatus;
  progress: number;
  start_time: string;
  end_time?: string;
  details: Record<string, any>;
  error?: string;
}

export interface CrawlParams {
  keywords: string[];
  pages?: number;
}

export async function startCrawl(params: CrawlParams): Promise<{ task_id: string }> {
  const res = await fetch(`${API_BASE_URL}/api/pipeline/crawl`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'keyword', ...params }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getOverview(limit = 20): Promise<{ crawl: Task[]; parse: Task[]; chunk: Task[] }> {
  const res = await fetch(`${API_BASE_URL}/api/pipeline/overview?limit=${limit}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTaskStatus(taskId: string): Promise<Task> {
  const res = await fetch(`${API_BASE_URL}/api/pipeline/status/${taskId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

