import React, { useState, useEffect } from 'react';
import { Button, Divider, Dropdown, Space, Tooltip, Typography, Modal, Form, Input, Select, message, Progress, Spin, Card, InputNumber, Radio, Switch } from 'antd';
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
  generateLessonPlan,
  generateQuiz,
  getCourseMaterials,
  resumeBlogTaskChapters,
  resumeBlogTaskOutline,
  startBlogGenerate,
  getBlogTaskStatus,
  type BlogResumeChaptersRequest,
  type BlogResumeOutlineRequest,
  type BlogTaskStatusResponse,
  type LessonPlanRequest,
  type LessonPlanResponse,
  type QuizRequest,
  type QuizResponse,
  type ReportResponse,
} from '../../services/teacher/api';
import { sendReportV2 } from '../../services/teacher/chatV2';
import { buildReportQuestionFromConfig, extractGeneratedFilesFromV2Response } from '../../services/teacher/chatV2.helpers';

import MarkdownPreview from '../shared/MarkdownPreview';

const { Title, Text, Paragraph } = Typography;

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

const calcProgressPercent = (current: number, total: number) => {
  if (!total || total <= 0) return 0;
  const v = Math.floor((Math.max(0, current) / total) * 100);
  return Math.max(0, Math.min(100, v));
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

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  onPreviewStateChange?: (open: boolean) => void;
};

const getGeneratedFileIcon = (file: GeneratedFile, size = 20) => {
  switch (file.type) {
    case 'report':
      return <FileMarkdownOutlined style={{ fontSize: size, color: '#555' }} />;
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
  color: string;
  onGenerate: () => void;
  onConfigure: () => void;
}

const GenerativeCard: React.FC<GenerativeCardProps> = ({ icon, title, color, onGenerate, onConfigure }) => {
  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: `linear-gradient(135deg, ${color}15 0%, ${color}08 100%)`,
        borderRadius: '24px',
        border: `1px solid ${color}30`,
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        minHeight: 56,
      }}
      onClick={onGenerate}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${color}25 0%, ${color}15 100%)`;
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = `0 4px 12px ${color}30`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = `linear-gradient(135deg, ${color}15 0%, ${color}08 100%)`;
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
        <div style={{ fontSize: 20, color: color }}>
          {icon}
        </div>
        <Text strong style={{ fontSize: 14, color: '#1e293b' }}>
          {title}
        </Text>
      </div>
      <Button
        type="text"
        icon={<EditOutlined />}
        size="small"
        onClick={(e) => {
          e.stopPropagation();
          onConfigure();
        }}
        style={{
          color: color,
          padding: '4px 8px',
          minWidth: 'auto',
        }}
      />
    </div>
  );
};

const StudioPanel: React.FC<Props> = ({ collapsed, onToggleCollapsed, courseId, onPreviewStateChange }) => {
  const {
    generatedFiles,
    viewingFile,
    addGeneratedFile,
    removeGeneratedFile,
    setViewingFile,
    selectedDocs,
    currentConversationId,
    setCurrentConversationId,
    allowRag,
    allowWeb,
    setAllowRag,
    setAllowWeb,
    setStatusCard,
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

  const [blogOutlineForm] = Form.useForm();

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
                const materials = await getCourseMaterials(courseId);
                const courseMaterials = materials.map((item) => ({
                  id: item.id,
                  name: item.name,
                  type: item.type as any,
                  content: item.content,
                  addedAt: item.addedAt,
                  courseId: item.courseId || courseId,
                }));
                useCourseMaterialsStore.getState().setMaterials(courseMaterials as any);
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
  }, [blogPolling, blogTaskId, courseId, addGeneratedFile, setViewingFile, addMaterial]);

  const [configForm] = Form.useForm();
  const [generating, setGenerating] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizChecked, setQuizChecked] = useState<Record<string, boolean>>({});

  const handleGenerate = async (type: GeneratedFile['type'] | string) => {
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

  const handleConfigure = (type: string) => {
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

  const handleConfigSubmit = async () => {
    try {
      const values = await configForm.validateFields();
      
      // 如果是教案生成，调用后端API
      if (configType === 'lesson_plan') {
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
          
          const request: LessonPlanRequest = {
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
          const response = await generateLessonPlan(request);
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
          
          message.success('教案生成成功！已自动保存到教学资源');
          setConfigModalVisible(false);
          configForm.resetFields();
        } catch (error: any) {
          message.error(`生成教案失败: ${error.message || '未知错误'}`);
        } finally {
          setGenerating(false);
        }
      } else if (configType === 'report') {
        setGenerating(true);
        try {
          const focusAreas = Array.isArray(values.focus_areas)
            ? values.focus_areas
            : values.focus_areas
              ? [values.focus_areas]
              : [];
          const response = await sendReportV2({
            question: buildReportQuestionFromConfig({
              title: values.title || undefined,
              focus_areas: focusAreas,
            }),
            conversation_id: currentConversationId || undefined,
            course_id: courseId,
            allow_rag: allowRag,
            allow_web: allowWeb,
            selected_doc_ids: selectedDocs,
            report_config: {
              title: values.title || undefined,
              focus_areas: focusAreas,
            },
          });

          const nextConversationId = String(response.conversation?.conversation_id || '').trim();
          if (nextConversationId && nextConversationId !== currentConversationId) {
            setCurrentConversationId(nextConversationId);
          }
          setStatusCard(response.status_card || null);

          const generatedReportFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
            ...file,
            meta: {
              ...(file.meta || {}),
              conversationId: nextConversationId || currentConversationId,
            },
          }));

          generatedReportFiles.forEach((file) => addGeneratedFile(file));

          if (generatedReportFiles.length > 0) {
            const latestFile = generatedReportFiles[generatedReportFiles.length - 1];
            setViewingFile(latestFile);

            if (courseId) {
              addMaterial({
                ...latestFile,
                addedAt: new Date().toISOString(),
                courseId,
              });
            }
          }

          message.success(generatedReportFiles.length > 0 ? 'Report is ready in the side panel.' : 'Report workflow started.');
          setConfigModalVisible(false);
          configForm.resetFields();
        } catch (error: any) {
          message.error(`Report generation failed: ${error.message || 'Unknown error'}`);
        } finally {
          setGenerating(false);
        }
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
  if (collapsed) {
    // 功能类型定义
    const functionTypes = [
      { type: 'audio' as const, icon: <AudioOutlined />, color: '#722ed1' },
      { type: 'lesson_plan' as const, icon: <BookOutlined />, color: '#52c41a' },
      { type: 'graph' as const, icon: <ApartmentOutlined />, color: '#eb2f96' },
      { type: 'report' as const, icon: <FileTextOutlined />, color: '#faad14' },
      { type: 'blog' as const, icon: <EditOutlined />, color: '#ff7875' },
      { type: 'quiz' as const, icon: <QuestionCircleOutlined />, color: '#1890ff' },
    ];

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
          {functionTypes.map((func) => (
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
                onClick={() => setViewingFile(f)}
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
    // 教案预览
    if (viewingFile.type === 'lesson_plan' && viewingFile.content) {
      const plan = viewingFile.content as LessonPlanResponse;
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
            {plan.title || viewingFile.name}
          </Title>
          <Divider style={{ flexShrink: 0 }} />
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
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
        </div>
      );
    }

    // 报告预览
    if (viewingFile.type === 'report' && viewingFile.content) {
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
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
              <MarkdownPreview content={viewingFile.content} />
            </div>
            {(viewingFile as any)?.meta?.kind === 'outline' && (
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

          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingRight: 8 }}>
            {questions.map((q, idx) => {
              const userAnswer = quizAnswers[q.id] || '';
              const hasChecked = !!quizChecked[q.id];
              const isCorrect = hasChecked && isQuizAnswerCorrect(q, userAnswer);

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

                    {hasChecked && (
                      <Text style={{ color: isCorrect ? '#52c41a' : '#ff4d4f' }}>
                        {isCorrect ? '回答正确' : '回答错误'}
                      </Text>
                    )}
                  </div>

                  {hasChecked && (
                    <div style={{ marginTop: 10, padding: 10, borderRadius: 8, background: '#fafafa', border: '1px solid #f0f0f0' }}>
                      <div><Text strong>正确答案：</Text><Text>{q.answer || '-'}</Text></div>
                      <div style={{ marginTop: 6 }}><Text strong>解析：</Text><Text>{q.explanation || '暂无解析'}</Text></div>
                    </div>
                  )}
                </Card>
              );
            })}
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
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <Paragraph>这里是【{viewingFile.name}】的内容预览。TODO: 集成实际内容显示。</Paragraph>
        </div>
      </div>
    );
  }

  // List view
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexShrink: 0 }}>
        <Title level={5} style={{ margin: 0, fontWeight: 600 }}>
          生成式工场
        </Title>
        <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="折叠工作室" />
      </div>

      <Text type="secondary" style={{ flexShrink: 0, marginBottom: 16, display: 'block' }}>点击生成</Text>

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
                const arr = blogOutlineForm.getFieldValue('outline') || [];
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

      
      {/* 六个功能：两行，每行三个 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginBottom: 12,
          flexShrink: 0,
        }}
      >
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


      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(3, 1fr)', 
        gap: 12, 
        marginBottom: 16,
        flexShrink: 0 
      }}>
        {/* 第一行 */}
        <GenerativeCard
          icon={<AudioOutlined />}
          title="音频概览"
          color="#722ed1"
          onGenerate={() => handleGenerate('audio')}
          onConfigure={() => handleConfigure('audio')}
        />
        <GenerativeCard
          icon={<BookOutlined />}
          title="教案生成"
          color="#52c41a"
          onGenerate={() => handleGenerate('lesson_plan')}
          onConfigure={() => handleConfigure('lesson_plan')}
        />
        <GenerativeCard
          icon={<ApartmentOutlined />}
          title="思维导图"
          color="#eb2f96"
          onGenerate={() => handleGenerate('graph')}
          onConfigure={() => handleConfigure('graph')}
        />
        
        {/* 第二行 */}
        <GenerativeCard
          icon={<FileTextOutlined />}
          title="报告"
          color="#faad14"
          onGenerate={() => handleGenerate('report')}
          onConfigure={() => handleConfigure('report')}
        />
        <GenerativeCard
          icon={<EditOutlined />}
          title="教学博客"
          color="#ff7875"
          onGenerate={() => handleGenerate('blog')}
          onConfigure={() => handleConfigure('blog')}
        />
        <GenerativeCard
          icon={<QuestionCircleOutlined />}
          title="测验"
          color="#1890ff"
          onGenerate={() => handleGenerate('quiz')}
          onConfigure={() => handleConfigure('quiz')}
        />
      </div>
      <Divider style={{ margin: '12px 0', flexShrink: 0 }} />

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {generatedFiles.map((item) => {
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
            <div key={item.id} style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '8px 0' }}>
              <div
                style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0, cursor: 'pointer' }}
                onClick={() => setViewingFile(item)}
              >
                {getGeneratedFileIcon(item)}
                <Text ellipsis={{ tooltip: item.name }} style={{ marginLeft: 12 }}>
                  {item.name}
                </Text>
              </div>

              <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                <Button type="text" icon={<MoreOutlined />} onClick={(e) => e.stopPropagation()} />
              </Dropdown>

              <Tooltip title="查看">
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setViewingFile(item);
                  }}
                />
              </Tooltip>
            </div>
          );
        })}
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
