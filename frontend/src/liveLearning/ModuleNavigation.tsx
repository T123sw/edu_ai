export function ModuleNavigation({ active, classroomHref }: { active: 'classroom' | 'practice' | 'exam' | 'resources'; classroomHref: string }) {
  const modules = [
    { id: 'classroom', label: 'AI 课堂', href: classroomHref },
    { id: 'practice', label: '互动实验', href: '#/practice' },
    { id: 'exam', label: '考试模拟', href: '#/exam' },
    { id: 'resources', label: '我的资源', href: '#/my-resources' },
  ];
  return <nav className="sl-main-nav sl-module-nav" aria-label="主导航">
    {modules.map(module => <a key={module.id} href={module.href} className={active === module.id ? 'active' : undefined} aria-current={active === module.id ? 'page' : undefined}>{module.label}</a>)}
  </nav>;
}
