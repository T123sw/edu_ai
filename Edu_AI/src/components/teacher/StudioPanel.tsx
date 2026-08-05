import React, { useState, useEffect, useRef } from 'react';
import { Button, Divider, Dropdown, Space, Tooltip, Typography, Modal, Form, Input, Select, message, notification, Progress, Spin, Card, InputNumber, Radio, Switch } from 'antd';
import type { MenuProps } from 'antd';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileMarkdownOutlined,
  FileTextOutlined,
  LeftOutlined,
  MoreOutlined,
  QuestionCircleOutlined,
  RightOutlined,
  AudioOutlined,
  BookOutlined,
  MessageOutlined,
  EditOutlined,
  PlayCircleOutlined,
  VideoCameraOutlined,
  FilePdfOutlined,
  TableOutlined,
  FilePptOutlined,
  InfoCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import type { GeneratedFile } from '../../store/teacher/useStore';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';
import {
  getCourseMaterials,
  getCourseMaterialsPage,
  resumeBlogTaskChapters,
  resumeBlogTaskOutline,
  startBlogGenerate,
  getBlogTaskStatus,
  generateQuiz,
  type BlogResumeChaptersRequest,
  type BlogResumeOutlineRequest,
  type BlogTaskStatusResponse,
  type QuizRequest,
  type QuizResponse,
  type ReportResponse,
} from '../../services/teacher/api';
import {
  type DirectQuizConfigV2,
  sendChatReplyV2,
  sendReportV2,
  generateKnowledgeBaseGameV2,
  type GameTypeV2,
  type LessonPlanEntryCard,
  generateKnowledgeBaseQuizV2,
  generateKnowledgeBaseReportV2,
  pollChatTask,
} from '../../services/teacher/chatV2';
import { extractGeneratedFilesFromV2Response } from '../../services/teacher/chatV2.helpers';
import { buildKnowledgeBaseQuizRequest } from '../../services/teacher/quizEntry.helpers';
import { buildKnowledgeBaseReportRequest } from '../../services/teacher/reportEntry.helpers';
import { buildKnowledgeBaseLessonPlanReplyRequest, type LessonPlanEntryConfigInput } from '../../services/teacher/lessonPlanEntry.helpers';
import type { ReportEntryCard } from '../../services/teacher/chatV2';
import { isArtifactReferenceEligible, toGeneratedFileFromCourseMaterial } from '../../services/teacher/materials.helpers';
import { resolvePptAssetUrl } from '../../services/teacher/pptAssets';
import {
  getWorkspaceScopeApiParams,
  normalizeWorkspaceScope,
  type WorkspaceScope,
} from '../../services/teacher/workspaceScope';
import GameArtifactPreview from './GameArtifactPreview';
import GameEntryModal from './GameEntryModal';
import { ClassroomGenerationEntry } from './ClassroomGenerationEntry';
import LessonPlanEntryModal from './LessonPlanEntryModal';
import LessonPlanArtifactPreview from './LessonPlanArtifactPreview';
import QuizArtifactPreview from './QuizArtifactPreview';
import QuizEntryModal from './QuizEntryModal';
import ReportEntryModal from './ReportEntryModal';
import ReportArtifactPreview from './ReportArtifactPreview';
import {
  TEACHER_STUDIO_ACTIONS,
  TEACHER_STUDIO_ACTION_ORDER,
  type TeacherStudioActionType,
} from './studioActions';

import MarkdownPreview from '../shared/MarkdownPreview';
import './StudioPanel.css';

const { Title, Text, Paragraph } = Typography;
const PPT_PREVIEW_BASE_WIDTH = 1920;
const HIDDEN_RECENT_ARTIFACT_NAMES = [
  '变量本质、动态特性及其教学价值分析报告.md',
  '编程基础：变量的概念、命名与赋值操作-quiz.json',
] as const;

const getGeneratedFileAddedAtTimestamp = (file: GeneratedFile): number => {
  const rawAddedAt = typeof file.meta?.addedAt === 'string' ? file.meta.addedAt : '';
  const parsed = Date.parse(rawAddedAt);
  return Number.isFinite(parsed) ? parsed : 0;
};

const getHiddenRecentArtifactIds = (files: GeneratedFile[]): string[] =>
  HIDDEN_RECENT_ARTIFACT_NAMES.map((targetName) => {
    const latestMatch = files
      .filter((file) => String(file.name || '').trim() === targetName)
      .sort((left, right) => getGeneratedFileAddedAtTimestamp(right) - getGeneratedFileAddedAtTimestamp(left))[0];
    return latestMatch?.id || '';
  }).filter(Boolean);

const getBlogStatusLabel = (status?: string) => {
  switch (status) {
    case 'planning':
      return { text: '规划中', color: '#1890ff' };
    case 'executing':
      return { text: '生成中', color: '#fa8c16' };
    case 'assembling':
      return { text: '组装中', color: '#722ed1' };
    case 'completed':
      return { text: '已完成', color: '#52c41a' };
    case 'failed':
      return { text: '失败', color: '#ff4d4f' };
    default:
      return { text: status || '未知', color: '#8c8c8c' };
  }
};

const getPptPhaseLabel = (phase?: string) => {
  switch (String(phase || '').trim()) {
    case 'preprocessing':
      return '正在准备生成任务';
    case 'generating_slides':
      return '正在生成幻灯片';
    case 'exporting_pptx':
      return '正在导出 PPT';
    case 'completed':
      return 'PPT 已生成完成';
    case 'failed':
      return '生成失败';
    default:
      return String(phase || '').trim() || '处理中';
  }
};

const getPptStatusText = (status?: string, phase?: string, message?: string) => {
  const normalizedStatus = String(status || '').trim();
  const normalizedMessage = String(message || '').trim();
  if (normalizedStatus === 'running') {
    return getPptPhaseLabel(phase);
  }
  if (normalizedStatus === 'failed') {
    return '生成失败';
  }
  if (normalizedStatus === 'completed') {
    return 'PPT 已生成完成';
  }
  return normalizedMessage || getPptPhaseLabel(phase);
};

const calcProgressPercent = (current: number, total: number) => {
  if (!total || total <= 0) return 0;
  const v = Math.floor((Math.max(0, current) / total) * 100);
  return Math.max(0, Math.min(100, v));
};

const toTextList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || '').trim()).filter(Boolean);
  }
  const text = String(value || '').trim();
  return text ? [text] : [];
};

const normalizeLessonPlanPreview = (content: unknown, kind?: string) => {
  const record = content && typeof content === 'object' ? (content as Record<string, any>) : {};
  const outlineBasicInfo =
    record.basic_info && typeof record.basic_info === 'object' ? (record.basic_info as Record<string, any>) : {};
  const outlineKeyAndHard =
    record.key_and_hard_points && typeof record.key_and_hard_points === 'object'
      ? (record.key_and_hard_points as Record<string, any>)
      : {};
  const outlineSupport =
    record.teaching_support && typeof record.teaching_support === 'object'
      ? (record.teaching_support as Record<string, any>)
      : {};
  const isOutline =
    String(kind || '').trim() === 'outline-solid'
    || Boolean(record.basic_info)
    || Boolean(record.lesson_flow)
    || Boolean(record.teaching_objectives);

  const outlineProcess = Array.isArray(record.lesson_flow)
    ? record.lesson_flow
        .map((item: any) => {
          const goal = String(item?.goal || '').trim();
          const teacherActivities = toTextList(item?.teacher_activities);
          const studentActivities = toTextList(item?.student_activities);
          const assessment = String(item?.assessment || '').trim();
          return {
            step: String(item?.step || '').trim(),
            duration: String(item?.duration || '').trim(),
            content: [
              goal ? `目标：${goal}` : '',
              teacherActivities.length > 0 ? `教师活动：${teacherActivities.join('；')}` : '',
              studentActivities.length > 0 ? `学生活动：${studentActivities.join('；')}` : '',
              assessment ? `评价方式：${assessment}` : '',
            ]
              .filter(Boolean)
              .join('\n'),
          };
        })
        .filter((item) => item.step || item.content)
    : [];

  const finalProcess = Array.isArray(record.process)
    ? record.process
        .map((item: any) => {
          const goal = String(item?.goal || '').trim();
          const teacherActivities = toTextList(item?.teacherActivities);
          const studentActivities = toTextList(item?.studentActivities);
          const assessment = String(item?.assessment || '').trim();
          const content = String(item?.content || '').trim();
          return {
            step: String(item?.step || '').trim(),
            duration: String(item?.duration || '').trim(),
            content:
              content
              || [
                goal ? `目标：${goal}` : '',
                teacherActivities.length > 0 ? `教师活动：${teacherActivities.join('；')}` : '',
                studentActivities.length > 0 ? `学生活动：${studentActivities.join('；')}` : '',
                assessment ? `评价方式：${assessment}` : '',
              ]
                  .filter(Boolean)
                  .join('\n'),
          };
        })
        .filter((item) => item.step || item.content)
    : [];

  return {
    isOutline,
    title: String(record.title || outlineBasicInfo.topic || '').trim(),
    basicInfo: {
      audience: String(outlineBasicInfo.audience || '').trim(),
      duration: String(outlineBasicInfo.duration || '').trim(),
      lessonType: String(outlineBasicInfo.lesson_type || '').trim(),
    },
    objectives: isOutline ? toTextList(record.teaching_objectives) : toTextList(record.objectives),
    keyPoints: isOutline ? toTextList(outlineKeyAndHard.key_points) : toTextList(record.keyPoints),
    hardPoints: isOutline ? toTextList(outlineKeyAndHard.hard_points) : toTextList(record.hardPoints),
    process: isOutline ? outlineProcess : finalProcess,
    homework: isOutline ? String(outlineSupport.homework_preview || '').trim() : String(record.homework || '').trim(),
    teachingMethods: toTextList(outlineSupport.teaching_methods),
    teachingAids: toTextList(outlineSupport.teaching_aids),
    boardPlan: toTextList(outlineSupport.board_plan),
    assessmentMethod: String(outlineSupport.assessment_method || '').trim(),
    breakthroughStrategy: String(outlineKeyAndHard.breakthrough_strategy || '').trim(),
  };
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
  const questionType = String((q as any).type || '').trim();

  if (questionType === 'judge') {
    const truthyAnswers = new Set(['正确', '对', 'true', 'yes', '是']);
    const falsyAnswers = new Set(['错误', '错', 'false', 'no', '否']);
    if (truthyAnswers.has(userAnswerRaw.trim()) && truthyAnswers.has(String(q.answer || '').trim())) {
      return true;
    }
    if (falsyAnswers.has(userAnswerRaw.trim()) && falsyAnswers.has(String(q.answer || '').trim())) {
      return true;
    }
  }

  if (questionType === 'choice') {
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

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onPreviewStateChange?: (open: boolean) => void;
};

const getGeneratedFileIcon = (file: GeneratedFile, size = 20) => {
  switch (file.type) {
    case 'report':
      return <FileMarkdownOutlined style={{ fontSize: size, color: '#555' }} />;
    case 'ppt':
      return <FilePptOutlined style={{ fontSize: size, color: '#d46b08' }} />;
    case 'quiz':
      return <QuestionCircleOutlined style={{ fontSize: size, color: '#f7b731' }} />;
    case 'blog':
      return <FileTextOutlined style={{ fontSize: size, color: '#1890ff' }} />;
    case 'lesson_plan':
      return <BookOutlined style={{ fontSize: size, color: '#52c41a' }} />;
    case 'audio':
      return <AudioOutlined style={{ fontSize: size, color: '#722ed1' }} />;
    case 'video':
      return <VideoCameraOutlined style={{ fontSize: size, color: '#52c41a' }} />;
    case 'graph':
      return <ApartmentOutlined style={{ fontSize: size, color: '#4caf50' }} />;
    case 'flashcard':
      return <BookOutlined style={{ fontSize: size, color: '#ff7875' }} />;
    default:
      return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
  }
};

// 生成功能卡片组件
interface GenerativeCardProps {
  icon: React.ReactNode;
  title: string;
  description?: string;
  color: string;
  onGenerate: () => void;
  onConfigure: () => void;
  featured?: boolean;
}

const GenerativeCard: React.FC<GenerativeCardProps> = ({
  icon,
  title,
  description = '',
  color,
  onGenerate,
  onConfigure,
  featured = false,
}) => {
  const accentStyles = {
    ['--studio-accent' as string]: color,
    ['--studio-accent-soft' as string]: `${color}16`,
    ['--studio-accent-border' as string]: `${color}28`,
  } as React.CSSProperties;

  return (
    <div
      className={`studio-panel__action-card${featured ? ' studio-panel__action-card--featured' : ''}`}
      style={accentStyles}
      role="button"
      tabIndex={0}
      aria-label={`${title}：${description}`}
      onClick={onGenerate}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onGenerate();
        }
      }}
    >
      <div className="studio-panel__action-card-head">
        <div className="studio-panel__action-icon">
          {icon}
        </div>
        <div className="studio-panel__action-copy">
          <div className="studio-panel__action-title">{title}</div>
          <div className="studio-panel__action-description">{description}</div>
        </div>
      </div>
      <div className="studio-panel__action-footer">
        <Button
          className="studio-panel__action-generate"
          type="text"
          onClick={(e) => {
            e.stopPropagation();
            onGenerate();
          }}
        >
          开始生成
        </Button>
        <Button
          className="studio-panel__action-configure"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onConfigure();
          }}
        />
      </div>
    </div>
  );
};

const STUDIO_ACTION_ICONS: Record<TeacherStudioActionType, React.ReactNode> = {
  report: <FileTextOutlined />,
  lesson_plan: <BookOutlined />,
  blog: <EditOutlined />,
  quiz: <QuestionCircleOutlined />,
  ppt: <FilePptOutlined />,
  flashcard: <BookOutlined />,
  graph: <ApartmentOutlined />,
  game: <PlayCircleOutlined />,
};

const STUDIO_ACTIONS = TEACHER_STUDIO_ACTIONS.map((action) => ({
  ...action,
  icon: STUDIO_ACTION_ICONS[action.type],
}));

const STUDIO_ACTION_DISPLAY_ORDER = [...TEACHER_STUDIO_ACTION_ORDER];

const COURSE_MATERIAL_PAGE_SIZE = 20;

type DirectBgTask = {
  taskId: string;
  workflowType: string;
  description: string;
  originMeta: Record<string, string>;
  courseId?: string | null;
};

const StudioPanel: React.FC<Props> = ({
  collapsed,
  onToggleCollapsed,
  courseId,
  workspaceScope,
  onPreviewStateChange,
}) => {
  const {
    generatedFiles,
    viewingFile,
    addGeneratedFile,
    replaceCourseMaterialGeneratedFiles,
    removeGeneratedFile,
    setViewingFile,
    selectedDocs,
    currentConversationId,
    setCurrentConversationId,
    setMessages,
    setArtifactReference,
    clearArtifactReference,
    clearConversationReference,
    allowRag,
    allowWeb,
    setAllowRag,
    setAllowWeb,
    setStatusCard,
    setQueuedMessage,
  } = useStore();
  const { addMaterial } = useCourseMaterialsStore();
  const [configModalVisible, setConfigModalVisible] = useState(false);
  const [configType, setConfigType] = useState<string>('');

  const [blogTaskId, setBlogTaskId] = useState<string | null>(null);
  const [blogTaskStatus, setBlogTaskStatus] = useState<BlogTaskStatusResponse | null>(null);
  const [blogPolling, setBlogPolling] = useState(false);

  const [blogReviewModalVisible, setBlogReviewModalVisible] = useState(false);
  const [blogOutlineDraftText, setBlogOutlineDraftText] = useState<string>('');
  const [blogOutlineOriginalText, setBlogOutlineOriginalText] = useState<string>('');
  const [blogResuming, setBlogResuming] = useState(false);
  const [courseMaterialsTotal, setCourseMaterialsTotal] = useState(0);
  const [courseMaterialsLoadingMore, setCourseMaterialsLoadingMore] = useState(false);
  const normalizedWorkspaceScope = React.useMemo(() => normalizeWorkspaceScope(workspaceScope), [workspaceScope]);
  const workspaceScopeApiParams = React.useMemo(
    () => getWorkspaceScopeApiParams(normalizedWorkspaceScope),
    [normalizedWorkspaceScope],
  );

  const [blogOutlineForm] = Form.useForm();
  const syncCourseMaterialsIntoStores = React.useCallback((
    materials: Array<{
      id: string;
      name: string;
      type: GeneratedFile['type'];
      content: unknown;
      addedAt: string;
      courseId?: string;
      isPinned?: boolean;
      pinnedAt?: string;
    }>,
  ) => {
    useCourseMaterialsStore.getState().setMaterials(materials as any);
    const syncedGeneratedFiles = materials
      .map((item) => toGeneratedFileFromCourseMaterial(item))
      .filter((item): item is GeneratedFile => item !== null);
    replaceCourseMaterialGeneratedFiles(syncedGeneratedFiles);
  }, [replaceCourseMaterialGeneratedFiles]);

  const refreshCourseMaterials = React.useCallback(async (options?: { append?: boolean }) => {
    if (!courseId) {
      return;
    }

    const append = Boolean(options?.append);
    const offset = append ? useCourseMaterialsStore.getState().materials.length : 0;
    const page = await getCourseMaterialsPage(courseId, {
      scopeType: workspaceScopeApiParams.scopeType,
      scopeId: workspaceScopeApiParams.scopeId,
      aggregate: workspaceScopeApiParams.aggregate,
      limit: COURSE_MATERIAL_PAGE_SIZE,
      offset,
    });

    setCourseMaterialsTotal(page.total);
    const nextPageItems = page.items.map((item) => ({
      id: item.id,
      name: item.name,
      type: item.type as GeneratedFile['type'],
      content: item.content,
      addedAt: item.addedAt,
      courseId: item.courseId || courseId,
      scopeType: item.scopeType,
      scopeId: item.scopeId,
      isPinned: item.isPinned,
      pinnedAt: item.pinnedAt,
    }));

    if (!append) {
      syncCourseMaterialsIntoStores(nextPageItems);
      return;
    }

    const currentMaterials = useCourseMaterialsStore.getState().materials;
    const seen = new Set(currentMaterials.map((item) => item.id));
    syncCourseMaterialsIntoStores([
      ...currentMaterials,
      ...nextPageItems.filter((item) => !seen.has(item.id)),
    ]);
  }, [courseId, syncCourseMaterialsIntoStores, workspaceScopeApiParams.aggregate, workspaceScopeApiParams.scopeId, workspaceScopeApiParams.scopeType]);

  useEffect(() => {
    if (!courseId) {
      return;
    }
    void refreshCourseMaterials();
  }, [courseId, refreshCourseMaterials, workspaceScopeApiParams.aggregate, workspaceScopeApiParams.scopeId, workspaceScopeApiParams.scopeType]);

  const handleLoadMoreCourseMaterials = async () => {
    if (courseMaterialsLoadingMore || generatedFiles.filter((file) => String(file.meta?.origin || '').trim() === 'course_material').length >= courseMaterialsTotal) {
      return;
    }
    setCourseMaterialsLoadingMore(true);
    try {
      await refreshCourseMaterials({ append: true });
    } catch (error) {
      console.error('load more course materials failed:', error);
      message.error('加载更多生成物失败');
    } finally {
      setCourseMaterialsLoadingMore(false);
    }
  };

  // 监听 viewingFile 变化，通知父组件预览状态
  useEffect(() => {
    if (onPreviewStateChange) {
      onPreviewStateChange(viewingFile !== null);
    }
  }, [viewingFile, onPreviewStateChange]);

  // 轮询博客生成状态
  useEffect(() => {
    if (!blogPolling || !blogTaskId) return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await getBlogTaskStatus(blogTaskId);
        setBlogTaskStatus(status);

        if (status.status === 'waiting_for_chapter_review') {
          setBlogPolling(false);
          setBlogReviewModalVisible(true);
          try {
            const outlineArr = Array.isArray(status.outline) ? status.outline : [];
            const chaptersOnly = outlineArr.map((sec: any) => ({
              id: sec?.id,
              title: sec?.title,
              estimated_word_count: sec?.estimated_word_count,
            }));
            const text = JSON.stringify(chaptersOnly, null, 2);
            setBlogOutlineDraftText(text);
            setBlogOutlineOriginalText(text);
            blogOutlineForm.setFieldsValue({ outline: chaptersOnly });
          } catch {
            setBlogOutlineDraftText('[]');
            setBlogOutlineOriginalText('[]');
            blogOutlineForm.setFieldsValue({ outline: [] });
          }
          return;
        }

        if (status.status === 'waiting_for_outline_review') {
          setBlogPolling(false);
          setBlogReviewModalVisible(true);
          try {
            const outlineArr = Array.isArray(status.outline) ? status.outline : [];
            const text = JSON.stringify(outlineArr, null, 2);
            setBlogOutlineDraftText(text);
            setBlogOutlineOriginalText(text);
            blogOutlineForm.setFieldsValue({ outline: outlineArr });
          } catch {
            setBlogOutlineDraftText('[]');
            setBlogOutlineOriginalText('[]');
            blogOutlineForm.setFieldsValue({ outline: [] });
          }
          return;
        }

        if (status.status === 'completed' || status.status === 'failed') {
          setBlogPolling(false);
          
          if (status.status === 'completed' && status.final_markdown) {
            const newFile: GeneratedFile = {
              id: blogTaskId,
              name: `教学博客-${new Date().toLocaleDateString()}`,
              type: 'blog',
              content: {
                markdown: status.final_markdown,
                outline: status.outline || [],
              },
            };
            
            addGeneratedFile(newFile);
            setViewingFile(newFile);
            
            if (courseId) {
              const material = {
                ...newFile,
                addedAt: new Date().toISOString(),
                courseId: courseId,
              };
              addMaterial(material);

              // 从后端刷新课程资源，确保“教学资源”页面立刻可见且持久化一致
              try {
                await refreshCourseMaterials();
              } catch (e) {
                console.warn('[StudioPanel] 刷新课程资源失败:', e);
              }
            }
            
            message.success('教学博客生成完成！');
          } else if (status.status === 'failed') {
            message.error(`生成失败: ${status.error_message || '未知错误'}`);
          }
        }
      } catch (error) {
        console.error('轮询博客状态失败:', error);
        setBlogPolling(false);
      }
    }, 1500);

    return () => clearInterval(pollInterval);
  }, [blogPolling, blogTaskId, courseId, addGeneratedFile, setViewingFile, addMaterial, refreshCourseMaterials]);

  const [directBgTasks, setDirectBgTasks] = useState<DirectBgTask[]>([]);

  useEffect(() => {
    if (directBgTasks.length === 0) return;
    const interval = setInterval(async () => {
      const remaining: DirectBgTask[] = [];
      for (const task of directBgTasks) {
        try {
          const status = await pollChatTask(task.taskId);
          if (status.status === 'completed' && status.result) {
            const files = extractGeneratedFilesFromV2Response(status.result as any).map((f) => ({
              ...f,
              meta: { ...(f.meta || {}), ...task.originMeta },
            }));
            files.forEach((f) => addGeneratedFile(f as GeneratedFile));
            if (files.length > 0) {
              const latest = files[files.length - 1] as GeneratedFile;
              setViewingFile(latest);
              if (task.courseId) {
                addMaterial({ ...latest, addedAt: new Date().toISOString(), courseId: task.courseId });
                refreshCourseMaterials();
              }
            }
            notification.success({
              message: `${task.description}已生成`,
              description: files.length > 0 ? '已在右侧面板打开。' : '请在资源列表中查看。',
              duration: 6,
            });
          } else if (status.status === 'failed') {
            notification.error({
              message: `${task.description}生成失败`,
              description: status.error || '未知错误',
              duration: 8,
            });
          } else {
            remaining.push(task);
          }
        } catch {
          remaining.push(task);
        }
      }
      setDirectBgTasks(remaining);
    }, 2000);
    return () => clearInterval(interval);
  }, [directBgTasks, addGeneratedFile, setViewingFile, addMaterial, refreshCourseMaterials]);

  const [configForm] = Form.useForm();
  const [generating, setGenerating] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizChecked, setQuizChecked] = useState<Record<string, boolean>>({});
  const [currentQuizIndex, setCurrentQuizIndex] = useState(0);
  const [reportPreviewMode, setReportPreviewMode] = useState<'body' | 'outline-solid'>('body');
  const [reportEntryVisible, setReportEntryVisible] = useState(false);
  const [lessonPlanEntryVisible, setLessonPlanEntryVisible] = useState(false);
  const [quizEntryVisible, setQuizEntryVisible] = useState(false);
  const [gameEntryVisible, setGameEntryVisible] = useState(false);
  const pptPreviewFrameRef = useRef<HTMLDivElement | null>(null);
  const pptFullscreenRef = useRef<HTMLDivElement | null>(null);
  const [pptPreviewFrameWidth, setPptPreviewFrameWidth] = useState(PPT_PREVIEW_BASE_WIDTH);
  const [pptFullscreenActive, setPptFullscreenActive] = useState(false);
  const openGeneratedFile = (file: GeneratedFile) => {
    setViewingFile(file);
  };

  useEffect(() => {
    const element = pptPreviewFrameRef.current;
    if (!element || typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      const nextWidth = Math.max(Math.floor(entry?.contentRect?.width || 0), 320);
      setPptPreviewFrameWidth(nextWidth);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [viewingFile?.id]);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const handleFullscreenChange = () => {
      setPptFullscreenActive(document.fullscreenElement === pptFullscreenRef.current);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    handleFullscreenChange();
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, [viewingFile?.id]);

  useEffect(() => {
    setReportPreviewMode('body');
  }, [viewingFile?.id]);

  useEffect(() => {
    setCurrentQuizIndex(0);
  }, [viewingFile?.id]);

  const handleGenerateLegacy = async (type: GeneratedFile['type'] | string) => {
    const typeNames: Record<string, string> = {
      report: '报告',
      quiz: '测验',
      blog: '博客',
      lesson_plan: '教案',
      audio: '音频概览',
      video: '视频概览',
      graph: '思维导图',
      flashcard: '闪卡',
    };
    
    // 需要先配置参数的生成类型
    if (type === 'lesson_plan' || type === 'report' || type === 'blog' || type === 'quiz') {
      setConfigType(type);
      setConfigModalVisible(true);
      if (type === 'lesson_plan') {
        configForm.setFieldsValue({
          topic: '',
          duration: 45,
          difficulty: 'medium',
          knowledge_points: [],
          key_points: '',
          hard_points: '',
        });
      } else if (type === 'report') {
        configForm.setFieldsValue({
          title: '',
          focus_areas: [],
        });
      } else if (type === 'blog') {
        configForm.setFieldsValue({
          topic: '',
          description: '',
          length: 'medium',
        });
      } else if (type === 'quiz') {
        configForm.setFieldsValue({
          title: '',
          question_type: 'mixed',
          count: 10,
          difficulty: 'medium',
        });
      }
      return;
    }
    
    // 其他类型暂时显示TODO
    const newFile: GeneratedFile = {
      id: Date.now().toString(),
      name: `新${typeNames[type] || '文件'}-${generatedFiles.length + 1}`,
      type: type as GeneratedFile['type'],
    };
    addGeneratedFile(newFile);
    message.info('该功能开发中，敬请期待');
  };

  const handleGenerate = async (type: GeneratedFile['type'] | string) => {
    if (type === 'lesson_plan') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先选择至少一份知识库文档。');
        return;
      }
      setLessonPlanEntryVisible(true);
      return;
    }
    if (type === 'report') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先选择至少一份知识库文档');
        return;
      }
      setReportEntryVisible(true);
      return;
    }

    if (type === 'quiz') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先勾选至少一份知识库文档。');
        return;
      }
      setQuizEntryVisible(true);
      return;
    }

    if (type === 'quiz') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先勾选至少一份知识库文档。');
        return;
      }
      setQuizEntryVisible(true);
      return;
    }

    if (type === 'game') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先勾选至少一份知识库文档。');
        return;
      }
      setGameEntryVisible(true);
      return;
    }

    if (type === 'game') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先勾选至少一份知识库文档。');
        return;
      }
      setGameEntryVisible(true);
      return;
    }

    return handleGenerateLegacy(type);
  };

  const handleConfigureLegacy = (type: string) => {
    setConfigType(type);
    setConfigModalVisible(true);
    if (type === 'lesson_plan') {
      configForm.setFieldsValue({
        topic: '',
        duration: 45,
        difficulty: 'medium',
        knowledge_points: [],
        key_points: '',
        hard_points: '',
      });
    } else {
      configForm.setFieldsValue({
        topic: '',
        duration: 45,
        difficulty: 'medium',
      });
    }
  };

  const handleConfigure = (type: string) => {
    if (type === 'lesson_plan') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先选择至少一份知识库文档。');
        return;
      }
      setLessonPlanEntryVisible(true);
      return;
    }
    if (type === 'report') {
      if (!selectedDocs || selectedDocs.length === 0) {
        message.warning('请先选择至少一份知识库文档');
        return;
      }
      setReportEntryVisible(true);
      return;
    }

    handleConfigureLegacy(type);
  };

  const handleReportEntrySubmit = async ({
    question,
    promptDraft,
    card,
  }: {
    question: string;
    promptDraft: string;
    card: ReportEntryCard;
  }) => {
    setGenerating(true);
    try {
      const task = await generateKnowledgeBaseReportV2(
        buildKnowledgeBaseReportRequest({
          question,
          promptDraft,
          card,
          courseId,
          scopeType: workspaceScopeApiParams.scopeType,
          scopeId: workspaceScopeApiParams.scopeId,
          selectedDocIds: selectedDocs,
          allowRag,
          allowWeb,
        }),
      );
      setDirectBgTasks((prev) => [
        ...prev,
        { taskId: task.task_id, workflowType: task.workflow_type, description: '报告', originMeta: { origin: 'knowledge_base_direct' }, courseId },
      ]);
      setReportEntryVisible(false);
      message.success('报告生成任务已提交，后台处理中...');
    } catch (error: any) {
      message.error(`报告生成失败: ${error.message || '未知错误'}`);
      throw error;
    } finally {
      setGenerating(false);
    }
  };

  const handleQuizEntrySubmit = async ({
    config,
  }: {
    config: DirectQuizConfigV2;
  }) => {
    setGenerating(true);
    try {
      const task = await generateKnowledgeBaseQuizV2(
        buildKnowledgeBaseQuizRequest({
          courseId,
          scopeType: workspaceScopeApiParams.scopeType,
          scopeId: workspaceScopeApiParams.scopeId,
          selectedDocIds: selectedDocs,
          config,
        }),
      );
      setDirectBgTasks((prev) => [
        ...prev,
        { taskId: task.task_id, workflowType: task.workflow_type, description: '习题', originMeta: { origin: 'knowledge_base_direct', entryMode: 'knowledge_base_quiz' }, courseId },
      ]);
      setQuizEntryVisible(false);
      message.success('习题生成任务已提交，后台处理中...');
    } catch (error: any) {
      message.error(`习题生成失败: ${error.message || '未知错误'}`);
      throw error;
    } finally {
      setGenerating(false);
    }
  };

  const handleGameEntrySubmit = async ({
    gameType,
  }: {
    gameType: GameTypeV2;
  }) => {
    setGenerating(true);
    try {
      const task = await generateKnowledgeBaseGameV2({
        course_id: courseId,
        scope_type: workspaceScopeApiParams.scopeType,
        scope_id: workspaceScopeApiParams.scopeId,
        selected_doc_ids: selectedDocs,
        game_type: gameType,
      });
      setDirectBgTasks((prev) => [
        ...prev,
        { taskId: task.task_id, workflowType: task.workflow_type, description: '小游戏', originMeta: { origin: 'knowledge_base_direct', entryMode: 'knowledge_base_game' }, courseId },
      ]);
      setGameEntryVisible(false);
      message.success('小游戏生成任务已提交，后台处理中...');
    } catch (error: any) {
      message.error(`小游戏生成失败: ${error.message || '未知错误'}`);
      throw error;
    } finally {
      setGenerating(false);
    }
  };

  const handleLessonPlanEntrySubmit = async ({
    card,
    config,
  }: {
    card: LessonPlanEntryCard;
    config: LessonPlanEntryConfigInput;
  }) => {
    setGenerating(true);
    try {
      clearArtifactReference();
      clearConversationReference();
      setMessages([]);

      const request = {
        ...buildKnowledgeBaseLessonPlanReplyRequest({
          card,
          config,
          courseId,
          scopeType: workspaceScopeApiParams.scopeType,
          scopeId: workspaceScopeApiParams.scopeId,
          selectedDocIds: selectedDocs,
        }),
        action_hint: 'generate.lesson_plan' as const,
      };

      const response = await sendChatReplyV2(request);

      const nextConversationId = String(response.conversation?.conversation_id || '').trim();
      if (nextConversationId) {
        setCurrentConversationId(nextConversationId);
      }
      setStatusCard(response.status_card || null);

      const generatedLessonPlanFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
        ...file,
        meta: {
          ...(file.meta || {}),
          origin: 'conversation',
          conversationId: nextConversationId || undefined,
          entryMode: 'knowledge_base_lesson_plan',
        },
      }));

      generatedLessonPlanFiles.forEach((file) => addGeneratedFile(file));

      if (generatedLessonPlanFiles.length > 0) {
        const latestFile = generatedLessonPlanFiles[generatedLessonPlanFiles.length - 1];
        setViewingFile(latestFile);

        if (courseId) {
          addMaterial({
            ...latestFile,
            addedAt: new Date().toISOString(),
            courseId,
          });
          await refreshCourseMaterials();
        }
      }

      setLessonPlanEntryVisible(false);
      message.success(generatedLessonPlanFiles.length > 0 ? '教案大纲已生成并在右侧打开。' : '教案流程已启动。');
    } catch (error: any) {
      message.error(`教案生成失败: ${error.message || '未知错误'}`);
      throw error;
    } finally {
      setGenerating(false);
    }
  };

  const handleConfigSubmit = async () => {
    try {
      const values = await configForm.validateFields();

      // 如果是教案生成，调用后端API
      if (configType === 'lesson_plan') {
        setConfigModalVisible(false);
        setLessonPlanEntryVisible(true);
        return;
        // 检查是否选择了文档
        if (!selectedDocs || selectedDocs.length === 0) {
          message.warning('请先选择至少一个文档');
          return;
        }
        
        setGenerating(true);
        try {
          // 检查courseId是否存在
          if (!courseId) {
            message.error('无法保存：课程ID缺失，请确保在课程页面中操作');
            return;
          }
          
          const request = {
            topic: values.topic,
            course_id: courseId,
            selected_doc_ids: selectedDocs,
            duration: values.duration || 45,
            difficulty: values.difficulty || 'medium',
            knowledge_points: values.knowledge_points ? (Array.isArray(values.knowledge_points) ? values.knowledge_points : [values.knowledge_points]) : [],
            key_points: values.key_points || undefined,
            hard_points: values.hard_points || undefined,
          };
          
          console.log('[StudioPanel] 生成教案请求:', { course_id: courseId, topic: values.topic });
          const response = null as any;
          console.log('[StudioPanel] 教案生成响应:', { id: response.id, title: response.title });
          
          // 使用后端返回的ID，如果没有则使用时间戳
          const fileId = response.id || Date.now().toString();
          
          // 创建生成的教案文件
          const newFile: GeneratedFile = {
            id: fileId,
            name: response.title || `教案-${generatedFiles.length + 1}`,
            type: 'lesson_plan',
            content: response, // 保存教案内容
          };
          addGeneratedFile(newFile);
          setViewingFile(newFile);
          
          // 自动添加到课程资源（后端已保存，前端同步到store）
          const material = {
            ...newFile,
            addedAt: new Date().toISOString(),
            courseId: courseId,
          };
          console.log('[StudioPanel] 添加到课程资源store:', material);
          addMaterial(material);
          await refreshCourseMaterials();
          
          message.success('教案生成成功！已自动保存到教学资源');
          setConfigModalVisible(false);
          configForm.resetFields();
        } catch (error: any) {
          message.error(`生成教案失败: ${error.message || '未知错误'}`);
        } finally {
          setGenerating(false);
        }
      } else if (configType === 'report') {
        setConfigModalVisible(false);
        setReportEntryVisible(true);
        configForm.resetFields();
      } else if (configType === 'blog') {
        if (!courseId) {
          message.error('无法生成：课程ID缺失，请确保在课程页面中操作');
          return;
        }

        setGenerating(true);
        try {
          const startResp = await startBlogGenerate({
            course_id: courseId,
            topic: values.topic,
          });

          setBlogTaskId(startResp.thread_id);
          message.success('已启动教学博客生成任务');
          setConfigModalVisible(false);
          configForm.resetFields();

          setBlogPolling(true);
        } catch (error: any) {
          message.error(`启动教学博客失败: ${error.message || '未知错误'}`);
        } finally {
          setGenerating(false);
        }
      } else if (configType === 'quiz') {
        if (!selectedDocs || selectedDocs.length === 0) {
          message.warning('请先选择至少一个文档');
          return;
        }
        if (!courseId) {
          message.error('无法保存：课程ID缺失，请确保在课程页面中操作');
          return;
        }

        setGenerating(true);
        try {
          const request: QuizRequest = {
            title: values.title || undefined,
            course_id: courseId,
            selected_doc_ids: selectedDocs,
            question_type: values.question_type || 'mixed',
            count: values.count || 10,
            difficulty: values.difficulty || 'medium',
          };

          const response = await generateQuiz(request);
          const fileId = response.id || Date.now().toString();

          const newFile: GeneratedFile = {
            id: fileId,
            name: response.title || `测验-${generatedFiles.length + 1}`,
            type: 'quiz',
            content: response,
          };

          addGeneratedFile(newFile);
          setViewingFile(newFile);

          const material = {
            ...newFile,
            addedAt: new Date().toISOString(),
            courseId,
          };
          addMaterial(material);

          message.success('测验生成成功！已自动保存到教学资源');
          setConfigModalVisible(false);
          configForm.resetFields();
        } catch (error: any) {
          message.error(`生成测验失败: ${error.message || '未知错误'}`);
        } finally {
          setGenerating(false);
        }
      } else {
        // 其他类型的配置保存
        console.log('配置参数:', values);
        setConfigModalVisible(false);
        configForm.resetFields();
      }
    } catch (error) {
      console.error('配置验证失败:', error);
    }
  };

  const handleAddToCourseMaterials = (file: GeneratedFile) => {
    const material = {
      ...file,
      addedAt: new Date().toISOString(),
    };
    addMaterial(material);
    message.success('已增加到课程资料');
  };

  // Collapsed view: 显示功能模块logo和文档列表
  const handleAddToChat = (file: GeneratedFile) => {
    if (!isArtifactReferenceEligible(file)) {
      return;
    }

    const artifactType =
      file.type === 'ppt'
        ? 'ppt_deck'
        : file.meta?.kind === 'outline-solid'
          ? 'report_outline'
          : 'report';

    setArtifactReference({
      artifact_id: String(file.meta?.originalArtifactId || file.id).trim(),
      artifact_type: artifactType,
      version_id: String(file.meta?.versionId || '').trim() || undefined,
      title: file.name,
      source_conversation_id: String(file.meta?.conversationId || currentConversationId || '').trim() || undefined,
      source_course_id: String(courseId || '').trim() || undefined,
    });
    message.success('已添加到对话');
  };

  const primaryStudioActions = [...STUDIO_ACTIONS].sort(
    (left, right) =>
      STUDIO_ACTION_DISPLAY_ORDER.indexOf(left.type) - STUDIO_ACTION_DISPLAY_ORDER.indexOf(right.type),
  );
  const selectedDocCount = selectedDocs.length;
  const visibleGeneratedFiles = generatedFiles;

  if (collapsed) {
    // 功能类型定义
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          background: '#ffffff',
          borderRadius: 12,
          padding: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <Button 
            type="text" 
            icon={<LeftOutlined />} 
            onClick={onToggleCollapsed} 
            aria-label="展开工作室"
            style={{ padding: '4px 8px' }}
          />
        </div>
        
        {/* 功能模块logo - 一字排开 */}
        <div style={{ 
          display: 'flex',
          flexDirection: 'column',
          gap: 8, 
          marginBottom: 16,
          paddingBottom: 16,
          borderBottom: '1px solid #f0f0f0'
        }}>
          {STUDIO_ACTIONS.map((func) => (
            <div
              key={func.type}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '10px',
                background: `${func.color}10`,
                borderRadius: 8,
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = `${func.color}20`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = `${func.color}10`;
              }}
              onClick={() => handleGenerate(func.type)}
            >
              <div style={{ fontSize: 18, color: func.color }}>
                {func.icon}
              </div>
            </div>
          ))}
        </div>

        {/* 生成的文档列表 */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {generatedFiles.length > 0 ? (
            generatedFiles.map((f) => (
              <div
                key={f.id}
                style={{ 
                  height: 40, 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  marginBottom: 4,
                  cursor: 'pointer',
                  borderRadius: 4,
                  transition: 'background 0.2s',
                }}
                onClick={() => openGeneratedFile(f)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
                title={f.name}
              >
                {getGeneratedFileIcon(f, 18)}
              </div>
            ))
          ) : (
            <Text type="secondary" style={{ fontSize: 12, textAlign: 'center', display: 'block' }}>
              暂无生成文件
            </Text>
          )}
        </div>
      </div>
    );
  }

  // Detail view
  if (viewingFile) {
    if (viewingFile.type === 'game') {
      return (
        <GameArtifactPreview
          file={viewingFile}
          onBack={() => setViewingFile(null)}
          onToggleCollapsed={onToggleCollapsed}
        />
      );
    }

    if (viewingFile.type === 'lesson_plan' && viewingFile.content) {
      const lessonPlanKind = String((viewingFile.meta as any)?.kind || '').trim();
      return (
        <LessonPlanArtifactPreview
          file={viewingFile}
          kind={lessonPlanKind}
          onBack={() => setViewingFile(null)}
          onToggleCollapsed={onToggleCollapsed}
          onContinueFromOutline={() => {
            setViewingFile(null);
            setQueuedMessage('确认并继续');
          }}
        />
      );
    }

    // 教案预览
    if (viewingFile.type === 'lesson_plan' && viewingFile.content) {
      const lessonPlanKind = String((viewingFile.meta as any)?.kind || '').trim();
      const plan = normalizeLessonPlanPreview(viewingFile.content, lessonPlanKind);
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {plan.title || viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
            {lessonPlanKind === 'outline-solid' && (
              <div
                style={{
                  marginBottom: 20,
                  padding: 16,
                  borderRadius: 10,
                  background: '#f6ffed',
                  border: '1px solid #b7eb8f',
                }}
              >
                <Text strong style={{ color: '#389e0d' }}>
                  当前预览的是教案大纲
                </Text>
                <Paragraph style={{ margin: '8px 0 0', color: '#595959' }}>
                  这版用于确认教学目标、重点难点和课堂流程，确认后会继续生成完整正文。
                </Paragraph>
              </div>
            )}

            {(plan.basicInfo.audience || plan.basicInfo.duration || plan.basicInfo.lessonType) && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ marginBottom: 12 }}>基本信息</Title>
                <Space size={[8, 8]} wrap>
                  {plan.basicInfo.audience && (
                    <span style={{ padding: '4px 12px', background: '#f5f5f5', borderRadius: 999 }}>
                      适用对象：{plan.basicInfo.audience}
                    </span>
                  )}
                  {plan.basicInfo.duration && (
                    <span style={{ padding: '4px 12px', background: '#f5f5f5', borderRadius: 999 }}>
                      课时：{plan.basicInfo.duration}
                    </span>
                  )}
                  {plan.basicInfo.lessonType && (
                    <span style={{ padding: '4px 12px', background: '#f5f5f5', borderRadius: 999 }}>
                      课型：{plan.basicInfo.lessonType}
                    </span>
                  )}
                </Space>
              </div>
            )}
            {/* 教学目标 */}
            {plan.objectives && plan.objectives.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>📚 教学目标</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {plan.objectives.map((obj, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {obj}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 教学重点 */}
            {plan.keyPoints && plan.keyPoints.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>⭐ 教学重点</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {plan.keyPoints.map((kp, idx) => (
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
            {plan.hardPoints && plan.hardPoints.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#ff4d4f', marginBottom: 12 }}>⚠️ 教学难点</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {plan.hardPoints.map((hp, idx) => (
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
            {plan.breakthroughStrategy && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#13c2c2', marginBottom: 12 }}>难点突破</Title>
                <div
                  style={{
                    padding: 16,
                    background: '#e6fffb',
                    borderRadius: 8,
                    border: '1px solid #87e8de',
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
                    {plan.breakthroughStrategy}
                  </Paragraph>
                </div>
              </div>
            )}

            {plan.process && plan.process.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#722ed1', marginBottom: 12 }}>📖 教学过程</Title>
                {plan.process.map((step, idx) => (
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
            {(plan.teachingMethods.length > 0 || plan.teachingAids.length > 0 || plan.boardPlan.length > 0 || plan.assessmentMethod) && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#2f54eb', marginBottom: 12 }}>教学支持</Title>
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {plan.teachingMethods.length > 0 && (
                    <div>
                      <Text strong>教学方法：</Text>
                      <Text>{plan.teachingMethods.join('、')}</Text>
                    </div>
                  )}
                  {plan.teachingAids.length > 0 && (
                    <div>
                      <Text strong>教学资源：</Text>
                      <Text>{plan.teachingAids.join('、')}</Text>
                    </div>
                  )}
                  {plan.boardPlan.length > 0 && (
                    <div>
                      <Text strong>板书建议：</Text>
                      <Text>{plan.boardPlan.join('、')}</Text>
                    </div>
                  )}
                  {plan.assessmentMethod && (
                    <div>
                      <Text strong>课堂评价：</Text>
                      <Text>{plan.assessmentMethod}</Text>
                    </div>
                  )}
                </Space>
              </div>
            )}

            {plan.homework && (
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
                    {plan.homework}
                  </Paragraph>
                </div>
              </div>
            )}
          </div>
          {lessonPlanKind === 'outline-solid' && (
            <div style={{ position: 'absolute', right: 24, bottom: 24 }}>
              <Button
                type="primary"
                onClick={() => {
                  setViewingFile(null);
                  setQueuedMessage('确认并继续');
                }}
              >
                继续生成教案
              </Button>
            </div>
          )}
        </div>
      );
    }

    if (viewingFile.type === 'video') {
      const videoPayload =
        viewingFile.content && typeof viewingFile.content === 'object'
          ? (viewingFile.content as Record<string, any>)
          : {};
      const videoUrl = String(videoPayload.video_url || '').trim();
      const videoErrorMessage = String(videoPayload.error_message || '').trim();
      const videoGenerationState = ((viewingFile.meta as any)?.generationState || {}) as Record<string, any>;
      const videoStatus = String(videoGenerationState.status || '').trim();
      const videoPhase = String(videoGenerationState.phase || '').trim();
      const videoMessage = String(videoGenerationState.message || '').trim();
      const videoReady = Boolean(videoUrl) && videoStatus !== 'failed';
      const videoStatusText =
        videoStatus === 'completed'
          ? '教学视频已生成完成'
          : videoStatus === 'failed'
            ? videoMessage || videoErrorMessage || '教学视频生成失败'
            : videoMessage || '教学视频生成中';

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作区" />
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />

          <div
            style={{
              border: '1px solid #f0f0f0',
              borderRadius: 16,
              background: 'linear-gradient(180deg, #f6ffed 0%, #ffffff 100%)',
              padding: 20,
              marginBottom: 16,
              flexShrink: 0,
            }}
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Space align="center">
                <Spin size="small" spinning={!videoReady && videoStatus !== 'failed'} />
                <Text strong style={{ fontSize: 16, color: '#1f1f1f' }}>
                  {videoStatusText}
                </Text>
              </Space>
              {(videoPhase || videoStatus !== 'completed') && (
                <Text type="secondary">
                  当前阶段：{videoPhase || 'processing'}
                </Text>
              )}
              <Space wrap>
                {videoUrl ? (
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => window.open(videoUrl, '_blank', 'noopener,noreferrer')}
                  >
                    新窗口播放
                  </Button>
                ) : null}
                <Button icon={<MessageOutlined />} onClick={() => handleAddToChat(viewingFile)}>
                  添加到对话
                </Button>
              </Space>
            </Space>
          </div>

          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {videoReady ? (
              <div
                style={{
                  height: '100%',
                  borderRadius: 16,
                  overflow: 'hidden',
                  background: '#000',
                  border: '1px solid rgba(0, 0, 0, 0.08)',
                }}
              >
                <video
                  controls
                  preload="metadata"
                  src={videoUrl}
                  style={{ width: '100%', height: '100%', display: 'block', background: '#000' }}
                />
              </div>
            ) : (
              <div
                style={{
                  height: '100%',
                  minHeight: 240,
                  borderRadius: 16,
                  border: '1px dashed #b7eb8f',
                  background: '#fcffe6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 24,
                }}
              >
                <Space direction="vertical" size={12} align="center">
                  <VideoCameraOutlined style={{ fontSize: 32, color: videoStatus === 'failed' ? '#ff4d4f' : '#52c41a' }} />
                  <Text strong>{videoStatusText}</Text>
                  <Text type="secondary" style={{ textAlign: 'center' }}>
                    {videoStatus === 'failed'
                      ? videoErrorMessage || videoMessage || '任务执行失败，请重新选择 PPT 后再次发起生成。'
                      : '视频任务已经提交，系统会继续轮询状态，生成完成后会自动在这里展示播放器。'}
                  </Text>
                </Space>
              </div>
            )}
          </div>
        </div>
      );
    }

    // 报告预览
    if (viewingFile.type === 'ppt') {
      const pptKind = String((viewingFile.meta as any)?.kind || '').trim();
      const pptPreviewUrl = String(resolvePptAssetUrl((viewingFile.meta as any)?.htmlPreviewUrl) || '').trim();
      const pptExportUrl = String(resolvePptAssetUrl((viewingFile.meta as any)?.pptxUrl) || '').trim();
      const pptManifestUrl = String(resolvePptAssetUrl((viewingFile.meta as any)?.manifestUrl) || '').trim();
      const pptOutlineContent = String((viewingFile.meta as any)?.outlineContent || '').trim();
      const pptMarkdownContent = String((viewingFile.meta as any)?.contentMarkdown || '').trim();
      const pptGenerationState = ((viewingFile.meta as any)?.generationState || {}) as Record<string, any>;
      const pptGenerationStatus = String(pptGenerationState?.status || '').trim();
      const pptGenerationPhase = String(pptGenerationState?.phase || '').trim();
      const pptGenerationMessage = String(pptGenerationState?.message || '').trim();
      const pptGenerationProgress = Number(pptGenerationState?.progress || 0);
      const pptGenerationPhaseLabel = getPptPhaseLabel(pptGenerationPhase);
      const pptStatusText = getPptStatusText(pptGenerationStatus, pptGenerationPhase, pptGenerationMessage);
      const pptPreviewScale = Math.min(1, pptPreviewFrameWidth / PPT_PREVIEW_BASE_WIDTH);
      const pptTextPreview =
        pptKind === 'ppt_content_markdown'
          ? String(viewingFile.content || '').trim()
          : pptOutlineContent || pptMarkdownContent || String(viewingFile.content || '').trim();

      if (pptKind === 'ppt_deck' && !pptPreviewUrl) {
        return (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              background: '#ffffff',
              borderRadius: 12,
              padding: 24,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              minHeight: 0,
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={() => setViewingFile(null)}
                style={{ marginLeft: -12 }}
              >
                返回
              </Button>
              <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
            </div>

            <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
              {viewingFile.name}
            </Title>
            <Divider style={{ flexShrink: 0 }} />
            <div
              style={{
                border: '1px solid #f0f0f0',
                borderRadius: 16,
                background: 'linear-gradient(180deg, #fffaf2 0%, #ffffff 100%)',
                padding: 20,
                marginBottom: 16,
                flexShrink: 0,
              }}
            >
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <Space align="center">
                  <Spin size="small" spinning={pptGenerationStatus === 'running'} />
                  <Text strong style={{ fontSize: 16, color: '#1f1f1f' }}>
                    {pptStatusText}
                  </Text>
                </Space>
                <Text type="secondary">
                  当前阶段：{pptGenerationPhaseLabel} {pptGenerationProgress > 0 ? `· ${pptGenerationProgress}%` : ''}
                </Text>
                {pptGenerationProgress > 0 && <Progress percent={Math.max(0, Math.min(100, pptGenerationProgress))} showInfo={false} strokeColor="#d48806" />}
                <Space>
                  {pptExportUrl && (
                    <Button icon={<FilePptOutlined />} onClick={() => window.open(pptExportUrl, '_blank', 'noopener,noreferrer')}>
                      导出 PPT
                    </Button>
                  )}
                </Space>
              </Space>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
              <MarkdownPreview content={pptOutlineContent || pptMarkdownContent || '当前 PPT 产物暂时还没有可预览内容。'} />
            </div>
          </div>
        );
      }

      if (pptKind === 'ppt_deck' && pptPreviewUrl) {
        return (
          <div
            ref={pptFullscreenRef}
            style={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              background: '#ffffff',
              borderRadius: 12,
              padding: 24,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              minHeight: 0,
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={() => setViewingFile(null)}
                style={{ marginLeft: -12 }}
              >
                返回
              </Button>
              <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
            </div>

            <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
              {viewingFile.name}
            </Title>
            <Divider style={{ flexShrink: 0 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, flexShrink: 0 }}>
              <Space>
                <Button icon={<MessageOutlined />} onClick={() => handleAddToChat(viewingFile)}>
                  添加到对话
                </Button>
                <Button
                  onClick={() => {
                    if (typeof document === 'undefined') {
                      return;
                    }
                    if (document.fullscreenElement === pptFullscreenRef.current) {
                      void document.exitFullscreen?.();
                      return;
                    }
                    void pptFullscreenRef.current?.requestFullscreen?.();
                  }}
                >
                  {pptFullscreenActive ? '退出全屏' : '全屏预览'}
                </Button>
                {pptManifestUrl && (
                  <Button onClick={() => window.open(pptManifestUrl, '_blank', 'noopener,noreferrer')}>
                    查看结构
                  </Button>
                )}
                {pptExportUrl && (
                  <Button type="primary" icon={<FilePptOutlined />} onClick={() => window.open(pptExportUrl, '_blank', 'noopener,noreferrer')}>
                    导出 PPT
                  </Button>
                )}
              </Space>
            </div>
            <div
              ref={pptPreviewFrameRef}
              style={{
                flex: 1,
                minHeight: 0,
                overflow: 'hidden',
                borderRadius: 12,
                border: '1px solid #f0f0f0',
                background: '#fafafa',
                position: 'relative',
              }}
            >
              <iframe
                src={pptPreviewUrl}
                title={viewingFile.name}
                style={{
                  width: `${PPT_PREVIEW_BASE_WIDTH}px`,
                  height: `calc(100% / ${pptPreviewScale})`,
                  border: 0,
                  background: '#fff',
                  transform: `scale(${pptPreviewScale})`,
                  transformOrigin: 'top left',
                }}
              />
            </div>
          </div>
        );
      }

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
            <MarkdownPreview content={pptTextPreview || '当前 PPT 产物暂时还没有可预览内容。'} />
          </div>
          {(viewingFile as any)?.meta?.kind === 'ppt_outline' && (
            <div style={{ position: 'absolute', right: 24, bottom: 24 }}>
              <Button
                type="primary"
                onClick={() => {
                  const text = `根据已确认的大纲开始生成PPT`;
                  setViewingFile(null);
                  setQueuedMessage(text);
                }}
              >
                生成PPT
              </Button>
            </div>
          )}
        </div>
      );
    }

    if (viewingFile.type === 'report' && viewingFile.content) {
      const rawReportOutlineContent = (viewingFile as any)?.meta?.outlineContent;
      const canToggleReportOutline = String((viewingFile as any)?.meta?.kind || '').trim() !== 'outline-solid';

      return (
        <ReportArtifactPreview
          file={viewingFile}
          outlineContent={rawReportOutlineContent}
          previewMode={reportPreviewMode}
          canToggleOutline={canToggleReportOutline}
          canAddToChat={isArtifactReferenceEligible(viewingFile)}
          onPreviewModeChange={setReportPreviewMode}
          onBack={() => setViewingFile(null)}
          onToggleCollapsed={onToggleCollapsed}
          onAddToChat={() => handleAddToChat(viewingFile)}
          onGenerateFromOutline={() => {
            setViewingFile(null);
            const store = useStore.getState();
            store.setQueuedMessage('根据已确认的大纲开始生成报告');
          }}
        />
      );
    }

    if (viewingFile.type === 'report' && viewingFile.content) {
      const reportOutlineContent = String((viewingFile as any)?.meta?.outlineContent || '').trim();
      const canToggleReportOutline =
        Boolean(reportOutlineContent) && (viewingFile as any)?.meta?.kind !== 'outline-solid';
      if (typeof viewingFile.content === 'string') {
        return (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              background: '#ffffff',
              borderRadius: 12,
              padding: 24,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              minHeight: 0,
              overflow: 'hidden',
              position: 'relative',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={() => setViewingFile(null)}
                style={{ marginLeft: -12 }}
              >
                返回
              </Button>
              <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
            </div>

            <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
              {viewingFile.name}
            </Title>
            <Divider style={{ flexShrink: 0 }} />
            {isArtifactReferenceEligible(viewingFile) && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, flexShrink: 0 }}>
                <Button type="primary" icon={<MessageOutlined />} onClick={() => handleAddToChat(viewingFile)}>
                  添加到对话
                </Button>
              </div>
            )}
            {canToggleReportOutline && (
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, flexShrink: 0 }}>
                <Space.Compact>
                  <Button
                    type={reportPreviewMode === 'body' ? 'primary' : 'default'}
                    onClick={() => setReportPreviewMode('body')}
                  >
                    正文
                  </Button>
                  <Button
                    type={reportPreviewMode === 'outline-solid' ? 'primary' : 'default'}
                    onClick={() => setReportPreviewMode('outline-solid')}
                  >
                    大纲
                  </Button>
                </Space.Compact>
              </div>
            )}
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
              <MarkdownPreview content={reportPreviewMode === 'outline-solid' ? reportOutlineContent : viewingFile.content} />
            </div>
            {(viewingFile as any)?.meta?.kind === 'outline-solid' && (
              <div style={{ position: 'absolute', right: 24, bottom: 24 }}>
                <Button type="primary" onClick={() => {
                  const text = `根据已确认的大纲开始生成报告`;
                  setViewingFile(null);
                  const store = useStore.getState();
                  store.setQueuedMessage(text);
                }}>
                  生成报告
                </Button>
              </div>
            )}
          </div>
        );
      }

      const report = viewingFile.content as ReportResponse;
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {report.title || viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />
          {isArtifactReferenceEligible(viewingFile) && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, flexShrink: 0 }}>
              <Button type="primary" icon={<MessageOutlined />} onClick={() => handleAddToChat(viewingFile)}>
                添加到对话
              </Button>
            </div>
          )}
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
            {/* 执行摘要 */}
            {report.summary && (
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
                  {report.summary}
                </Paragraph>
              </div>
            )}

            {/* 引言 */}
            {report.introduction && (
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
                  {report.introduction}
                </Paragraph>
              </div>
            )}

            {/* 主要内容 */}
            {report.mainContent && report.mainContent.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>📚 主要内容</Title>
                {report.mainContent.map((section, idx) => (
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
            {report.keyFindings && report.keyFindings.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#fa8c16', marginBottom: 12 }}>⭐ 关键发现</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {report.keyFindings.map((finding, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {finding}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 结论 */}
            {report.conclusions && (
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
                    {report.conclusions}
                  </Paragraph>
                </div>
              </div>
            )}

            {/* 建议 */}
            {report.recommendations && report.recommendations.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>💡 建议</Title>
                <ul style={{ marginLeft: 20, lineHeight: 1.8, paddingLeft: 8 }}>
                  {report.recommendations.map((rec, idx) => (
                    <li key={idx} style={{ marginBottom: 8, fontSize: 14 }}>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      );
    }

    // 测验预览
    if (viewingFile.type === 'quiz' && viewingFile.content) {
      const quiz = viewingFile.content as QuizResponse;
      const questions = Array.isArray(quiz.questions) ? quiz.questions : [];
      const totalCount = questions.length;
      const checkedCount = questions.filter((q) => !!quizChecked[q.id]).length;
      const correctCount = questions.filter((q) => {
        if (!quizChecked[q.id]) return false;
        return isQuizAnswerCorrect(q, quizAnswers[q.id] || '');
      }).length;
      const accuracy = checkedCount > 0 ? Math.round((correctCount / checkedCount) * 100) : 0;
      const safeQuizIndex = Math.max(0, Math.min(currentQuizIndex, totalCount - 1));
      const currentQuestion = questions[safeQuizIndex];
      const currentQuestionId = String(currentQuestion?.id || '');
      const currentQuestionType = String(currentQuestion?.type || '').trim();
      const currentUserAnswer = currentQuestionId ? quizAnswers[currentQuestionId] || '' : '';
      const currentHasChecked = currentQuestionId ? !!quizChecked[currentQuestionId] : false;
      const currentIsCorrect = currentQuestion ? isQuizAnswerCorrect(currentQuestion, currentUserAnswer || '') : false;
      const progressPercent = totalCount > 0 ? Math.round(((safeQuizIndex + 1) / totalCount) * 100) : 0;

      const goToQuizIndex = (index: number) => {
        setCurrentQuizIndex(index);
      };

      const handleAutoAnswer = (value: string, autoCheck = false) => {
        if (!currentQuestionId) {
          return;
        }
        setQuizAnswers((prev) => ({ ...prev, [currentQuestionId]: value }));
        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: Boolean(autoCheck) }));
      };

      const handleCheckAllAnswers = () => {
        const nextChecked: Record<string, boolean> = { ...quizChecked };
        let answered = 0;
        questions.forEach((q) => {
          const val = quizAnswers[q.id];
          if (val && val.trim()) {
            answered += 1;
            nextChecked[q.id] = true;
          }
        });
        if (answered === 0) {
          message.warning('请至少作答一题后再查看答案');
          return;
        }
        setQuizChecked(nextChecked);
        message.success(`已判题 ${answered} 题`);
      };

      const handleSubmitCurrent = () => {
        if (!currentUserAnswer || !currentUserAnswer.trim()) {
          message.warning('请先作答后再判题');
          return;
        }
        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: true }));
      };

      return (
        <QuizArtifactPreview
          file={viewingFile}
          quiz={quiz}
          questions={questions}
          totalCount={totalCount}
          checkedCount={checkedCount}
          correctCount={correctCount}
          accuracy={accuracy}
          progressPercent={progressPercent}
          safeQuizIndex={safeQuizIndex}
          currentQuestion={currentQuestion}
          currentQuestionId={currentQuestionId}
          currentQuestionType={currentQuestionType}
          currentUserAnswer={currentUserAnswer}
          currentHasChecked={currentHasChecked}
          currentIsCorrect={currentIsCorrect}
          quizChecked={quizChecked}
          onBack={() => setViewingFile(null)}
          onToggleCollapsed={onToggleCollapsed}
          onReset={() => {
            setQuizAnswers({});
            setQuizChecked({});
          }}
          onCheckAll={handleCheckAllAnswers}
          onGoToIndex={goToQuizIndex}
          onAnswerChange={handleAutoAnswer}
          onSubmitCurrent={handleSubmitCurrent}
        />
      );
    }

    if (viewingFile.type === 'quiz' && viewingFile.content) {
      const quiz = viewingFile.content as QuizResponse;
      const questions = Array.isArray(quiz.questions) ? quiz.questions : [];
      const totalCount = questions.length;
      const checkedCount = questions.filter((q) => !!quizChecked[q.id]).length;
      const correctCount = questions.filter((q) => {
        if (!quizChecked[q.id]) return false;
        return isQuizAnswerCorrect(q, quizAnswers[q.id] || '');
      }).length;
      const accuracy = checkedCount > 0 ? Math.round((correctCount / checkedCount) * 100) : 0;
      const safeQuizIndex = totalCount > 0 ? Math.min(Math.max(currentQuizIndex, 0), totalCount - 1) : 0;
      const currentQuestion = questions[safeQuizIndex];
      const currentQuestionId = currentQuestion ? String(currentQuestion.id || safeQuizIndex + 1) : '';
      const currentQuestionType = String((currentQuestion as any)?.type || '').trim();
      const isCurrentChoiceQuestion = currentQuestionType === 'choice' && Array.isArray(currentQuestion?.options);
      const isCurrentJudgeQuestion = currentQuestionType === 'judge';
      const currentUserAnswer = currentQuestionId ? quizAnswers[currentQuestionId] || '' : '';
      const currentHasChecked = currentQuestionId ? !!quizChecked[currentQuestionId] : false;
      const currentIsCorrect = Boolean(
        currentQuestion && currentHasChecked && isQuizAnswerCorrect(currentQuestion, currentUserAnswer),
      );
      const progressPercent = totalCount > 0 ? Math.round(((safeQuizIndex + 1) / totalCount) * 100) : 0;
      const goToQuizIndex = (nextIndex: number) => {
        if (totalCount <= 0) return;
        setCurrentQuizIndex(Math.max(0, Math.min(totalCount - 1, nextIndex)));
      };

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {quiz.title || viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />

          <Card size="small" style={{ marginBottom: 12, flexShrink: 0, background: '#fafcff', borderColor: '#d6e4ff' }}>
            <Space size={16} wrap>
              <Text>总题数：<Text strong>{totalCount}</Text></Text>
              <Text>已判题：<Text strong>{checkedCount}</Text></Text>
              <Text>答对：<Text strong style={{ color: '#52c41a' }}>{correctCount}</Text></Text>
              <Text>正确率：<Text strong>{accuracy}%</Text></Text>
            </Space>
            <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button
                size="small"
                onClick={() => {
                  setQuizAnswers({});
                  setQuizChecked({});
                }}
              >
                重做本测验
              </Button>
              <Button
                size="small"
                type="primary"
                ghost
                onClick={() => {
                  const nextChecked: Record<string, boolean> = { ...quizChecked };
                  let answered = 0;
                  questions.forEach((q) => {
                    const val = quizAnswers[q.id];
                    if (val && val.trim()) {
                      answered += 1;
                      nextChecked[q.id] = true;
                    }
                  });
                  if (answered === 0) {
                    message.warning('请至少作答一题后再查看答案');
                    return;
                  }
                  setQuizChecked(nextChecked);
                  message.success(`已判题 ${answered} 道`);
                }}
              >
                一键查看答案
              </Button>
            </div>
          </Card>

          <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
            {currentQuestion ? (
              <Card
                key={currentQuestionId}
                size="small"
                style={{
                  height: '100%',
                  borderRadius: 16,
                  borderColor: '#d6e4ff',
                  boxShadow: '0 10px 28px rgba(22, 119, 255, 0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                }}
                bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, padding: 24 }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <Space direction="vertical" size={2}>
                    <Text type="secondary">第 {safeQuizIndex + 1} / {totalCount} 题</Text>
                    <Text strong style={{ fontSize: 20, lineHeight: 1.5 }}>
                      {currentQuestion.stem}
                    </Text>
                  </Space>
                  <Text
                    style={{
                      flexShrink: 0,
                      border: '1px solid #d6e4ff',
                      borderRadius: 999,
                      padding: '4px 10px',
                      color: '#1677ff',
                      background: '#f0f6ff',
                    }}
                  >
                    {isCurrentJudgeQuestion ? '判断题' : isCurrentChoiceQuestion ? '选择题' : '简答题'}
                  </Text>
                </div>

                <Progress percent={progressPercent} showInfo={false} style={{ margin: '18px 0 20px' }} />

                <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
                  {isCurrentChoiceQuestion ? (
                    <Radio.Group
                      value={currentUserAnswer || undefined}
                      onChange={(e) => {
                        setQuizAnswers((prev) => ({ ...prev, [currentQuestionId]: e.target.value }));
                        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: false }));
                      }}
                      style={{ width: '100%' }}
                    >
                      <Space direction="vertical" size={12} style={{ width: '100%' }}>
                        {(currentQuestion.options || []).map((opt, optIdx) => (
                          <Radio
                            key={`${currentQuestionId}_${optIdx}`}
                            value={opt}
                            style={{
                              width: '100%',
                              minHeight: 48,
                              padding: '10px 14px',
                              border: '1px solid #f0f0f0',
                              borderRadius: 12,
                              background: currentUserAnswer === opt ? '#f0f6ff' : '#fff',
                            }}
                          >
                            {opt}
                          </Radio>
                        ))}
                      </Space>
                    </Radio.Group>
                  ) : isCurrentJudgeQuestion ? (
                    <Radio.Group
                      value={currentUserAnswer || undefined}
                      onChange={(e) => {
                        setQuizAnswers((prev) => ({ ...prev, [currentQuestionId]: e.target.value }));
                        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: false }));
                      }}
                    >
                      <Space size={12} wrap>
                        <Radio.Button value="正确" style={{ minWidth: 120, textAlign: 'center' }}>正确</Radio.Button>
                        <Radio.Button value="错误" style={{ minWidth: 120, textAlign: 'center' }}>错误</Radio.Button>
                      </Space>
                    </Radio.Group>
                  ) : (
                    <Input.TextArea
                      value={currentUserAnswer}
                      rows={5}
                      placeholder="请输入答案"
                      onChange={(e) => {
                        setQuizAnswers((prev) => ({ ...prev, [currentQuestionId]: e.target.value }));
                        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: false }));
                      }}
                    />
                  )}

                  {currentHasChecked && (
                    <div style={{ marginTop: 18, padding: 14, borderRadius: 12, background: '#fafafa', border: '1px solid #f0f0f0' }}>
                      <Text strong style={{ color: currentIsCorrect ? '#52c41a' : '#ff4d4f' }}>
                        {currentIsCorrect ? '回答正确' : '回答错误'}
                      </Text>
                      <div style={{ marginTop: 8 }}><Text strong>正确答案：</Text><Text>{currentQuestion.answer || '-'}</Text></div>
                      <div style={{ marginTop: 6 }}><Text strong>解析：</Text><Text>{currentQuestion.explanation || '暂无解析'}</Text></div>
                    </div>
                  )}
                </div>

                <div style={{ marginTop: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <Button disabled={safeQuizIndex <= 0} onClick={() => goToQuizIndex(safeQuizIndex - 1)}>
                    上一题
                  </Button>
                  <Space size={6} wrap style={{ justifyContent: 'center' }}>
                    {questions.map((item, idx) => {
                      const itemId = String(item.id || idx + 1);
                      const isChecked = !!quizChecked[itemId];
                      return (
                        <Button
                          key={itemId}
                          size="small"
                          shape="circle"
                          type={idx === safeQuizIndex ? 'primary' : 'default'}
                          onClick={() => goToQuizIndex(idx)}
                          style={isChecked && idx !== safeQuizIndex ? { borderColor: '#52c41a', color: '#52c41a' } : undefined}
                        >
                          {idx + 1}
                        </Button>
                      );
                    })}
                  </Space>
                  <Space>
                    <Button
                      type="primary"
                      onClick={() => {
                        if (!currentUserAnswer || !currentUserAnswer.trim()) {
                          message.warning('请先作答后再判题');
                          return;
                        }
                        setQuizChecked((prev) => ({ ...prev, [currentQuestionId]: true }));
                      }}
                    >
                      提交并判题
                    </Button>
                    <Button disabled={safeQuizIndex >= totalCount - 1} onClick={() => goToQuizIndex(safeQuizIndex + 1)}>
                      下一题
                    </Button>
                  </Space>
                </div>
              </Card>
            ) : (
              <Card style={{ borderRadius: 16, textAlign: 'center' }}>
                <Text type="secondary">暂无题目，请重新生成习题。</Text>
              </Card>
            )}
          </div>
        </div>
      );
    }

    // 教学博客预览
    if (viewingFile.type === 'blog') {
      const markdown = typeof viewingFile.content === 'string'
        ? viewingFile.content
        : (viewingFile.content?.markdown || '');

      const outline = Array.isArray(viewingFile.content?.outline) ? viewingFile.content.outline : [];

      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            background: '#ffffff',
            borderRadius: 12,
            padding: 24,
            boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => setViewingFile(null)}
              style={{ marginLeft: -12 }}
            >
              返回
            </Button>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                type="default"
                size="small"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(markdown || '');
                    message.success('已复制Markdown');
                  } catch {
                    message.error('复制失败');
                  }
                }}
              >
                复制Markdown
              </Button>
              <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
            </div>
          </div>

          <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
            {viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />

          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
            {outline.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong>大纲</Text>
                <div style={{ marginTop: 8, padding: 12, background: '#fafafa', borderRadius: 8, border: '1px solid #f0f0f0' }}>
                  {outline.map((sec: any, idx: number) => (
                    <div key={sec?.id || idx} style={{ marginBottom: 6, fontSize: 13, color: '#555' }}>
                      {idx + 1}. {sec?.title || '未命名章节'}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Text strong>正文（Markdown）</Text>
            <div
              style={{
                marginTop: 8,
                padding: 12,
                borderRadius: 8,
                border: '1px solid #f0f0f0',
                background: '#fcfcfc',
                fontSize: 13,
                lineHeight: 1.7,
                overflow: 'auto',
              }}
            >
              {markdown ? (
                <MarkdownPreview content={markdown} />
              ) : (
                <Text type="secondary">（暂无内容）</Text>
              )}
            </div>
          </div>
        </div>
      );
    }

    // 其他类型文件预览
    return (
      <div className="studio-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => setViewingFile(null)}
            style={{ marginLeft: -12 }}
          >
            返回
          </Button>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
        </div>

        <Title level={4} style={{ marginTop: 8, flexShrink: 0 }}>
          {viewingFile.name}
        </Title>
        <Divider style={{ flexShrink: 0 }} />
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <Paragraph>这里是【{viewingFile.name}】的内容预览。TODO: 集成实际内容显示。</Paragraph>
        </div>
      </div>
    );
  }

  // List view
  return (
      <div className="studio-panel">
      <div className="studio-panel__header">
        <div className="studio-panel__heading">
          <Title level={5} className="studio-panel__title">
            生成式工厂
          </Title>
          <div className="studio-panel__subtitle">
            已生成 {visibleGeneratedFiles.length} 份资源
          </div>
        </div>
        <Button
          className="studio-panel__collapse-button"
          type="text"
          icon={<RightOutlined />}
          onClick={onToggleCollapsed}
          aria-label="折叠生成式工厂"
        />
      </div>

      <div className="studio-panel__divider" />

      <ClassroomGenerationEntry courseId={courseId} />

      <ReportEntryModal
        open={reportEntryVisible}
        selectedDocIds={selectedDocs}
        courseId={courseId}
        workspaceScope={normalizedWorkspaceScope}
        submitting={generating}
        onCancel={() => setReportEntryVisible(false)}
        onSubmit={handleReportEntrySubmit}
      />
      <LessonPlanEntryModal
        open={lessonPlanEntryVisible}
        selectedDocIds={selectedDocs}
        courseId={courseId}
        workspaceScope={normalizedWorkspaceScope}
        submitting={generating}
        onCancel={() => setLessonPlanEntryVisible(false)}
        onSubmit={handleLessonPlanEntrySubmit}
      />
      <QuizEntryModal
        open={quizEntryVisible}
        selectedDocIds={selectedDocs}
        courseId={courseId}
        workspaceScope={normalizedWorkspaceScope}
        submitting={generating}
        onCancel={() => setQuizEntryVisible(false)}
        onSubmit={handleQuizEntrySubmit}
      />
      <GameEntryModal
        open={gameEntryVisible}
        selectedDocIds={selectedDocs}
        submitting={generating}
        onCancel={() => setGameEntryVisible(false)}
        onSubmit={handleGameEntrySubmit}
      />
      <Modal
        title="教学博客大纲审查"
        open={blogReviewModalVisible}
        onCancel={() => {
          setBlogReviewModalVisible(false);
        }}
        okText="确认并继续"
        cancelText="取消"
        confirmLoading={blogResuming}
        onOk={async () => {
          if (!blogTaskId) return;
          setBlogResuming(true);
          try {
            const values = await blogOutlineForm.validateFields();
            const outline = Array.isArray(values?.outline) ? values.outline : [];

            const phase = blogTaskStatus?.status;
            if (phase === 'waiting_for_chapter_review') {
              const req: BlogResumeChaptersRequest = { chapters: outline };
              await resumeBlogTaskChapters(blogTaskId, req);
              message.success('已提交章节，正在生成小标题…');
            } else if (phase === 'waiting_for_outline_review') {
              const req: BlogResumeOutlineRequest = { outline };
              await resumeBlogTaskOutline(blogTaskId, req);
              message.success('已提交大纲，继续生成中…');
            } else {
              throw new Error(`当前状态不允许提交: ${phase || '未知'}`);
            }
            setBlogReviewModalVisible(false);
            setBlogPolling(true);
          } catch (e: any) {
            message.error(`提交大纲失败: ${e?.message || '未知错误'}`);
          } finally {
            setBlogResuming(false);
          }
        }}
      >
        <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center' }}>
          <Text type="secondary">
            {blogTaskStatus?.status === 'waiting_for_chapter_review'
              ? '请先审查并确认一级目录（章节）。确认后系统将为每章生成小标题（知识点）。'
              : '请审查并确认二级目录（小标题/知识点）。确认后开始生成正文。'}
          </Text>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Button
              onClick={() => {
                try {
                  const parsed = JSON.parse(blogOutlineDraftText || '[]');
                  const arr = Array.isArray(parsed) ? parsed : [];
                  blogOutlineForm.setFieldsValue({ outline: arr });
                } catch {
                  message.error('JSON 解析失败，无法从文本同步到表单');
                }
              }}
            >
              从 JSON 同步
            </Button>
            <Button
              onClick={() => {
                const arr = blogOutlineForm.getFieldValue('outline-solid') || [];
                try {
                  setBlogOutlineDraftText(JSON.stringify(arr, null, 2));
                } catch {
                  message.error('序列化失败，无法从表单同步到 JSON');
                }
              }}
            >
              同步到 JSON
            </Button>
            <Button
              onClick={() => {
                try {
                  const arr = JSON.parse(blogOutlineOriginalText || '[]');
                  blogOutlineForm.setFieldsValue({ outline: Array.isArray(arr) ? arr : [] });
                } catch {
                  blogOutlineForm.setFieldsValue({ outline: [] });
                }
              }}
            >
              重置
            </Button>
          </div>
        </div>

        <Form form={blogOutlineForm} layout="vertical" initialValues={{ outline: [] }}>
          <Form.List name="outline">
            {(fields, { add, remove }) => (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <Button
                    type="dashed"
                    onClick={() => add({ title: '', key_concepts: [], estimated_word_count: 600 })}
                    icon={<PlusOutlined />}
                    block
                  >
                    新增章节
                  </Button>
                </div>

                {fields.map((field, idx) => (
                  <Card
                    key={field.key}
                    size="small"
                    title={`章节 ${idx + 1}`}
                    extra={
                      <Button danger onClick={() => remove(field.name)}>
                        删除
                      </Button>
                    }
                  >
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px', gap: 12 }}>
                      <Form.Item
                        label="章节标题"
                        name={[field.name, 'title']}
                        rules={[{ required: true, message: '请输入章节标题' }]}
                      >
                        <Input placeholder="例如：TCP 三次握手" />
                      </Form.Item>

                      <Form.Item
                        label="预计字数"
                        name={[field.name, 'estimated_word_count']}
                        rules={[{ required: true, message: '请输入预计字数' }]}
                      >
                        <InputNumber min={100} max={5000} step={50} style={{ width: '100%' }} />
                      </Form.Item>
                    </div>

                    <Form.Item label="章节 ID（可选）" name={[field.name, 'id']}>
                      <Input placeholder="留空将由后端自动补齐" />
                    </Form.Item>

                    {blogTaskStatus?.status !== 'waiting_for_chapter_review' && (
                      <Card size="small" title="小标题（知识点）" style={{ marginTop: 8 }}>
                        <Form.List name={[field.name, 'children']}>
                          {(ptFields, { add: addPt, remove: removePt }) => (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                              <div>
                                <Button
                                  type="dashed"
                                  onClick={() => addPt({ title: '', key_concepts: [], estimated_word_count: 300 })}
                                  icon={<PlusOutlined />}
                                  block
                                >
                                  新增小标题
                                </Button>
                              </div>

                              {ptFields.map((ptField, ptIdx) => (
                                <Card
                                  key={ptField.key}
                                  size="small"
                                  title={`小标题 ${idx + 1}.${ptIdx + 1}`}
                                  extra={
                                    <Button danger onClick={() => removePt(ptField.name)}>
                                      删除
                                    </Button>
                                  }
                                >
                                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px', gap: 12 }}>
                                    <Form.Item
                                      label="小标题"
                                      name={[ptField.name, 'title']}
                                      rules={[{ required: true, message: '请输入小标题' }]}
                                    >
                                      <Input placeholder="例如：什么是三次握手" />
                                    </Form.Item>

                                    <Form.Item
                                      label="预计字数"
                                      name={[ptField.name, 'estimated_word_count']}
                                      rules={[{ required: true, message: '请输入预计字数' }]}
                                    >
                                      <InputNumber min={50} max={2000} step={50} style={{ width: '100%' }} />
                                    </Form.Item>
                                  </div>

                                  <Form.Item label="关键概念" name={[ptField.name, 'key_concepts']}>
                                    <Select
                                      mode="tags"
                                      tokenSeparators={[',', '，']}
                                      placeholder="输入后回车，支持多个"
                                    />
                                  </Form.Item>

                                  <Form.Item label="小标题 ID（可选）" name={[ptField.name, 'id']}>
                                    <Input placeholder="留空将由后端自动补齐" />
                                  </Form.Item>
                                </Card>
                              ))}
                            </div>
                          )}
                        </Form.List>
                      </Card>
                    )}
                  </Card>
                ))}

                <Card size="small" title="JSON 预览">
                  <Input.TextArea
                    value={blogOutlineDraftText}
                    onChange={(e) => setBlogOutlineDraftText(e.target.value)}
                    autoSize={{ minRows: 6, maxRows: 12 }}
                    style={{ fontFamily: 'monospace' }}
                  />
                </Card>
              </div>
            )}
          </Form.List>
        </Form>
      </Modal>

      {blogPolling && blogTaskStatus && (
        <div
          style={{
            marginBottom: 16,
            padding: 12,
            background: '#fafafa',
            borderRadius: 12,
            border: '1px solid #f0f0f0',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Spin size="small" />
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '2px 8px',
                  borderRadius: 6,
                  fontSize: 12,
                  border: `1px solid ${getBlogStatusLabel(blogTaskStatus.status).color}33`,
                  background: `${getBlogStatusLabel(blogTaskStatus.status).color}10`,
                  color: getBlogStatusLabel(blogTaskStatus.status).color,
                }}
              >
                {getBlogStatusLabel(blogTaskStatus.status).text}
              </span>
              <Text type="secondary" style={{ fontSize: 12 }}>
                教学博客生成中…
              </Text>
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {blogTaskStatus.progress?.current_section_idx ?? 0}/{blogTaskStatus.progress?.total_sections ?? 0}
            </Text>
          </div>

          <div style={{ marginTop: 10 }}>
            <Progress
              percent={calcProgressPercent(
                blogTaskStatus.progress?.current_section_idx ?? 0,
                blogTaskStatus.progress?.total_sections ?? 0
              )}
              status="active"
              showInfo
              size="small"
            />
          </div>
        </div>
      )}

      
      {/* 生成入口：按右侧面板宽度自适应为三列、两列或一列 */}
      <div className="studio-panel__summary-card">
        <div className="studio-panel__summary-copy">
          <div className="studio-panel__summary-eyebrow">工作摘要</div>
          <div className="studio-panel__summary-title">从当前知识库快速生成本课时教学产物</div>
          <div className="studio-panel__summary-hint">
            已选 {selectedDocCount} 份资料，已生成 {visibleGeneratedFiles.length} 项内容
          </div>
        </div>
      </div>

      <div className="studio-panel__mode-row">
        <Space size="middle">
          <Space size="small">
            <Text type="secondary">RAG</Text>
            <Switch checked={allowRag} onChange={setAllowRag} />
          </Space>
          <Space size="small">
            <Text type="secondary">Web</Text>
            <Switch checked={allowWeb} onChange={setAllowWeb} />
          </Space>
        </Space>
      </div>

      <div className="studio-panel__section-headline">
        <div>
          <div className="studio-panel__section-title">生成入口</div>
          <div className="studio-panel__section-note">先从高频产物开始，再补充课堂延展内容。</div>
        </div>
      </div>

      <div className="studio-panel__primary-grid">
        {primaryStudioActions.map((item) => (
          <GenerativeCard
            key={item.type}
            icon={item.icon}
            title={item.title}
            description={item.description}
            color={item.color}
            featured
            onGenerate={() => handleGenerate(item.type)}
            onConfigure={() => handleConfigure(item.type)}
          />
        ))}
      </div>

      <div className="studio-panel__divider" />

      <div className="studio-panel__artifact-header">
        <div>
          <div className="studio-panel__section-title">最近产物</div>
          <div className="studio-panel__section-note">生成完成后可在这里继续查看、预览或加入课程资源。</div>
        </div>
        <Space size="small">
          <div className="studio-panel__artifact-count">{visibleGeneratedFiles.length}</div>
          {generatedFiles.filter((file) => String(file.meta?.origin || '').trim() === 'course_material').length < courseMaterialsTotal && (
            <Button type="text" size="small" loading={courseMaterialsLoadingMore} onClick={() => void handleLoadMoreCourseMaterials()}>
              加载更多
            </Button>
          )}
        </Space>
      </div>

      <div className="studio-panel__artifact-list">
        {visibleGeneratedFiles.map((item) => {
          const menuItems: MenuProps['items'] = [
            {
              key: 'add-to-course',
              label: '增加至课程资料',
              icon: <PlusOutlined />,
              onClick: (info) => {
                info.domEvent.stopPropagation();
                handleAddToCourseMaterials(item);
              },
            },
            {
              key: 'delete',
              label: '删除',
              icon: <DeleteOutlined />,
              danger: true,
              onClick: (info) => {
                info.domEvent.stopPropagation();
                removeGeneratedFile(item.id);
              },
            },
          ];

          return (
            <div key={item.id} className="studio-panel__artifact-item">
              <div
                className="studio-panel__artifact-main"
                onClick={() => openGeneratedFile(item)}
              >
                {getGeneratedFileIcon(item)}
                <Text ellipsis={{ tooltip: item.name }} className="studio-panel__artifact-name">
                  {item.name}
                </Text>
              </div>

              <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                <Button className="studio-panel__artifact-action" type="text" icon={<MoreOutlined />} onClick={(e) => e.stopPropagation()} />
              </Dropdown>

              <Tooltip title="查看">
                <Button
                  className="studio-panel__artifact-action"
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    openGeneratedFile(item);
                  }}
                />
              </Tooltip>
            </div>
          );
        })}
        {visibleGeneratedFiles.length === 0 && (
          <div className="studio-panel__empty-state">
            <div className="studio-panel__empty-title">还没有生成内容</div>
            <div className="studio-panel__empty-copy">从上方入口开始，生成后的报告、教案、博客、习题、PPT、闪卡、思维导图和小游戏会集中出现在这里。</div>
          </div>
        )}
      </div>

      {/* 配置参数模态框 */}
      <Modal
        title={`配置${configType === 'audio' ? '音频概览' : configType === 'lesson_plan' ? '教案生成' : configType === 'graph' ? '思维导图' : configType === 'report' ? '报告' : configType === 'blog' ? '教学博客' : '测验'}参数`}
        open={configModalVisible}
        onOk={handleConfigSubmit}
        onCancel={() => {
          setConfigModalVisible(false);
          configForm.resetFields();
        }}
        okText={configType === 'lesson_plan' ? '生成教案' : configType === 'report' ? '生成报告' : configType === 'quiz' ? '生成测验' : '保存配置'}
        cancelText="取消"
        width={600}
        confirmLoading={generating}
      >
        <Form
          form={configForm}
          layout="vertical"
          style={{ marginTop: 24 }}
        >
          {configType === 'report' ? (
            <>
              <Form.Item
                label="报告标题（可选）"
                name="title"
                tooltip="不填写则根据文档内容自动生成标题"
              >
                <Input placeholder="请输入报告标题，留空则自动生成" />
              </Form.Item>
              <Form.Item
                label="重点关注领域（可选）"
                name="focus_areas"
                tooltip="指定需要特别关注的领域，用逗号分隔"
              >
                <Select
                  mode="tags"
                  placeholder="输入重点关注领域，按回车添加"
                  tokenSeparators={[',']}
                />
              </Form.Item>
              <div style={{ marginTop: 16, padding: 12, background: '#f0f0f0', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  💡 提示：报告将基于您选中的文档完整内容生成，结构清晰且非常详细。请确保已选择至少一个文档。
                </Text>
              </div>
            </>
          ) : configType === 'lesson_plan' ? (
            <>
              <Form.Item
                label="教学主题"
                name="topic"
                rules={[{ required: true, message: '请输入教学主题' }]}
              >
                <Input placeholder="请输入教学主题" />
              </Form.Item>
              <Form.Item
                label="课时长度（分钟）"
                name="duration"
                initialValue={45}
              >
                <Input type="number" min={10} max={180} placeholder="默认45分钟" />
              </Form.Item>
              <Form.Item
                label="教学难度"
                name="difficulty"
                initialValue="medium"
              >
                <Select>
                  <Select.Option value="low">低</Select.Option>
                  <Select.Option value="medium">中</Select.Option>
                  <Select.Option value="high">高</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item
                label="知识点（可选）"
                name="knowledge_points"
                tooltip="输入知识点，用逗号分隔"
              >
                <Select
                  mode="tags"
                  placeholder="输入知识点，按回车添加"
                  tokenSeparators={[',']}
                />
              </Form.Item>
              <Form.Item
                label="教学重点（可选）"
                name="key_points"
              >
                <Input.TextArea rows={2} placeholder="请输入教学重点" />
              </Form.Item>
              <Form.Item
                label="教学难点（可选）"
                name="hard_points"
              >
                <Input.TextArea rows={2} placeholder="请输入教学难点" />
              </Form.Item>
              <div style={{ marginTop: 16, padding: 12, background: '#f0f0f0', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  💡 提示：教案将基于您选中的文档完整内容生成。其他配置项为可选，留空时将由模型根据文档内容自行确定。
                </Text>
              </div>
            </>
          ) : (
            <>
              <Form.Item
                label="生成主题"
                name="topic"
                rules={[{ required: true, message: '请输入生成主题' }]}
              >
                <Input placeholder="请输入要生成的内容主题" />
              </Form.Item>
              
              <Form.Item
                label="详细描述"
                name="description"
              >
                <Input.TextArea 
                  rows={4} 
                  placeholder="请描述生成内容的详细要求（可选）"
                />
              </Form.Item>

              {configType === 'quiz' && (
                <>
                  <Form.Item
                    label="题目类型"
                    name="question_type"
                    initialValue="mixed"
                    rules={[{ required: true, message: '请选择题目类型' }]}
                  >
                    <Select>
                      <Select.Option value="choice">选择题</Select.Option>
                      <Select.Option value="blank">填空题</Select.Option>
                      <Select.Option value="mixed">混合题型</Select.Option>
                    </Select>
                  </Form.Item>
                  <Form.Item
                    label="题目数量（5-20）"
                    name="count"
                    initialValue={10}
                    rules={[{ required: true, message: '请输入题目数量' }]}
                  >
                    <InputNumber min={5} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item
                    label="难易度"
                    name="difficulty"
                    initialValue="medium"
                    rules={[{ required: true, message: '请选择难易度' }]}
                  >
                    <Select>
                      <Select.Option value="easy">简单</Select.Option>
                      <Select.Option value="medium">中等</Select.Option>
                      <Select.Option value="hard">困难</Select.Option>
                    </Select>
                  </Form.Item>
                </>
              )}

              {configType === 'audio' && (
                <Form.Item
                  label="音频时长（分钟）"
                  name="duration"
                  initialValue={5}
                >
                  <Input type="number" min={1} max={30} />
                </Form.Item>
              )}

              {configType === 'graph' && (
                <Form.Item
                  label="导图层级"
                  name="levels"
                  initialValue={3}
                >
                  <Input type="number" min={2} max={5} />
                </Form.Item>
              )}

              {configType === 'blog' && (
                <Form.Item
                  label="博客长度"
                  name="length"
                  initialValue="medium"
                >
                  <Select>
                    <Select.Option value="short">短篇（500-1000字）</Select.Option>
                    <Select.Option value="medium">中篇（1000-2000字）</Select.Option>
                    <Select.Option value="long">长篇（2000-3000字）</Select.Option>
                  </Select>
                </Form.Item>
              )}
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default StudioPanel;
