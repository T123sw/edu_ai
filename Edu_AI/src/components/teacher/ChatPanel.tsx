import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Input, Button, List, Space, Typography, Tag, Tooltip, message, Empty, Spin, Modal, Popover, Switch } from 'antd';
import { SendOutlined, SnippetsOutlined, HistoryOutlined, DeleteOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { listChatConversations, getChatConversationDetail, deleteChatConversation, type ConversationListItem } from '../../services/teacher/api';
import { sendChatReplyV2 } from '../../services/teacher/chatV2';
import { extractGeneratedFilesFromV2Response } from '../../services/teacher/chatV2.helpers';
import ReactMarkdown from 'react-markdown';
import { type RAGSource } from '../../services/rag';
import StatusCard from './StatusCardV2';

const { TextArea } = Input;
const { Title, Text } = Typography;

interface Message {
  user: 'You' | 'AI';
  text: string;
  sources?: any[];
  statusText?: string;
}

interface ChatPanelProps {
  courseId?: string;
}

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
    addGeneratedFile,
    setViewingFile,
    statusCard,
    setStatusCard,
  } = useStore();

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [historyList, setHistoryList] = useState<ConversationListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<string | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPopoverOpen, setHistoryPopoverOpen] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const init = async () => {
      setHistoryLoading(true);
      try {
        const result = await listChatConversations();
        const list = result.conversations || [];
        setHistoryList(list);

        if (!currentConversationId && list.length > 0) {
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

  const loadConversation = async (conversationId: string, showSuccess = true) => {
    setLoadingConversationId(conversationId);
    try {
      const detail = await getChatConversationDetail(conversationId);
      const mapped: Message[] = (detail.history || []).map((msg: any) => ({
        user: msg.role === 'assistant' ? 'AI' : 'You',
        text: msg.content || '',
        sources: (msg.sources || []) as any[],
      }));

      setMessages(mapped);
      setCurrentConversationId(detail.conversation_id);
      setStatusCard(detail.status_card || null);

      if (showSuccess) {
        message.success('已切换到历史对话');
      }
    } catch (error: any) {
      console.error('加载对话详情失败:', error);
      message.error(error?.message || '加载历史对话失败');
    } finally {
      setLoadingConversationId(null);
    }
  };

  const handleNewConversation = () => {
    setMessages([]);
    setCurrentConversationId(null);
    setInputValue('');
    setStatusCard(null);
    message.success('已新建对话');
  };

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      await deleteChatConversation(conversationId);

      const nextHistory = historyList.filter((item) => item.conversation_id !== conversationId);
      setHistoryList(nextHistory);

      if (currentConversationId === conversationId) {
        if (nextHistory.length > 0) {
          await loadConversation(nextHistory[0].conversation_id, false);
        } else {
          setMessages([]);
          setCurrentConversationId(null);
          setStatusCard(null);
        }
      }

      message.success('历史对话已删除');
    } catch (error: any) {
      console.error('删除对话失败:', error);
      message.error(error?.message || '删除历史对话失败');
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
      const response = await sendChatReplyV2({
        question: userMessage.text,
        conversation_id: currentConversationId || undefined,
        course_id: courseId,
        allow_rag: allowRag,
        allow_web: allowWeb,
        selected_doc_ids: selectedDocs,
      });

      const nextConversationId = String(response.conversation?.conversation_id || '').trim();
      if (nextConversationId && nextConversationId !== currentConversationId) {
        setCurrentConversationId(nextConversationId);
      }
      setStatusCard(response.status_card || null);

      const sources = Array.isArray(response.sources) ? (response.sources as unknown as RAGSource[]) : [];
      const generatedFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
        ...file,
        meta: {
          ...(file.meta || {}),
          conversationId: nextConversationId || currentConversationId,
        },
      }));

      generatedFiles.forEach((file) => addGeneratedFile(file));
      if (generatedFiles.length > 0) {
        setViewingFile(generatedFiles[generatedFiles.length - 1]);
      }

      updateLastMessage({
        text: String(response.message?.content || ''),
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

      <Space.Compact style={{ width: '100%' }}>
        <TextArea
          autoSize={{ minRows: 1, maxRows: 5 }}
          placeholder="开始输入... (Shift + Enter 换行)"
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
