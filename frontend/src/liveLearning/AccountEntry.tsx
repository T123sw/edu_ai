import { lazy, Suspense, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthSessionProvider } from '../stitch/authSession';
import { AppShellProvider, type ThemeName } from '../stitch/shared';
import { ProfilePage } from '../stitch/pages/Profile';
import { LoginPage } from '../stitch/pages/LoginPage';
import '../stitch/styles.css';

const RuntimeSettingsPage = lazy(() => import('../stitch/pages/RuntimeSettings').then(module => ({ default: module.RuntimeSettingsPage })));

function Account() {
  const { user, authReady, login, logout } = useAuth();
  const [hash, setHash] = useState(location.hash);
  const [theme, setTheme] = useState<ThemeName>(() => {
    const stored = localStorage.getItem('stitch-theme');
    return stored === 'forest' || stored === 'sunset' || stored === 'dark' ? stored : 'ocean';
  });
  useEffect(() => {
    const update = () => { setHash(location.hash); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  useEffect(() => {
    localStorage.setItem('stitch-theme', theme);
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  if (!authReady) return <p role="status">正在恢复登录…</p>;
  if (!user) return <LoginPage onLogin={async ({ username, password }) => { await login(username.trim(), password); }} />;
  return (
    <AuthSessionProvider user={{ ...user, role: user.role === 'teacher' || user.role === 'admin' ? user.role : 'student' }} authenticated>
      <AppShellProvider selectedCourse={null} setSelectedCourse={() => undefined} theme={theme} setTheme={setTheme} logout={() => { logout(); location.assign(location.pathname); }}>
        <Suspense fallback={<p role="status">正在打开服务配置…</p>}>
          {hash.replace(/^#\/?/, '') === 'settings' ? <RuntimeSettingsPage /> : <ProfilePage homeHref={location.pathname} />}
        </Suspense>
      </AppShellProvider>
    </AuthSessionProvider>
  );
}

export default function AccountEntry() {
  return <AuthProvider><Account /></AuthProvider>;
}
