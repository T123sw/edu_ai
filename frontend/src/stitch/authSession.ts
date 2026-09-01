import { createContext, createElement, useContext, type PropsWithChildren } from "react";

export const AUTH_STORAGE_KEY = "edu-ai-auth";

export type AuthUser = {
  username: string;
  role: "admin" | "teacher" | "student";
};

export type StoredAuthSession = {
  token: string;
  user: AuthUser;
};

export function normalizeAuthUser(user: {
  username?: string;
  role?: string;
}): AuthUser | null {
  const username = String(user.username ?? "").trim();
  const role = String(user.role ?? "student").trim().toLowerCase();
  if (!username || !["admin", "teacher", "student"].includes(role)) {
    return null;
  }
  return { username, role: role as AuthUser["role"] };
}

export function parseStoredAuthSession(raw: string | null): StoredAuthSession | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as {
      token?: unknown;
      user?: { username?: string; role?: string };
    };
    const token = typeof value.token === "string" ? value.token.trim() : "";
    const user = normalizeAuthUser(value.user ?? {});
    return token && user ? { token, user } : null;
  } catch {
    return null;
  }
}

type AuthSessionValue = {
  user: AuthUser | null;
  authenticated: boolean;
};

const AuthSessionContext = createContext<AuthSessionValue>({
  user: null,
  authenticated: false,
});

export function AuthSessionProvider({
  children,
  user,
  authenticated,
}: PropsWithChildren<AuthSessionValue>) {
  return createElement(
    AuthSessionContext.Provider,
    { value: { user, authenticated } },
    children,
  );
}

export function useAuthSession() {
  return useContext(AuthSessionContext);
}
