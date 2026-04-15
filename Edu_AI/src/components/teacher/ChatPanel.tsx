import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Input, Button, List, Space, Typography, Tag, Tooltip, message, Empty, Spin, Modal, Popover, Switch } from 'antd';
import { SendOutlined, SnippetsOutlined, HistoryOutlined, DeleteOutlined, AudioOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';
import { listChatConversations, getChatConversationDetail, deleteChatConversation, type ConversationListItem } from '../../services/teacher/api';
import { buildChatReplyPayload, sendChatReplyV2, transcribeSpeechV2 } from '../../services/teacher/chatV2';
import { resolveSpeechInputError } from '../../services/teacher/speechInput';
import { extractGeneratedFilesFromV2Response, restoreGeneratedFilesFromConversationDetail } from '../../services/teacher/chatV2.helpers';
import ReactMarkdown from 'react-markdown';
import { type RAGSource } from '../../services/rag';
import StatusCard from './StatusCardV2';

const { TextArea } = Input;
const { Title, Text } = Typography;

function buildSpeechFileName(mimeType: string): string {
  if (mimeType.includes('mp4')) return 'voice.mp4';
  if (mimeType.includes('mpeg')) return 'voice.mp3';
  if (mimeType.includes('ogg')) return 'voice.ogg';
  if (mimeType.includes('wav')) return 'voice.wav';
  return 'voice.webm';
}

function appendTranscript(previous: string, transcript: string): string {
  const normalizedTranscript = String(transcript || '').trim();
  if (!normalizedTranscript) {
    return previous;
  }
  if (!previous.trim()) {
    return normalizedTranscript;
  }
  return `${previous.trimEnd()} ${normalizedTranscript}`;
}

interface Message {
  user: 'You' | 'AI';
  text: string;
  sources?: any[];
  statusText?: string;
}

interface ChatPanelProps {
  courseId?: string;
}

const normalizeArtifactReferenceType = (
  value: unknown,
): 'report' | 'report_outline' | 'ppt_outline' | 'ppt_content_markdown' | 'ppt_deck' => {
  const artifactType = String(value || '').trim();
  if (
    artifactType === 'report_outline'
    || artifactType === 'ppt_outline'
    || artifactType === 'ppt_content_markdown'
    || artifactType === 'ppt_deck'
  ) {
    return artifactType;
  }
  return 'report';
};

const ChatPanel: React.FC<ChatPanelProps> = ({ courseId }) => {
  const {
    messages,
    addMessage,
    setMessages,
    updateLastMessage,
    selectedDocs,
    allowRag,
    allowWeb,
    setAllowRag,
    setAllowWeb,
    setHighlightRequest,
    currentConversationId,
    setCurrentConversationId,
    queuedMessage,
    setQueuedMessage,
    artifactReference,
    conversationReference,
    setArtifactReference,
    clearArtifactReference,
    setConversationReference,
    clearConversationReference,
    addGeneratedFile,
    replaceConversationGeneratedFiles,
    clearConversationGeneratedFiles,
    removeGeneratedFilesByConversationId,
    setViewingFile,
    statusCard,
    setStatusCard,
  } = useStore();
  const { addMaterial } = useCourseMaterialsStore();

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [historyList, setHistoryList] = useState<ConversationListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<string | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPopoverOpen, setHistoryPopoverOpen] = useState(false);
  const [workflowType, setWorkflowType] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
      mediaStreamRef.current = null;
      audioChunksRef.current = [];
    };
  }, []);

  useEffect(() => {
    const init = async () => {
      setHistoryLoading(true);
      try {
        const result = await listChatConversations();
        const list = result.conversations || [];
        setHistoryList(list);

        const storedConversationId = String(currentConversationId || '').trim();
        const storedConversationExists = storedConversationId
          ? list.some((item) => item.conversation_id === storedConversationId)
          : false;

        if (storedConversationExists) {
          await loadConversation(storedConversationId, false);
        } else if (list.length > 0) {
          setCurrentConversationId(list[0].conversation_id);
          await loadConversation(list[0].conversation_id, false);
        }
      } catch (error) {
        console.error('加载历史对话失败:', error);
      } finally {
        setHistoryLoading(false);
      }
    };

    void init();
  }, []);

  const refreshHistoryList = async () => {
    try {
      const result = await listChatConversations();
      setHistoryList(result.conversations || []);
    } catch (error) {
      console.error('刷新历史对话失败:', error);
    }
  };

  const loadConversation = async (conversationId: string, showSuccess = true, silent = false) => {
    if (!silent) {
      setLoadingConversationId(conversationId);
    }
    try {
      const detail = await getChatConversationDetail(conversationId);
      const mapped: Message[] = (detail.history || []).map((msg: any) => ({
        user: msg.role === 'assistant' ? 'AI' : 'You',
        text: msg.content || '',
        sources: (msg.sources || []) as any[],
      }));
      const detailWorkflowState = detail?.state?.workflow_state;
      const nextWorkflowType = String((detailWorkflowState as any)?.workflow_type || '').trim();
      const nextWorkflowStatus = String((detailWorkflowState as any)?.status || '').trim();

      setMessages(mapped);
      setCurrentConversationId(detail.conversation_id);
      setStatusCard(detail.status_card || null);
      setWorkflowType(nextWorkflowType || null);
      setWorkflowStatus(nextWorkflowStatus || null);
      const restoredFiles = restoreGeneratedFilesFromConversationDetail(detail);
      replaceConversationGeneratedFiles(restoredFiles);
      const stateArtifactReference = detail?.state?.artifact_reference;
      if (stateArtifactReference && typeof stateArtifactReference === 'object') {
        setArtifactReference({
          artifact_id: String((stateArtifactReference as any).artifact_id || '').trim(),
          artifact_type: normalizeArtifactReferenceType((stateArtifactReference as any).artifact_type),
          version_id: String((stateArtifactReference as any).version_id || '').trim() || undefined,
          title: String((stateArtifactReference as any).title || '').trim() || undefined,
          source_conversation_id: String((stateArtifactReference as any).source_conversation_id || detail.conversation_id || '').trim() || undefined,
          source_course_id: String((stateArtifactReference as any).source_course_id || courseId || '').trim() || undefined,
        });
      } else {
        clearArtifactReference();
      }
      const stateConversationReference = detail?.state?.conversation_reference;
      if (stateConversationReference && typeof stateConversationReference === 'object') {
        setConversationReference({
          conversation_id: String((stateConversationReference as any).conversation_id || '').trim(),
          title: String((stateConversationReference as any).title || '').trim() || undefined,
          message_count:
            typeof (stateConversationReference as any).message_count === 'number'
              ? (stateConversationReference as any).message_count
              : undefined,
        });
      } else {
        clearConversationReference();
      }
      if (silent && nextWorkflowType === 'ppt' && nextWorkflowStatus === 'completed' && restoredFiles.length > 0) {
        setViewingFile(restoredFiles[restoredFiles.length - 1]);
      } else if (!silent) {
        setViewingFile(null);
      }

      if (showSuccess && !silent) {
        message.success('已切换到历史对话');
      }
    } catch (error: any) {
      console.error('加载对话详情失败:', error);
      if (!silent) {
        message.error(error?.message || '加载历史对话失败');
      }
    } finally {
      if (!silent) {
        setLoadingConversationId(null);
      }
    }
  };

  const handleNewConversation = () => {
    setMessages([]);
    setCurrentConversationId(null);
    setInputValue('');
    setStatusCard(null);
    setWorkflowType(null);
    setWorkflowStatus(null);
    clearArtifactReference();
    clearConversationReference();
    clearConversationGeneratedFiles();
    setViewingFile(null);
    message.success('已新建对话');
  };

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      await deleteChatConversation(conversationId);

      const nextHistory = historyList.filter((item) => item.conversation_id !== conversationId);
      setHistoryList(nextHistory);
      removeGeneratedFilesByConversationId(conversationId);

      if (currentConversationId === conversationId) {
        if (nextHistory.length > 0) {
          await loadConversation(nextHistory[0].conversation_id, false);
        } else {
          setMessages([]);
          setCurrentConversationId(null);
          setStatusCard(null);
          setWorkflowType(null);
          setWorkflowStatus(null);
          clearArtifactReference();
          clearConversationReference();
          setViewingFile(null);
        }
      }

      message.success('历史对话已删除');
    } catch (error: any) {
      console.error('删除对话失败:', error);
      message.error(error?.message || '删除历史对话失败');
    }
  };

  const transcribeAudioFile = async (file: Blob, filename: string) => {
    try {
      setIsTranscribing(true);
      const result = await transcribeSpeechV2(file, filename);
      setInputValue((previous) => appendTranscript(previous, result.text));
      message.success('语音已转换为文本');
    } catch (error: any) {
      console.error('speech transcription error:', error);
      message.error(error?.message || '语音识别失败');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleVoiceInput = async () => {
    if (isTranscribing) {
      return;
    }

    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    if (typeof window === 'undefined' || !window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      message.error('当前浏览器不支持语音输入');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });

        mediaRecorderRef.current = null;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        audioChunksRef.current = [];

        if (audioBlob.size === 0) {
          message.warning('未录到有效语音内容');
          return;
        }

        void transcribeAudioFile(audioBlob, buildSpeechFileName(mimeType));
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error: any) {
      console.error('start recording error:', error);
      const resolution = resolveSpeechInputError(error);
      message.error(resolution.message);
    }
  };

  const handleSendMessage = async (overrideText?: string, forceSend = false) => {
    const draft = (overrideText ?? inputValue).trim();
    if (draft === '' || (isLoading && !forceSend)) return;

    const userMessage: Message = { user: 'You', text: draft };
    addMessage(userMessage);
    setInputValue('');
    setIsLoading(true);
    setQueuedMessage(null);

    const aiResponse: Message = { user: 'AI', text: '', statusText: 'Thinking...' };
    addMessage(aiResponse);

    try {
      const response = await sendChatReplyV2(
        buildChatReplyPayload({
          question: userMessage.text,
          conversationId: currentConversationId,
          courseId,
          allowRag,
          allowWeb,
          selectedDocIds: selectedDocs,
          artifactReference,
          conversationReference,
        }),
      );

      const nextConversationId = String(response.conversation?.conversation_id || '').trim();
      if (nextConversationId && nextConversationId !== currentConversationId) {
        setCurrentConversationId(nextConversationId);
      }
      setStatusCard(response.status_card || null);
      setWorkflowType(String(response.workflow?.type || '').trim() || null);
      setWorkflowStatus(String(response.workflow?.status || '').trim() || null);

      const sources = Array.isArray(response.sources) ? (response.sources as unknown as RAGSource[]) : [];
      const generatedFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
        ...file,
        meta: {
          ...(file.meta || {}),
          origin: 'conversation',
          conversationId: nextConversationId || currentConversationId,
        },
      }));

      generatedFiles.forEach((file) => addGeneratedFile(file));
      const nextPptArtifact = generatedFiles.find((file) => file.meta?.kind === 'ppt_deck');
      if (artifactReference?.artifact_type === 'ppt_deck' && nextPptArtifact) {
        setArtifactReference({
          artifact_id: String(nextPptArtifact.meta?.originalArtifactId || nextPptArtifact.id).trim(),
          artifact_type: 'ppt_deck',
          title: nextPptArtifact.name,
          source_conversation_id: String(
            nextPptArtifact.meta?.conversationId || nextConversationId || currentConversationId || '',
          ).trim() || undefined,
          source_course_id: String(courseId || '').trim() || undefined,
        });
      }
      if (courseId) {
        generatedFiles.forEach((file) =>
          addMaterial({
            id: file.id,
            name: file.name,
            type: file.type,
            content: file.content,
            addedAt: String(file.meta?.addedAt || new Date().toISOString()),
            courseId,
            isPinned: Boolean(file.meta?.isPinned),
            pinnedAt: typeof file.meta?.pinnedAt === 'string' ? file.meta.pinnedAt : undefined,
          } as any),
        );
      }
      if (generatedFiles.length > 0) {
        setViewingFile(generatedFiles[generatedFiles.length - 1]);
      }

      const hasFinalReport = generatedFiles.some((file) => file.meta?.kind === 'final_report');
      const replyText = hasFinalReport ? '已生成，请在右侧查看。' : String(response.message?.content || '');

      updateLastMessage({
        text: replyText,
        sources,
        statusText: '',
      });

      await refreshHistoryList();
    } catch (error: any) {
      console.error('v2 reply error:', error);
      updateLastMessage({
        text: error?.message || 'Request failed. Please try again.',
        statusText: 'Failed',
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!queuedMessage || isLoading) return;
    void handleSendMessage(queuedMessage, true);
  }, [queuedMessage, isLoading]);

  useEffect(() => {
    if (!currentConversationId || workflowType !== 'ppt' || workflowStatus !== 'running') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadConversation(currentConversationId, false, true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [currentConversationId, workflowStatus, workflowType]);

  const handleSuggestedAction = (action: string) => {
    const normalized = String(action || '').trim();
    const actionPromptMap: Record<string, string> = {
      生成报告: '请基于当前内容生成一份报告。',
      继续生成: '请继续生成。',
      确认并继续: '确认并继续。',
      调整要求: '我想调整要求：',
      选择资料: '我准备先补充资料。',
      跳过资料直接生成: '跳过资料，直接继续生成。',
      继续提问: '',
    };
    setInputValue(actionPromptMap[normalized] ?? normalized);
  };

  const handleSourceClick = (source: any) => {
    const path =
      source?.source_path ||
      source?.sourcePath ||
      source?.source ||
      source?.source_path_encoded ||
      source?.source_path_raw;

    if (!path) return;

    setHighlightRequest({
      filePath: path,
      source: source as RAGSource,
    });
  };

  const visibleHistoryList = useMemo(() => {
    return historyExpanded ? historyList : historyList.slice(0, 7);
  }, [historyExpanded, historyList]);

  const historyContent = (
    <div style={{ width: 360, maxHeight: 420, overflowY: 'auto' }}>
      {historyLoading ? (
        <div style={{ padding: 16, textAlign: 'center' }}>
          <Spin size="small" /> <Text style={{ marginLeft: 8 }}>加载中...</Text>
        </div>
      ) : historyList.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史对话" />
      ) : (
        <>
          {visibleHistoryList.map((item) => (
            <div
              key={item.conversation_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 4px',
                borderBottom: '1px solid #f5f5f5',
              }}
            >
              <Button
                type="text"
                onClick={() => {
                  void loadConversation(item.conversation_id);
                  setHistoryPopoverOpen(false);
                  setHistoryExpanded(false);
                }}
                style={{ flex: 1, textAlign: 'left', height: 'auto', padding: '4px 8px' }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.title || '未命名对话'}
                  </div>
                  <div style={{ fontSize: 12, color: '#999' }}>{item.message_count || 0} 条消息</div>
                </div>
              </Button>

              {loadingConversationId === item.conversation_id && <Spin size="small" />}

              <Button
                type="text"
                size="small"
                icon={<SnippetsOutlined />}
                disabled={item.conversation_id === currentConversationId}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setConversationReference({
                    conversation_id: item.conversation_id,
                    title: item.title || undefined,
                    message_count: item.message_count,
                  });
                  setHistoryPopoverOpen(false);
                  setHistoryExpanded(false);
                  message.success('已引用历史对话');
                }}
              >
                引用
              </Button>

              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  Modal.confirm({
                    title: '确认删除该历史对话？',
                    content: '删除后不可恢复。',
                    okText: '删除',
                    cancelText: '取消',
                    okButtonProps: { danger: true },
                    onOk: async () => {
                      await handleDeleteConversation(item.conversation_id);
                    },
                  });
                }}
              />
            </div>
          ))}

          {!historyExpanded && historyList.length > 7 && (
            <div style={{ paddingTop: 8, textAlign: 'center' }}>
              <Button
                type="text"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setHistoryExpanded(true);
                }}
              >
                ...
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#ffffff',
        borderRadius: '12px',
        padding: '24px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexShrink: 0 }}>
        <Title level={5} style={{ margin: 0, fontWeight: 600 }}>
          对话
        </Title>

        <Space>
          <Space size="small" style={{ marginRight: 8 }}>
            <Text type="secondary">RAG</Text>
            <Switch checked={allowRag} onChange={setAllowRag} />
            <Text type="secondary">Web</Text>
            <Switch checked={allowWeb} onChange={setAllowWeb} />
          </Space>
          <Button onClick={handleNewConversation}>新建对话</Button>
          <Popover
            trigger="click"
            placement="bottomLeft"
            content={historyContent}
            open={historyPopoverOpen}
            onOpenChange={(open) => {
              setHistoryPopoverOpen(open);
              if (!open) {
                setHistoryExpanded(false);
              }
            }}
          >
            <Button icon={<HistoryOutlined />}>历史对话</Button>
          </Popover>
        </Space>
      </div>

      <StatusCard statusCard={statusCard} onActionSelect={handleSuggestedAction} />

      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '20px', padding: '0 12px', minHeight: 0 }}>
        <List
          dataSource={messages}
          renderItem={(item, index) => (
            <List.Item
              key={index}
              style={{
                border: 'none',
                display: 'flex',
                flexDirection: 'column',
                alignItems: item.user === 'You' ? 'flex-end' : 'flex-start',
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start',
                  flexDirection: item.user === 'You' ? 'row-reverse' : 'row',
                  maxWidth: '100%',
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: item.user === 'You' ? '#1677ff' : '#6f42c1',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 14,
                    flexShrink: 0,
                    boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                  }}
                >
                  {item.user === 'You' ? '我' : 'AI'}
                </div>
                <div style={{ maxWidth: '80%' }}>
                  {item.user === 'AI' && item.statusText && (
                    <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
                      {item.statusText}
                    </div>
                  )}
                  <div
                    style={{
                      padding: '10px 15px',
                      borderRadius: '18px',
                      background: item.user === 'You' ? '#1677ff' : '#f0f0f0',
                      color: item.user === 'You' ? 'white' : 'black',
                      width: 'fit-content',
                      maxWidth: 'min(80vw, 720px)',
                      wordBreak: 'normal',
                      overflowWrap: 'break-word',
                    }}
                  >
                    {item.user === 'AI' ? (
                      <ReactMarkdown
                        components={{
                          p: ({ children }) => (
                            <p style={{ margin: 0, whiteSpace: 'normal', wordBreak: 'normal' }}>
                              {children}
                            </p>
                          ),
                        }}
                      >
                        {item.text}
                      </ReactMarkdown>
                    ) : (
                      <div style={{ whiteSpace: 'pre-wrap' }}>{item.text}</div>
                    )}
                  </div>

                  {item.user === 'AI' && item.sources && item.sources.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Space wrap size={[0, 8]}>
                        {item.sources.map((source, i) => {
                          const isImage = String((source as any)?.modality || '').toLowerCase() === 'image';
                          const imageUrl = (source as any)?.image_url as string | undefined;
                          const imageTitle = (source as any)?.image_name || source?.source || `图片来源 ${i + 1}`;
                          return (
                            <Tooltip
                              key={i}
                              title={source?.content ? `来源片段: ${String(source.content).substring(0, 100)}...` : '无片段'}
                            >
                              <Tag
                                icon={<SnippetsOutlined />}
                                color={isImage ? 'purple' : 'blue'}
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  handleSourceClick(source);
                                }}
                                onMouseDown={(e) => {
                                  e.preventDefault();
                                }}
                                style={{ cursor: 'pointer', userSelect: 'none' }}
                              >
                                {isImage ? `图片 · ${source?.source || `来源 ${i + 1}`}` : (source?.source || `来源 ${i + 1}`)}
                              </Tag>
                              {isImage && imageUrl && (
                                <div style={{ marginTop: 8, marginBottom: 4 }}>
                                  <img
                                    src={imageUrl}
                                    alt={String((source as any)?.image_alt || imageTitle || '图片上下文')}
                                    style={{ maxWidth: 220, maxHeight: 140, borderRadius: 8, border: '1px solid #eee' }}
                                  />
                                </div>
                              )}
                            </Tooltip>
                          );
                        })}
                      </Space>
                    </div>
                  )}
                </div>
              </div>
            </List.Item>
          )}
        />
        <div ref={chatEndRef} />
      </div>

      {conversationReference ? (
        <div
          style={{
            marginBottom: 8,
            padding: '8px 12px',
            border: '1px solid #d9d9d9',
            borderRadius: 8,
            background: '#fafafa',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <Text strong>{conversationReference.title || '已引用对话'}</Text>
            <div>
              <Text type="secondary">
                历史对话
                {typeof conversationReference.message_count === 'number'
                  ? ` · ${conversationReference.message_count} 条消息`
                  : ''}
              </Text>
            </div>
          </div>
          <Button size="small" onClick={() => clearConversationReference()}>
            移除引用
          </Button>
        </div>
      ) : null}

      {artifactReference ? (
        <div
          style={{
            marginBottom: 8,
            padding: '8px 12px',
            border: '1px solid #d9d9d9',
            borderRadius: 8,
            background: '#fafafa',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div style={{ minWidth: 0 }}>
            <Text strong>{artifactReference.title || '已引用产物'}</Text>
            <div>
              <Text type="secondary">
                {artifactReference.artifact_type === 'report_outline'
                  ? '报告大纲'
                  : artifactReference.artifact_type === 'ppt_deck'
                    ? 'PPT 文件'
                    : artifactReference.artifact_type === 'ppt_outline'
                      ? 'PPT 大纲'
                      : artifactReference.artifact_type === 'ppt_content_markdown'
                        ? 'PPT 文稿'
                        : '报告正文'}
                {artifactReference.version_id ? ` · ${artifactReference.version_id}` : ''}
              </Text>
            </div>
          </div>
          <Button size="small" onClick={() => clearArtifactReference()}>
            移除引用
          </Button>
        </div>
      ) : null}

      <Space.Compact style={{ width: '100%' }}>
        <TextArea
          autoSize={{ minRows: 1, maxRows: 5 }}
          placeholder={isTranscribing ? '正在识别语音...' : '开始输入... (Shift + Enter 换行)'}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              void handleSendMessage();
            }
          }}
          disabled={isLoading}
          size="large"
          style={{ borderRadius: '8px 0 0 8px' }}
        />
        <Tooltip title={isRecording ? '点击停止录音并转文字' : isTranscribing ? '正在识别语音' : '语音输入'}>
          <Button
            icon={<AudioOutlined />}
            onClick={() => void handleVoiceInput()}
            disabled={isLoading || isTranscribing}
            danger={isRecording}
            size="large"
            style={{ borderRadius: 0 }}
          >
            {isRecording ? '录音中' : '语音输入'}
          </Button>
        </Tooltip>
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={() => void handleSendMessage()}
          loading={isLoading}
          size="large"
          style={{ borderRadius: '0 8px 8px 0' }}
        />
      </Space.Compact>
    </div>
  );
};

export default ChatPanel;
