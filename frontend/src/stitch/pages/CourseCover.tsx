import './CourseCover.css';

function courseTheme(title: string, id: string) {
  if (/诗|文学|语文|历史|鉴赏/.test(title)) return 'ink';
  if (/网络|通信/.test(title)) return 'teal';
  if (/人工智能|机器学习|AI/i.test(title)) return 'violet';
  if (/组成|系统|硬件/.test(title)) return 'slate';
  if (/数据|数学/.test(title)) return 'amber';
  if (/计算思维|编程|Python/i.test(title)) return 'indigo';
  const themes = ['indigo', 'teal', 'violet', 'slate', 'amber', 'ink'];
  const hash = Array.from(id).reduce((value, char) => (value * 31 + char.charCodeAt(0)) >>> 0, 0);
  return themes[hash % themes.length];
}

export function CourseCover({ title, id }: { title: string; id: string }) {
  const theme = courseTheme(title, id);
  return <div className={`course-cover course-cover--${theme}`} aria-hidden="true">
    <svg viewBox="0 0 440 140" fill="none" preserveAspectRatio="xMidYMid slice">
      <path className="course-cover__grid" d="M0 35H440M0 70H440M0 105H440M55 0V140M110 0V140M165 0V140M220 0V140M275 0V140M330 0V140M385 0V140" />
      <circle className="course-cover__halo" cx="325" cy="70" r="100" />
      <circle className="course-cover__halo" cx="325" cy="70" r="70" />
      {theme === 'ink' ? <g className="course-cover__drawing">
        <circle cx="320" cy="34" r="14" fill="currentColor" opacity=".3" stroke="none" />
        <path d="m155 140 72-85 50 54 39-48 84 79M217 67l10 25 10-13M298 84l18 15 9-25" />
        <path d="M130 119c65-15 94 26 179 2s100-4 131 0" opacity=".4" />
      </g> : theme === 'slate' ? <g className="course-cover__drawing">
        <rect x="260" y="29" width="80" height="80" rx="15" />
        <rect x="278" y="47" width="44" height="44" rx="7" fill="currentColor" fillOpacity=".1" />
        <path d="M275 17v12m25-12v12m25-12v12m-50 80v14m25-14v14m25-14v14M245 44h15m-15 25h15m-15 25h15m80-50h15m-15 25h15m-15 25h15" />
      </g> : theme === 'amber' ? <g className="course-cover__drawing">
        <ellipse cx="305" cy="34" rx="53" ry="16" fill="currentColor" fillOpacity=".08" />
        <path d="M252 34v66c0 21 106 21 106 0V34M252 56c0 21 106 21 106 0M252 78c0 21 106 21 106 0" />
      </g> : theme === 'indigo' ? <g className="course-cover__drawing">
        <path d="M300 47v20m-56 18h-26V38h54m56 47h47v36h-47" />
        <rect x="272" y="15" width="56" height="32" rx="9" fill="var(--cover-bg)" />
        <path d="m300 64 31 21-31 21-31-21 31-21Z" fill="var(--cover-bg)" />
        <rect x="272" y="113" width="56" height="24" rx="8" fill="var(--cover-bg)" />
        <path d="m290 26-5 5 5 5m20-10 5 5-5 5M300 106v7" />
      </g> : theme === 'violet' ? <g className="course-cover__drawing">
        <path d="m238 42 64-17-64 17 64 46-64-46m0 56 64-73m-64 73 64-10m0-63 63 45-63 18 63-18m-127 28 64 30 63-58" opacity=".7" />
        {[[238,42],[238,98],[302,25],[302,88],[302,128],[365,70]].map(([x,y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="11" fill="var(--cover-bg)" />)}
        <circle cx="365" cy="70" r="4" fill="currentColor" stroke="none" />
      </g> : <g className="course-cover__drawing">
        <path d="m227 38 59 32-22 44m22-44 68-36m-68 36 77 37m-77-37 30-59m-30 59 100-3" />
        {[[227,38,12],[286,70,22],[264,114,10],[354,34,14],[363,107,12],[316,11,7],[386,67,7]].map(([x,y,r]) =>
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="var(--cover-bg)" />)}
        <circle cx="286" cy="70" r="8" fill="currentColor" stroke="none" />
      </g>}
      <g className="course-cover__book" transform="translate(28 46)">
        <rect width="49" height="49" rx="15" fill="white" fillOpacity=".75" />
        <path d="M25 15c-5-3-10-3-14-1v21c4-2 9-2 14 1 5-3 10-3 14-1V14c-4-2-9-2-14 1Zm0 0v21M16 20h4m-4 5h4m10-5h4m-4 5h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  </div>;
}
