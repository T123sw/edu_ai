import { Brand, Icon } from './ui';

export function SpaceNavigation({ active }: { active: 'home' | 'research' | 'interview' }) {
  return <>
    <a className="sl-space-brand" href="#/" aria-label="Edu AI 首页"><Brand /><span>学习空间</span></a>
    <nav className="sl-space-nav" aria-label="学习空间导航">
      <a href="#/" aria-current={active === 'home' ? 'page' : undefined}><Icon name="book" size={17} />课程学习</a>
      <a href="#/research" aria-current={active === 'research' ? 'page' : undefined}><Icon name="flask" size={17} />科研实践</a>
      <a href="#/resources"><Icon name="folder" size={17} />个人作品</a>
      <a href="#/interview" aria-current={active === 'interview' ? 'page' : undefined}><Icon name="briefcase" size={17} />面试 Agent<span className="sl-nav-soon">筹备中</span></a>
    </nav>
  </>;
}

export function InterviewEntry() {
  return <main className="sl-module-page sl-interview-page">
    <a className="sl-text-button" href="#/"><Icon name="back" size={16} />返回学习空间</a>
    <div className="sl-module-intro">
      <span className="sl-kicker">独立产品 · 筹备中</span>
      <h1>让下一次面试，<br />多一份准备。</h1>
      <p>围绕你的简历和目标岗位，练习真实求职中的表达、追问与现场解题。</p>
    </div>
    <div className="sl-interview-steps">{[
      ['01', '带着自己的经历', '以简历、项目材料和目标岗位作为模拟依据。'],
      ['02', '经历完整的面试', '实时语音交流，衔接笔试、项目追问和算法题。'],
      ['03', '找到下一次的突破口', '围绕具体回答与解题过程复盘，再针对性重练。'],
    ].map(([number, title, text]) => <article key={number}><span>{number}</span><h2>{title}</h2><p>{text}</p></article>)}</div>
    <section className="sl-module-note"><Icon name="briefcase" /><div><strong>面试 Agent 将独立提供服务</strong><p>当前尚未开放。开放后可从这里前往；课程资料和个人记录不会自动传入面试项目。</p></div></section>
    <a className="sl-primary" href="#/">先回到课程学习<Icon name="arrow" size={17} /></a>
  </main>;
}
