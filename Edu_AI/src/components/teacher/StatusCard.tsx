import React from 'react';
import { Button } from 'antd';
import type { StatusCardV2 } from '../../services/teacher/chatV2';
import './StatusCard.css';

type Props = {
  statusCard?: StatusCardV2 | null;
  onActionSelect?: (action: string) => void;
};

const fallbackCard: StatusCardV2 = {
  mode: 'chat',
  status_label: '普通对话',
  source_labels: ['当前会话'],
  waiting_label: '继续提问，或告诉我你想生成什么',
  suggested_actions: ['继续提问', '生成报告'],
};

function renderList(items?: string[], kind: 'topic' | 'issue' = 'topic') {
  if (!items || items.length === 0) return null;
  return (
    <div className="teacher-status-card__list">
      {items.map((item) => (
        <span
          key={`${kind}-${item}`}
          className={`teacher-status-card__chip${kind === 'issue' ? ' teacher-status-card__chip--issue' : ''}`}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

const StatusCard: React.FC<Props> = ({ statusCard, onActionSelect }) => {
  const card = statusCard || fallbackCard;
  const topics = Array.isArray(card.topics) ? card.topics.slice(0, 3) : [];
  const issues = Array.isArray(card.issues) ? card.issues.slice(0, 3) : [];
  const facts = Array.isArray(card.confirmed_facts) ? card.confirmed_facts.slice(0, 2) : [];
  const sources = Array.isArray(card.source_labels) && card.source_labels.length > 0 ? card.source_labels : ['当前会话'];
  const actions = Array.isArray(card.suggested_actions) ? card.suggested_actions.slice(0, 3) : [];
  const capabilityPills = [
    card.workflow_label,
    card.allow_rag ? '文档检索开启' : null,
    card.allow_web ? '网页搜索开启' : null,
  ].filter(Boolean) as string[];

  return (
    <section className="teacher-status-card" data-mode={card.mode || 'chat'} aria-label="当前系统状态">
      <div className="teacher-status-card__eyebrow">Current Workspace State</div>

      <div className="teacher-status-card__header">
        <div className="teacher-status-card__title-group">
          <h3 className="teacher-status-card__title">{card.status_label || '普通对话'}</h3>
          <div className="teacher-status-card__subtitle">
            {card.waiting_label || card.active_artifact_label || '系统已经整理好当前会话重点，可以继续追问或发起生成。'}
          </div>
        </div>

        {capabilityPills.length > 0 && (
          <div className="teacher-status-card__header-tags">
            {capabilityPills.map((pill) => (
              <span key={pill} className="teacher-status-card__pill">
                {pill}
              </span>
            ))}
          </div>
        )}
      </div>

      {card.summary_hint && <div className="teacher-status-card__summary">{card.summary_hint}</div>}

      <div className="teacher-status-card__grid">
        <div className="teacher-status-card__section">
          <div className="teacher-status-card__section-title">当前理解</div>
          {card.goal ? <div className="teacher-status-card__goal">{card.goal}</div> : null}
          {topics.length > 0 ? renderList(topics, 'topic') : <div className="teacher-status-card__empty">尚未形成明确主题。</div>}
          {issues.length > 0 ? <div style={{ marginTop: 10 }}>{renderList(issues, 'issue')}</div> : null}
        </div>

        <div className="teacher-status-card__stack">
          <div className="teacher-status-card__section">
            <div className="teacher-status-card__section-title">当前依据</div>
            <div className="teacher-status-card__line">
              <strong>来源：</strong>
              {sources.join(' · ')}
            </div>
            {facts.length > 0 && (
              <div className="teacher-status-card__line">
                <strong>已确认：</strong>
                {facts.join('；')}
              </div>
            )}
          </div>

          <div className="teacher-status-card__section">
            <div className="teacher-status-card__section-title">约束与下一步</div>
            {card.audience || card.tone || card.length || card.grade_level || card.subject ? (
              <div className="teacher-status-card__line">
                <strong>约束：</strong>
                {[card.audience, card.tone, card.length, card.grade_level, card.subject].filter(Boolean).join(' · ')}
              </div>
            ) : (
              <div className="teacher-status-card__line">
                <strong>下一步：</strong>
                {card.waiting_label || '可以继续补充目标、资料或直接发起生成。'}
              </div>
            )}

            {actions.length > 0 && (
              <div className="teacher-status-card__action-row">
                {actions.map((action) => (
                  <Button
                    key={action}
                    size="small"
                    className="teacher-status-card__action"
                    onClick={() => onActionSelect?.(action)}
                  >
                    {action}
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default StatusCard;
