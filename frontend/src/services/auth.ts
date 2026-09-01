const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';

export interface User {
  username: string;
  role?: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface RegisterRequest {
  username: string;
  password: string;
  role?: string;
}

/**
 * 带超时的fetch请求
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout: number = 10000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接或后端服务是否正常运行');
    }
    throw error;
  }
}

/**
 * 用户登录
 * @param username 用户名
 * @param password 密码
 * @returns 登录响应，包含token和用户信息
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  if (!username || !password) {
    throw new Error('账号或密码不能为空');
  }

  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/api/auth/login`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
        }),
      },
      10000 // 10秒超时
    );

    if (!response.ok) {
      let errorMessage = '登录失败';
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // 如果无法解析JSON，使用状态文本
        errorMessage = response.status === 401 
          ? '用户名或密码错误' 
          : response.status === 500
          ? '服务器错误，请稍后重试'
          : `登录失败: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return {
      token: data.token,
      user: data.user,
    };
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('登录失败，请稍后重试');
  }
}

/**
 * 用户注册
 * @param username 用户名（3-50个字符）
 * @param password 密码（至少6个字符）
 * @param role 用户角色（可选，默认为student）
 * @returns 注册响应，包含token和用户信息
 */
export async function register(
  username: string,
  password: string,
  role: string = 'student'
): Promise<LoginResponse> {
  if (!username || !password) {
    throw new Error('账号或密码不能为空');
  }

  if (username.length < 3 || username.length > 50) {
    throw new Error('用户名长度必须在3-50个字符之间');
  }

  if (password.length < 6) {
    throw new Error('密码长度至少为6个字符');
  }

  try {
    const response = await fetchWithTimeout(
      `${API_BASE_URL}/api/auth/register`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          password,
          role,
        }),
      },
      10000 // 10秒超时
    );

    if (!response.ok) {
      let errorMessage = '注册失败';
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = `注册失败: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return {
      token: data.token,
      user: data.user,
    };
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      throw new Error(`无法连接到服务器 (${API_BASE_URL})，请检查后端服务是否已启动`);
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('注册失败，请稍后重试');
  }
}

/**
 * 获取当前用户信息
 * @param token JWT token
 * @returns 用户信息
 */
export async function getCurrentUser(token: string): Promise<User> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Token已过期或无效');
      }
      throw new Error(`获取用户信息失败: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('获取用户信息失败，请稍后重试');
  }
}

/**
 * 验证token是否有效
 * @param token JWT token
 * @returns 验证结果和用户信息
 */
export async function verifyToken(token: string): Promise<{ valid: boolean; user: User }> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/verify`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return {
        valid: false,
        user: { username: '' },
      };
    }

    return await response.json();
  } catch (error) {
    return {
      valid: false,
      user: { username: '' },
    };
  }
}
