import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { User } from '../services/auth';
import { login as loginService, verifyToken } from '../services/auth';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  authReady: boolean;
  login: (username: string, password: string) => Promise<{ user: User; token: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = 'edu-ai-auth';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function restoreAuth() {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        if (!cancelled) {
          setAuthReady(true);
        }
        return;
      }

      try {
        const parsed = JSON.parse(stored) as { user: User; token: string };
        const result = await verifyToken(parsed.token);

        if (cancelled) return;

        if (result.valid) {
          setUser(result.user);
          setToken(parsed.token);
        } else {
          setUser(null);
          setToken(null);
          window.localStorage.removeItem(STORAGE_KEY);
        }
      } catch {
        if (cancelled) return;
        setUser(null);
        setToken(null);
        window.localStorage.removeItem(STORAGE_KEY);
      } finally {
        if (!cancelled) {
          setAuthReady(true);
        }
      }
    }

    void restoreAuth();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (username: string, password: string) => {
    const res = await loginService(username, password);
    setUser(res.user);
    setToken(res.token);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(res));
    return res; // 返回登录结果，以便在登录页面使用
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    window.localStorage.removeItem(STORAGE_KEY);
  };

  const value = useMemo(
    () => ({
      user,
      token,
      authReady,
      login,
      logout
    }),
    [user, token, authReady]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth 必须在 AuthProvider 内使用');
  }
  return ctx;
}


