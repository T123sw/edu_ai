import { lazy, Suspense, useEffect, useState } from 'react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthSessionProvider } from '../stitch/authSession';
import { AppShellProvider } from '../stitch/shared';
import { useAppearance } from '../stitch/theme/appearance';
import { ProfilePage } from '../stitch/pages/Profile';
import { LoginPage } from '../stitch/pages/LoginPage';
import '../stitch/styles.css';
import { LearningPreferences } from './LearningPreferences';

const RuntimeSettingsPage = lazy(() => import('../stitch/pages/RuntimeSettings').then(module => ({ default: module.RuntimeSettingsPage })));

function Account() {
  const { user, authReady, login, logout } = useAuth();
  const [hash, setHash] = useState(location.hash);
  const [theme, setTheme] = useAppearance();
  useEffect(() => {
    const update = () => { setHash(location.hash); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  if (!authReady) return <p role="status">正在恢复登录…</p>;
  if (!user) return <LoginPage onLogin={async ({ username, password }) => { await login(username.trim(), password); }} />;
  return (
    <AuthSessionProvider user={{ ...user, role: user.role === 'teacher' || user.role === 'admin' ? user.role : 'student' }} authenticated>
      <AppShellProvider selectedCourse={null} setSelectedCourse={() => undefined} theme={theme} setTheme={setTheme} logout={() => { logout(); location.assign(location.pathname); }}>
        <Suspense fallback={<p role="status">正在打开服务配置…</p>}>
          {hash.replace(/^#\/?/, '') === 'settings' ? <RuntimeSettingsPage /> : <><ProfilePage homeHref={location.pathname} /><LearningPreferences key={user.username} /></>}
        </Suspense>
      </AppShellProvider>
    </AuthSessionProvider>
  );
}

export default function AccountEntry() {
  return <AuthProvider><Account /></AuthProvider>;
}
