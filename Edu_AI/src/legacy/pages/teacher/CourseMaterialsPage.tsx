import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Tabs,
  List,
  Button,
  Typography,
  Space,
  Dropdown,
  message,
  Empty,
  Modal,
  Divider,
  Spin,
  Radio,
  Input,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  AudioOutlined,
  BookOutlined,
  ApartmentOutlined,
  FileTextOutlined,
  FilePptOutlined,
  EditOutlined,
  QuestionCircleOutlined,
  MoreOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlusOutlined,
  ReloadOutlined,
  PushpinOutlined,
} from '@ant-design/icons';
import { useCourseMaterialsStore, type CourseMaterial } from '../../store/teacher/useCourseMaterialsStore';
import { useStore, type GeneratedFile } from '../../store/teacher/useStore';
import { deleteCourseMaterial, getLessonPlanDetail, getCourseMaterials, pinCourseMaterial, type LessonPlanResponse, type ReportResponse, type QuizResponse } from '../../services/teacher/api';
import { resolvePptAssetUrl } from '../../services/teacher/pptAssets';
import MarkdownPreview from '../../components/shared/MarkdownPreview';
import './CourseMaterialsPage.css';

const { Title, Text, Paragraph } = Typography;

// 六个功能类型
const materialTypes: Array<{
  key: GeneratedFile['type'];
  label: string;
  icon: React.ReactNode;
  color: string;
}> = [
  { key: 'audio', label: '音频概览', icon: <AudioOutlined />, color: '#722ed1' },
  { key: 'lesson_plan', label: '教案生成', icon: <BookOutlined />, color: '#52c41a' },
  { key: 'graph', label: '思维导图', icon: <ApartmentOutlined />, color: '#eb2f96' },
  { key: 'report', label: '报告', icon: <FileTextOutlined />, color: '#faad14' },
  { key: 'ppt', label: 'PPT', icon: <FilePptOutlined />, color: '#d46b08' },
  { key: 'blog', label: '教学博客', icon: <EditOutlined />, color: '#ff7875' },
  { key: 'quiz', label: '测验', icon: <QuestionCircleOutlined />, color: '#1890ff' },
];

const getFileIcon = (type: GeneratedFile['type'], size = 20) => {
  const typeConfig = materialTypes.find(t => t.key === type);
  if (typeConfig) {
    return React.cloneElement(typeConfig.icon as React.ReactElement, {
      style: { fontSize: size, color: typeConfig.color },
    });
  }
  return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
};

const normalizeAnswer = (value: string) => (value || '').trim().toLowerCase();

const extractChoiceKey = (value: string) => {
  const normalized = normalizeAnswer(value);
  const match = normalized.match(/^([a-d])[\.|、|\)|\s]/i) || normalized.match(/^([a-d])$/i);
  return match ? match[1].toUpperCase() : '';
};

const isQuizAnswerCorrect = (q: QuizResponse['questions'][number], userAnswerRaw: string) => {
  const userAnswer = normalizeAnswer(userAnswerRaw);
  const standardAnswer = normalizeAnswer(q.answer || '');

  if (q.type === 'choice') {
    const userKey = extractChoiceKey(userAnswerRaw || '');
    const answerKey = extractChoiceKey(q.answer || '');

    if (userKey && answerKey) {
      return userKey === answerKey;
    }

    if (answerKey && Array.isArray(q.options)) {
      const idx = answerKey.charCodeAt(0) - 'A'.charCodeAt(0);
      const mapped = q.options[idx];
      if (mapped && normalizeAnswer(mapped) === userAnswer) {
        return true;
      }
    }

    if (userKey && Array.isArray(q.options)) {
      const idx = userKey.charCodeAt(0) - 'A'.charCodeAt(0);
      const mapped = q.options[idx];
      if (mapped && normalizeAnswer(mapped) === standardAnswer) {
        return true;
      }
    }
  }

  return userAnswer === standardAnswer;
};

export default function CourseMaterialsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { materials, removeMaterial, getMaterialsByType, setMaterials, pinMaterial } = useCourseMaterialsStore();
  const { removeGeneratedFile, pinGeneratedFile } = useStore();
  const [activeTab, setActiveTab] = useState<GeneratedFile['type']>('lesson_plan');
  const [viewModalVisible, setViewModalVisible] = useState(false);
  const [viewingMaterial, setViewingMaterial] = useState<GeneratedFile | null>(null);
  const [viewingPlan, setViewingPlan] = useState<LessonPlanResponse | null>(null);
  const [viewingReport, setViewingReport] = useState<ReportResponse | null>(null);
  const [viewingMarkdownReport, setViewingMarkdownReport] = useState<string | null>(null);
  const [viewingBlogContent, setViewingBlogContent] = useState<{ markdown: string; outline: any[] } | null>(null);
  const [viewingQuiz, setViewingQuiz] = useState<QuizResponse | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizChecked, setQuizChecked] = useState<Record<string, boolean>>({});
  const [loadingContent, setLoadingContent] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [pinning, setPinning] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 从后端加载课程资源（永久化存储）
  const loadMaterials = React.useCallback(async (showLoading = false) => {
    if (!courseId) return;
    
    if (showLoading) {
      setLoading(true);
    }
    
    try {
      const materials = await getCourseMaterials(courseId);
      // 转换为CourseMaterial格式
      const courseMaterials = materials.map((item): CourseMaterial => ({
        id: item.id,
        name: item.name,
        type: item.type as GeneratedFile['type'],
        content: item.content,
        addedAt: item.addedAt,
        courseId: item.courseId || courseId,
        isPinned: item.isPinned,
        pinnedAt: item.pinnedAt,
      }));
      setMaterials(courseMaterials);
      console.log(`[CourseMaterials] 已从后端加载 ${courseMaterials.length} 个资料`);
      if (showLoading) {
        message.success(`已加载 ${courseMaterials.length} 个资料`);
      }
    } catch (error: any) {
      console.error('加载课程资源失败:', error);
      if (showLoading) {
        message.error('加载课程资源失败');
      }
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [courseId, setMaterials]);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);
  
  // 当页面获得焦点时，重新加载数据（用户可能在其他页面生成了新内容）
  useEffect(() => {
    const handleFocus = () => {
      loadMaterials();
    };
    window.addEventListener('focus', handleFocus);
    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [loadMaterials]);

  const handleView = async (item: GeneratedFile) => {
    setViewingMaterial(item);
    setViewModalVisible(true);
    setLoadingContent(true);
    setViewingPlan(null);
    setViewingReport(null);
    setViewingMarkdownReport(null);
    setViewingBlogContent(null);
    setViewingQuiz(null);
    setQuizAnswers({});
    setQuizChecked({});
    
    try {
      if (item.type === 'lesson_plan' && item.id) {
        // 如果content已存在，直接使用；否则从后端加载
        if (item.content) {
          setViewingPlan(item.content as LessonPlanResponse);
        } else {
          const plan = await getLessonPlanDetail(item.id);
          setViewingPlan(plan);
        }
      } else if (item.type === 'report') {
        // 报告查看
        if (item.content) {
          if (typeof item.content === 'string') {
            setViewingMarkdownReport(item.content);
          } else if (typeof item.content?.report === 'string') {
            setViewingMarkdownReport(item.content.report);
          } else {
            setViewingReport(item.content as ReportResponse);
          }
        } else {
          // 如果后端有获取报告详情的API，可以在这里调用
          // 目前报告内容应该已经在content中
          message.warning('报告内容未找到');
        }
      } else if (item.type === 'blog') {
        // 教学博客查看
        if (item.content) {
          const blogContent = item.content as any;
          const markdown = typeof blogContent === 'string' 
            ? blogContent 
            : (blogContent?.markdown || '');
          const outline = Array.isArray(blogContent?.outline) ? blogContent.outline : [];
          setViewingBlogContent({ markdown, outline });
        } else {
          message.warning('博客内容未找到');
        }
      } else if (item.type === 'quiz') {
        if (item.content) {
          setViewingQuiz(item.content as QuizResponse);
        } else {
          message.warning('测验内容未找到');
        }
      } else if (item.type === 'ppt') {
        if (!item.content) {
          message.warning('PPT 内容未找到');
          setViewModalVisible(false);
        }
      } else {
        message.info('该类型的内容查看功能待实现');
        setViewModalVisible(false);
      }
    } catch (error: any) {
      message.error(`加载内容失败: ${error.message}`);
      setViewModalVisible(false);
    } finally {
      setLoadingContent(false);
    }
  };

  const handleDelete = async (id: string, type: GeneratedFile['type']) => {
    if (!courseId) {
      message.error('课程 ID 缺失');
      return;
    }
    setDeleting(id);
    try {
      if (type === 'lesson_plan') {
        await deleteCourseMaterial(courseId, type, id);
        removeMaterial(id);
        removeGeneratedFile(id);
        message.success('已删除');
      } else if (type === 'report') {
        await deleteCourseMaterial(courseId, type, id);
        removeMaterial(id);
        removeGeneratedFile(id);
        message.success('已删除');
      } else if (type === 'quiz') {
        await deleteCourseMaterial(courseId, type, id);
        removeMaterial(id);
        removeGeneratedFile(id);
        message.success('已删除');
      } else {
        // 其他类型暂时只从store删除
        await deleteCourseMaterial(courseId, type, id);
        removeMaterial(id);
        removeGeneratedFile(id);
        message.success('已删除');
      }
    } catch (error: any) {
      message.error(`删除失败: ${error.message}`);
    } finally {
      setDeleting(null);
    }
  };

  const handlePin = async (item: CourseMaterial) => {
    if (!courseId) {
      message.error('课程 ID 缺失');
      return;
    }
    const nextPinned = !item.isPinned;
    setPinning(item.id);
    try {
      const updated = await pinCourseMaterial(courseId, item.type, item.id, nextPinned);
      pinMaterial(item.id, nextPinned, updated.pinnedAt);
      pinGeneratedFile(item.id, nextPinned, updated.pinnedAt);
      await loadMaterials();
      message.success(nextPinned ? '已置顶' : '已取消置顶');
    } catch (error: any) {
      message.error(`置顶失败: ${error.message}`);
    } finally {
      setPinning(null);
    }
  };

  const currentMaterials = getMaterialsByType(activeTab);

  const tabItems = materialTypes.map(type => ({
    key: type.key,
    label: (
      <Space>
        <span style={{ color: type.color }}>{type.icon}</span>
        <span>{type.label}</span>
        <span style={{ color: '#999', fontSize: 12 }}>
          ({getMaterialsByType(type.key).length})
        </span>
      </Space>
    ),
  }));

  return (
    <div className="course-materials-page">
      <div className="course-materials-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={2} style={{ marginBottom: 8 }}>
              课程资料管理
            </Title>
            <Text type="secondary">
              管理从生成工厂保存下来的教学材料，按类型分类查看和管理
            </Text>
          </div>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => loadMaterials(true)}
            loading={loading}
            style={{ marginTop: 8 }}
          >
            刷新
          </Button>
        </div>
      </div>

      <Card className="course-materials-card">
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as GeneratedFile['type'])}
          items={tabItems}
        >
        </Tabs>

        <div style={{ marginTop: 24 }}>
          {currentMaterials.length === 0 ? (
            <Empty
              description={
                <Text type="secondary">
                  暂无{materialTypes.find(t => t.key === activeTab)?.label}资料
                </Text>
              }
            />
          ) : (
            <List
              dataSource={currentMaterials}
              renderItem={(item) => {
                const menuItems: MenuProps['items'] = [
                  {
                    key: 'view',
                    label: '查看',
                    icon: <EyeOutlined />,
                    onClick: () => {
                      handleView(item);
                    },
                  },
                  {
                    key: 'pin',
                    label: pinning === item.id ? '处理中...' : item.isPinned ? '取消置顶' : '置顶',
                    icon: pinning === item.id ? <Spin size="small" /> : <PushpinOutlined />,
                    disabled: pinning === item.id,
                    onClick: () => {
                      handlePin(item);
                    },
                  },
                  {
                    key: 'delete',
                    label: deleting === item.id ? '删除中...' : '删除',
                    icon: deleting === item.id ? <Spin size="small" /> : <DeleteOutlined />,
                    danger: true,
                    disabled: deleting === item.id,
                    onClick: () => {
                      handleDelete(item.id, item.type);
                    },
                  },
                ];

                return (
                  <List.Item
                    style={{
                      padding: '12px 0',
                      borderBottom: '1px solid #f0f0f0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                      <div style={{ marginRight: 12 }}>
                        {getFileIcon(item.type)}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Text strong style={{ display: 'block', marginBottom: 4 }}>
                          {item.name}
                          {item.isPinned ? (
                            <PushpinOutlined style={{ marginLeft: 8, color: '#fa8c16' }} />
                          ) : null}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          添加时间：{new Date(item.addedAt).toLocaleString('zh-CN')}
                        </Text>
                      </div>
                      <Space>
                        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                          <Button
                            type="text"
                            icon={<MoreOutlined />}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Dropdown>
                      </Space>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
        </div>
      </Card>

      {/* 查看教案/报告/博客的Modal */}
      <Modal
        title={viewingPlan?.title || viewingReport?.title || viewingQuiz?.title || viewingMaterial?.name || '内容详情'}
        open={viewModalVisible}
        onCancel={() => {
          setViewModalVisible(false);
          setViewingPlan(null);
          setViewingReport(null);
          setViewingMarkdownReport(null);
          setViewingMaterial(null);
          setViewingBlogContent(null);
          setViewingQuiz(null);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setViewModalVisible(false);
            setViewingPlan(null);
            setViewingReport(null);
            setViewingMarkdownReport(null);
            setViewingMaterial(null);
            setViewingBlogContent(null);
            setViewingQuiz(null);
          }}>
            关闭
          </Button>,
        ]}
        width={800}
        style={{ top: 20 }}
        bodyStyle={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}
      >
        {loadingContent ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
          </div>
        ) : viewingMaterial?.type === 'ppt' ? (
          (() => {
            const pptContent = (viewingMaterial.content || {}) as Record<string, any>;
            const pptPreviewUrl = String(resolvePptAssetUrl(pptContent.html_full_url || pptContent.html_url) || '').trim();
            const pptExportUrl = String(resolvePptAssetUrl(pptContent.pptx_url) || '').trim();
            const pptManifestUrl = String(resolvePptAssetUrl(pptContent.manifest_url) || '').trim();

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                  {pptManifestUrl ? (
                    <Button onClick={() => window.open(pptManifestUrl, '_blank', 'noopener,noreferrer')}>
                      查看结构
                    </Button>
                  ) : null}
                  {pptExportUrl ? (
                    <Button
                      type="primary"
                      icon={<FilePptOutlined />}
                      onClick={() => window.open(pptExportUrl, '_blank', 'noopener,noreferrer')}
                    >
                      导出 PPT
                    </Button>
                  ) : null}
                </Space>
                {pptPreviewUrl ? (
                  <div style={{ height: 'calc(100vh - 320px)', minHeight: 420, border: '1px solid #f0f0f0', borderRadius: 12, overflow: 'hidden' }}>
                    <iframe
                      src={pptPreviewUrl}
                      title={viewingMaterial.name}
                      style={{ width: '100%', height: '100%', border: 0, background: '#fff' }}
                    />
                  </div>
                ) : (
                  <Empty description={<Text type="secondary">当前 PPT 暂无可预览内容</Text>} />
                )}
              </div>
            );
          })()
        ) : viewingReport ? (
          <div>
            {/* 执行摘要 */}
            {viewingReport.summary && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>📋 执行摘要</Title>
                <Paragraph
                  style={{
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.8,
                    fontSize: 14,
                    color: '#595959',
                  }}
                >
                  {viewingReport.summary}
                </Paragraph>
              </div>
            )}

            {/* 引言 */}
            {viewingReport.introduction && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#722ed1', marginBottom: 12 }}>📖 引言</Title>
                <Paragraph
                  style={{
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.8,
                    fontSize: 14,
                    color: '#595959',
                  }}
                >
                  {viewingReport.introduction}
                </Paragraph>
              </div>
            )}

            {/* 主要内容 */}
            {viewingReport.mainContent && viewingReport.mainContent.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>📚 主要内容</Title>
                {viewingReport.mainContent.map((section, idx) => (
                  <div
                    key={idx}
                    style={{
                      marginBottom: 20,
                      padding: 16,
                      background: idx % 2 === 0 ? '#fafafa' : '#ffffff',
                      borderRadius: 8,
                      border: '1px solid #e8e8e8',
                    }}
                  >
                    <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>
                      {idx + 1}. {section.title}
                    </Title>
                    <Paragraph
                      style={{
                        margin: 0,
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.8,
                        fontSize: 14,
                        color: '#595959',
                        marginBottom: section.subsections && section.subsections.length > 0 ? 16 : 0,
                      }}
                    >
                      {section.content}
                    </Paragraph>
                    {section.subsections && section.subsections.length > 0 && (
                      <div style={{ marginTop: 16, paddingLeft: 16 }}>
                        {section.subsections.map((subsection, subIdx) => (
                          <div key={subIdx} style={{ marginBottom: 12 }}>
                            <Text strong style={{ fontSize: 14, color: '#722ed1' }}>
                              {idx + 1}.{subIdx + 1} {subsection.title}
                            </Text>
                            <Paragraph
                              style={{
                                margin: '8px 0 0 0',
                                whiteSpace: 'pre-wrap',
                                lineHeight: 1.8,
                                fontSize: 13,
                                color: '#595959',
                              }}
                            >
                              {subsection.content}
                            </Paragraph>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 关键发现 */}
            {viewingReport.keyFindings && viewingReport.keyFindings.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#fa8c16', marginBottom: 12 }}>⭐ 关键发现</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {viewingReport.keyFindings.map((finding, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {finding}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 结论 */}
            {viewingReport.conclusions && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#ff4d4f', marginBottom: 12 }}>📝 结论</Title>
                <div
                  style={{
                    padding: 16,
                    background: '#fff1f0',
                    borderRadius: 8,
                    border: '1px solid #ffccc7',
                  }}
                >
                  <Paragraph
                    style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.8,
                      fontSize: 14,
                      color: '#595959',
                    }}
                  >
                    {viewingReport.conclusions}
                  </Paragraph>
                </div>
              </div>
            )}

            {/* 建议 */}
            {viewingReport.recommendations && viewingReport.recommendations.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>💡 建议</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {viewingReport.recommendations.map((rec, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : viewingMarkdownReport ? (
          <div
            style={{
              padding: 16,
              borderRadius: 8,
              border: '1px solid #f0f0f0',
              background: '#fcfcfc',
            }}
          >
            <MarkdownPreview content={viewingMarkdownReport} />
          </div>
        ) : viewingQuiz ? (
          <div>
            {(() => {
              const questions = Array.isArray(viewingQuiz.questions) ? viewingQuiz.questions : [];
              const total = questions.length;
              const checkedCount = questions.filter((q) => !!quizChecked[q.id]).length;
              const correctCount = questions.filter((q) => {
                if (!quizChecked[q.id]) return false;
                return isQuizAnswerCorrect(q, quizAnswers[q.id] || '');
              }).length;
              const accuracy = checkedCount > 0 ? Math.round((correctCount / checkedCount) * 100) : 0;

              return (
                <>
                  <Card size="small" style={{ marginBottom: 12, background: '#fafafa', border: '1px solid #f0f0f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                      <Space split={<Divider type="vertical" />}>
                        <Text>总题数：<Text strong>{total}</Text></Text>
                        <Text>已判题：<Text strong>{checkedCount}</Text></Text>
                        <Text>答对：<Text strong style={{ color: '#52c41a' }}>{correctCount}</Text></Text>
                        <Text>正确率：<Text strong>{accuracy}%</Text></Text>
                      </Space>
                      <Space>
                        <Button
                          size="small"
                          onClick={() => {
                            const nextChecked: Record<string, boolean> = {};
                            questions.forEach((q) => {
                              if ((quizAnswers[q.id] || '').trim()) {
                                nextChecked[q.id] = true;
                              }
                            });
                            setQuizChecked(nextChecked);
                          }}
                        >
                          一键查看答案
                        </Button>
                        <Button
                          size="small"
                          onClick={() => {
                            setQuizAnswers({});
                            setQuizChecked({});
                          }}
                        >
                          重做本测验
                        </Button>
                      </Space>
                    </div>
                  </Card>

                  {questions.length > 0 ? (
                    questions.map((q, idx) => {
                      const userAnswer = quizAnswers[q.id] || '';
                      const checked = !!quizChecked[q.id];
                      const isCorrect = checked && isQuizAnswerCorrect(q, userAnswer);

                      return (
                        <Card key={q.id || idx} size="small" style={{ marginBottom: 12 }}>
                          <div style={{ marginBottom: 8 }}>
                            <Text strong>{idx + 1}. {q.stem}</Text>
                          </div>

                          {q.type === 'choice' && Array.isArray(q.options) ? (
                            <Radio.Group
                              value={userAnswer || undefined}
                              onChange={(e) => {
                                setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }));
                                setQuizChecked((prev) => ({ ...prev, [q.id]: false }));
                              }}
                            >
                              <Space direction="vertical">
                                {q.options.map((opt, optIdx) => (
                                  <Radio key={`${q.id}_${optIdx}`} value={opt}>{opt}</Radio>
                                ))}
                              </Space>
                            </Radio.Group>
                          ) : (
                            <Input
                              value={userAnswer}
                              placeholder="请输入答案"
                              onChange={(e) => {
                                setQuizAnswers((prev) => ({ ...prev, [q.id]: e.target.value }));
                                setQuizChecked((prev) => ({ ...prev, [q.id]: false }));
                              }}
                            />
                          )}

                          <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
                            <Button
                              size="small"
                              type="primary"
                              onClick={() => {
                                if (!quizAnswers[q.id] || !quizAnswers[q.id].trim()) {
                                  message.warning('请先作答后再判题');
                                  return;
                                }
                                setQuizChecked((prev) => ({ ...prev, [q.id]: true }));
                              }}
                            >
                              提交并判题
                            </Button>

                            {checked && (
                              <Text style={{ color: isCorrect ? '#52c41a' : '#ff4d4f' }}>
                                {isCorrect ? '回答正确' : '回答错误'}
                              </Text>
                            )}
                          </div>

                          {checked && (
                            <div style={{ marginTop: 10, padding: 10, borderRadius: 8, background: '#fafafa', border: '1px solid #f0f0f0' }}>
                              <div><Text strong>正确答案：</Text><Text>{q.answer || '-'}</Text></div>
                              <div style={{ marginTop: 6 }}><Text strong>解析：</Text><Text>{q.explanation || '暂无解析'}</Text></div>
                            </div>
                          )}
                        </Card>
                      );
                    })
                  ) : (
                    <Empty description="暂无题目" />
                  )}
                </>
              );
            })()}
          </div>
        ) : viewingPlan ? (
          <div>
            {/* 教学目标 */}
            {viewingPlan.objectives && viewingPlan.objectives.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>📚 教学目标</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {viewingPlan.objectives.map((obj, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {obj}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 教学重点 */}
            {viewingPlan.keyPoints && viewingPlan.keyPoints.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>⭐ 教学重点</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {viewingPlan.keyPoints.map((kp, idx) => (
                    <span
                      key={idx}
                      style={{
                        padding: '4px 12px',
                        background: '#f6ffed',
                        border: '1px solid #b7eb8f',
                        borderRadius: 4,
                        fontSize: 13,
                        color: '#389e0d',
                      }}
                    >
                      {kp}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 教学难点 */}
            {viewingPlan.hardPoints && viewingPlan.hardPoints.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#ff4d4f', marginBottom: 12 }}>⚠️ 教学难点</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {viewingPlan.hardPoints.map((hp, idx) => (
                    <span
                      key={idx}
                      style={{
                        padding: '4px 12px',
                        background: '#fff1f0',
                        border: '1px solid #ffccc7',
                        borderRadius: 4,
                        fontSize: 13,
                        color: '#cf1322',
                      }}
                    >
                      {hp}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 教学过程 */}
            {viewingPlan.process && viewingPlan.process.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#722ed1', marginBottom: 12 }}>📖 教学过程</Title>
                {viewingPlan.process.map((step, idx) => (
                  <div
                    key={idx}
                    style={{
                      marginBottom: 16,
                      padding: 16,
                      background: idx % 2 === 0 ? '#fafafa' : '#ffffff',
                      borderRadius: 8,
                      border: '1px solid #e8e8e8',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <Text strong style={{ fontSize: 16, color: '#722ed1' }}>
                        {idx + 1}. {step.step}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ⏱️ {step.duration}
                      </Text>
                    </div>
                    <Paragraph
                      style={{
                        margin: 0,
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.8,
                        fontSize: 14,
                        color: '#595959',
                      }}
                    >
                      {step.content}
                    </Paragraph>
                  </div>
                ))}
              </div>
            )}

            {/* 作业布置 */}
            {viewingPlan.homework && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#fa8c16', marginBottom: 12 }}>📝 作业布置</Title>
                <div
                  style={{
                    padding: 16,
                    background: '#fff7e6',
                    borderRadius: 8,
                    border: '1px solid #ffd591',
                  }}
                >
                  <Paragraph
                    style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.8,
                      fontSize: 14,
                      color: '#595959',
                    }}
                  >
                    {viewingPlan.homework}
                  </Paragraph>
                </div>
              </div>
            )}
          </div>
        ) : viewingBlogContent ? (
          <div>
            {/* 博客大纲 */}
            {viewingBlogContent.outline && viewingBlogContent.outline.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>📋 博客大纲</Title>
                <div style={{ 
                  padding: 12, 
                  background: '#fafafa', 
                  borderRadius: 8, 
                  border: '1px solid #f0f0f0' 
                }}>
                  {viewingBlogContent.outline.map((sec: any, idx: number) => (
                    <div key={sec?.id || idx} style={{ marginBottom: 8 }}>
                      <Text strong style={{ fontSize: 14, color: '#1890ff' }}>
                        {idx + 1}. {sec?.title || '未命名章节'}
                      </Text>
                      {sec?.children && Array.isArray(sec.children) && sec.children.length > 0 && (
                        <div style={{ marginTop: 6, paddingLeft: 16 }}>
                          {sec.children.map((child: any, childIdx: number) => (
                            <div key={child?.id || childIdx} style={{ marginBottom: 4 }}>
                              <Text style={{ fontSize: 13, color: '#595959' }}>
                                {idx + 1}.{childIdx + 1} {child?.title || '未命名小标题'}
                              </Text>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Divider />

            {/* 博客正文（Markdown） */}
            <div style={{ marginBottom: 24 }}>
              <Title level={5} style={{ color: '#722ed1', marginBottom: 12 }}>📝 正文内容</Title>
              <div
                style={{
                  padding: 16,
                  borderRadius: 8,
                  border: '1px solid #f0f0f0',
                  background: '#fcfcfc',
                  fontSize: 14,
                  lineHeight: 1.7,
                }}
              >
                {viewingBlogContent.markdown ? (
                  <MarkdownPreview content={viewingBlogContent.markdown} />
                ) : (
                  <Text type="secondary">（暂无内容）</Text>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

