import type { toCourseCardPresentation } from './courseCardPresentation';

type Props = {
  card: ReturnType<typeof toCourseCardPresentation>;
  action: string;
};

export function CourseCardContent({ card, action }: Props) {
  return <>
    <div className="teacher-course-card__heading">
      <span className="teacher-course-card__icon" aria-hidden="true">
        <svg width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 3.5h13a1 1 0 0 1 1 1V20H6a3 3 0 0 1-3-3V5.5a2 2 0 0 1 2-2Z" />
          <path d="M3 17a3 3 0 0 1 3-3h13M8 7h7M8 10h4M7 14v6" />
        </svg>
      </span>
      <h3 title={card.title}>{card.title}</h3>
    </div>
    <p className="teacher-course-card__description" title={card.description}>{card.description}</p>
    <dl className="teacher-course-card__metrics">
      {card.metrics.slice(2).map((metric) => <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>)}
    </dl>
    <div className="teacher-course-card__footer">
      <span>{card.updatedLabel}</span>
      <strong>{action}<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14m-5-5 5 5-5 5" /></svg></strong>
    </div>
  </>;
}
