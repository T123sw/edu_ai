import React, { useMemo, useState } from 'react';
import { Button } from 'antd';
import type { StatusCardEvidenceDetail, StatusCardV2 } from '../../services/teacher/chatV2';
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

function renderChipList(items?: string[], kind: 'topic' | 'issue' = 'topic') {
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

function renderDetailGroup(title: string, items?: string[]) {
  if (!items || items.length === 0) return null;
  return (
    <div className="teacher-status-card__detail-group">
      <div className="teacher-status-card__detail-title">{title}</div>
      <div className="teacher-status-card__detail-list">
        {items.map((item) => (
          <div key={`${title}-${item}`} className="teacher-status-card__detail-item">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatEvidenceSourceLabel(sourceType?: string) {
  const value = String(sourceType || '').trim();
  if (value === 'assistant_message') return '来自回复';
  if (value === 'user_message') return '来自提问';
  return '来源记录';
}

function formatConfidenceLabel(confidence?: string) {
  const value = String(confidence || '').trim();
  if (value === 'high') return '高可信';
  if (value === 'medium') return '中可信';
  return '低可信';
}

function renderEvidenceDetailGroup(items?: StatusCardEvidenceDetail[]) {
  if (!items || items.length === 0) return null;
  return (
    <div className="teacher-status-card__detail-group teacher-status-card__detail-group--evidence">
      <div className="teacher-status-card__detail-title">观察证据</div>
      <div className="teacher-status-card__detail-list">
        {items.map((item, index) => (
          <div key={`evidence-${index}-${item.content}`} className="teacher-status-card__evidence-item">
            <div className="teacher-status-card__evidence-content">{item.content}</div>
            <div className="teacher-status-card__evidence-meta">
              <span className="teacher-status-card__meta-pill">{formatEvidenceSourceLabel(item.source_type)}</span>
              <span className="teacher-status-card__meta-pill teacher-status-card__meta-pill--confidence">
                {formatConfidenceLabel(item.confidence)}
              </span>
              <span className="teacher-status-card__meta-text">
                {item.source_message_count || 0} 条来源
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const StatusCardV2View: React.FC<Props> = ({ statusCard, onActionSelect }) => {
  const [expanded, setExpanded] = useState(false);
  const card = statusCard || fallbackCard;
  const topics = Array.isArray(card.topics) ? card.topics.slice(0, 3) : [];
  const issues = Array.isArray(card.issues) ? card.issues.slice(0, 3) : [];
  const facts = Array.isArray(card.confirmed_facts) ? card.confirmed_facts.slice(0, 2) : [];
  const sources = Array.isArray(card.source_labels) && card.source_labels.length > 0 ? card.source_labels : ['当前会话'];
  const actions = Array.isArray(card.suggested_actions) ? card.suggested_actions.slice(0, 3) : [];
  const studentSignals = Array.isArray(card.student_signals) ? card.student_signals.slice(0, 4) : [];
  const evidencePoints = Array.isArray(card.evidence_points) ? card.evidence_points.slice(0, 4) : [];
  const evidenceDetails = Array.isArray(card.evidence_details) ? card.evidence_details.slice(0, 4) : [];
  const extraConstraints = Array.isArray(card.extra_constraints) ? card.extra_constraints.slice(0, 4) : [];
  const capabilityPills = [
    card.workflow_label,
    card.allow_rag ? '文档检索开启' : null,
    card.allow_web ? '网页搜索开启' : null,
  ].filter(Boolean) as string[];

  const hasDetails = useMemo(
    () =>
      facts.length > 0 ||
      studentSignals.length > 0 ||
      evidencePoints.length > 0 ||
      evidenceDetails.length > 0 ||
      extraConstraints.length > 0,
    [facts.length, studentSignals.length, evidencePoints.length, evidenceDetails.length, extraConstraints.length],
  );

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
          {topics.length > 0 ? renderChipList(topics, 'topic') : <div className="teacher-status-card__empty">尚未形成明确主题。</div>}
          {issues.length > 0 ? <div style={{ marginTop: 10 }}>{renderChipList(issues, 'issue')}</div> : null}
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

      {hasDetails && (
        <div className="teacher-status-card__details-shell">
          <button
            type="button"
            className="teacher-status-card__details-toggle"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
          >
            <span>{expanded ? '收起详情' : '展开详情'}</span>
            <span className={`teacher-status-card__details-caret${expanded ? ' is-open' : ''}`}>⌄</span>
          </button>

          {expanded && (
            <div className="teacher-status-card__details-grid">
              {renderDetailGroup('已确认事实', facts)}
              {renderDetailGroup('学生信号', studentSignals)}
              {evidenceDetails.length > 0 ? renderEvidenceDetailGroup(evidenceDetails) : renderDetailGroup('观察证据', evidencePoints)}
              {renderDetailGroup('附加要求', extraConstraints)}
            </div>
          )}
        </div>
      )}
    </section>
  );
};

export default StatusCardV2View;
