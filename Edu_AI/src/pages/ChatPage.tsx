import { 
  Button, Col, Input, List, Row, Select, Switch, Typography, message, Spin, Empty, Space, Divider,
  Dropdown, Tooltip
} from 'antd';
import { useState, useEffect, useRef } from 'react';
import { 
  PlusOutlined, DeleteOutlined, MessageOutlined, CopyOutlined, EditOutlined, 
  ReloadOutlined, MoreOutlined, CheckOutlined, CloseOutlined, DownOutlined, RightOutlined
} from '@ant-design/icons';
import { 
  sendChatMessage, listConversations, getConversationHistory, deleteConversation, 
  truncateConversation, deleteMessagePair as apiDeleteMessagePair,
  listModels, type ChatRequest, type Source, type ModelInfo 
} from '../services/chat';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import './ChatPage.css';

const { TextArea } = Input;
const { Text } = Typography;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  isEditing?: boolean;
  isRegenerating?: boolean;
  backendIndex?: number; // 后端消息索引
}

interface ConversationItem {
  conversation_id: string;
  title: string;
  created_at?: string;
  message_count?: number;
}

// 解析思考过程的函数
const parseThinkingContent = (content: string): { thinking: string | null; answer: string } => {
  // 支持多种思考标签格式
  const thinkPatterns = [
    /<think>([\s\S]*?)<\/think>/i,
    /<thinking>([\s\S]*?)<\/thinking>/i,
    /<thought>([\s\S]*?)<\/thought>/i,
  ];
  
  for (const pattern of thinkPatterns) {
    const match = content.match(pattern);
    if (match) {
      const thinking = match[1].trim();
      const answer = content.replace(match[0], '').trim();
      return { thinking, answer };
    }
  }
  
  return { thinking: null, answer: content };
};

// 思考过程组件
const ThinkingBlock = ({ content }: { content: string }) => {
  const [expanded, setExpanded] = useState(false);
  
  // 只在点击header时切换，阻止内容区域的点击冒泡
  const handleHeaderClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(!expanded);
  };

  // 阻止内容区域的鼠标事件冒泡，防止影响文本选择
  const handleContentMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
  };
  
  return (
    <div className="thinking-block">
      <div 
        className="thinking-header" 
        onClick={handleHeaderClick}
      >
        {expanded ? <DownOutlined /> : <RightOutlined />}
        <span className="thinking-label">思考过程</span>
      </div>
      {expanded && (
        <div 
          className="thinking-content"
          onMouseDown={handleContentMouseDown}
        >
          {content}
        </div>
      )}
    </div>
  );
};

export default function ChatPage() {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [useRAG, setUseRAG] = useState(true);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | undefined>(undefined);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatAreaRef = useRef<HTMLDivElement>(null);

  // 复制文本到剪贴板
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success('已复制到剪贴板');
    } catch {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      message.success('已复制到剪贴板');
    }
  };

  // 开始编辑消息
  const startEditMessage = (messageId: string, content: string) => {
    setEditingMessageId(messageId);
    setEditingContent(content);
  };

  // 取消编辑
  const cancelEdit = () => {
    setEditingMessageId(null);
    setEditingContent('');
  };


  // 保存编辑并重新发送（同步后端）
  const saveEditAndResend = async () => {
    if (!editingContent.trim() || editingMessageId === null) return;

    const messageIndex = messages.findIndex(m => m.id === editingMessageId);
    if (messageIndex === -1) return;

    // 获取后端索引
    const backendIndex = messages[messageIndex].backendIndex;
    
    // 先同步后端：截断到该消息之前
    if (currentConversationId && backendIndex !== undefined) {
      try {
        await truncateConversation(currentConversationId, backendIndex);
      } catch (error) {
        console.error('截断对话失败:', error);
      }
    }

    // 删除该消息及其后面的所有消息
    const newMessages = messages.slice(0, messageIndex);
    setMessages(newMessages);
    
    cancelEdit();

    // 重新发送编辑后的消息
    const question = editingContent.trim();
    
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
      backendIndex: messageIndex
    };
    setMessages(prev => [...prev, userMessage]);

    const loadingMessageId = `loading_${Date.now()}`;
    const loadingMessage: Message = {
      id: loadingMessageId,
      role: 'assistant',
      content: '正在思考...',
      isRegenerating: true
    };
    setMessages(prev => [...prev, loadingMessage]);

    setLoading(true);
    setSources([]);

    try {
      if (!selectedModelId) {
        message.error('未找到可用模型');
        setLoading(false);
        setMessages(prev => prev.filter(m => m.id !== loadingMessageId));
        return;
      }

      const request: ChatRequest = {
        question,
        conversation_id: currentConversationId || undefined,
        model_id: selectedModelId,
        use_rag: useRAG,
        temperature: 0.1,
        max_tokens: 1000
      };

      const response = await sendChatMessage(request);

      if (!currentConversationId) {
        setCurrentConversationId(response.conversation_id);
        loadConversations();
      } else {
        loadConversations();
      }

      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== loadingMessageId);
        return [
          ...filtered,
          {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: response.answer,
            timestamp: new Date().toISOString(),
            backendIndex: messageIndex + 1
          }
        ];
      });

      if (response.sources && response.sources.length > 0) {
        setSources(response.sources);
      } else {
        setSources([]);
      }

      message.success('消息已重新发送');
    } catch (error: any) {
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== loadingMessageId);
        return [
          ...filtered,
          {
            id: `error_${Date.now()}`,
            role: 'assistant',
            content: `错误: ${error.message || '发送消息失败'}`
          }
        ];
      });
      message.error(error.message || '重新发送失败');
    } finally {
      setLoading(false);
    }
  };

  // 重新生成回答（同步后端）
  const regenerateResponse = async (messageId: string) => {
    const messageIndex = messages.findIndex(m => m.id === messageId);
    if (messageIndex === -1 || messageIndex === 0) return;

    const userMessage = messages[messageIndex - 1];
    if (userMessage.role !== 'user') return;

    // 截断后端到用户消息位置
    const backendIndex = messages[messageIndex].backendIndex;
    if (currentConversationId && backendIndex !== undefined) {
      try {
        await truncateConversation(currentConversationId, backendIndex);
      } catch (error) {
        console.error('截断对话失败:', error);
      }
    }

    setMessages(prev => prev.map(m => 
      m.id === messageId ? { ...m, isRegenerating: true, content: '正在重新生成...' } : m
    ));

    setLoading(true);

    try {
      if (!selectedModelId) {
        message.error('未找到可用模型');
        return;
      }

      const request: ChatRequest = {
        question: userMessage.content,
        conversation_id: currentConversationId || undefined,
        model_id: selectedModelId,
        use_rag: useRAG,
        temperature: 0.1,
        max_tokens: 1000
      };

      const response = await sendChatMessage(request);

      setMessages(prev => prev.map(m => 
        m.id === messageId 
          ? { 
              ...m, 
              content: response.answer, 
              isRegenerating: false,
              timestamp: new Date().toISOString()
            } 
          : m
      ));

      if (response.sources && response.sources.length > 0) {
        setSources(response.sources);
      }

      message.success('回答已重新生成');
    } catch (error: any) {
      setMessages(prev => prev.map(m => 
        m.id === messageId 
          ? { 
              ...m, 
              content: `重新生成失败: ${error.message || '请稍后重试'}`, 
              isRegenerating: false 
            } 
          : m
      ));
      message.error('重新生成失败');
    } finally {
      setLoading(false);
    }
  };

  // 删除单条消息对话（同步后端）
  const deleteMessagePair = async (messageId: string) => {
    const messageIndex = messages.findIndex(m => m.id === messageId);
    if (messageIndex === -1) return;

    let startIndex = messageIndex;
    let endIndex = messageIndex;

    if (messages[messageIndex].role === 'user') {
      endIndex = messageIndex + 1;
      if (!(endIndex < messages.length && messages[endIndex].role === 'assistant')) {
        endIndex = messageIndex;
      }
    } else {
      startIndex = messageIndex - 1;
      if (!(startIndex >= 0 && messages[startIndex].role === 'user')) {
        startIndex = messageIndex;
        endIndex = messageIndex;
      }
    }

    // 同步后端删除
    const backendIndex = messages[startIndex].backendIndex;
    if (currentConversationId && backendIndex !== undefined) {
      try {
        await apiDeleteMessagePair(currentConversationId, backendIndex);
      } catch (error) {
        console.error('后端删除失败:', error);
      }
    }

    const newMessages = [
      ...messages.slice(0, startIndex),
      ...messages.slice(endIndex + 1)
    ];
    
    // 重新计算后端索引
    const updatedMessages = newMessages.map((m, idx) => ({
      ...m,
      backendIndex: idx
    }));
    
    setMessages(updatedMessages);
    message.success('已删除该轮对话');
  };

  // 获取当前选中的文本（用于复制功能）
  const getSelectedText = () => {
    const selection = window.getSelection();
    return selection ? selection.toString().trim() : '';
  };

  // 保存选中文本的ref（在下拉菜单打开时保存）
  const savedSelectionRef = useRef('');
  // 保存选区范围，用于恢复选中状态
  const savedRangeRef = useRef<Range | null>(null);


  // Markdown 渲染组件（支持表格）
  const MarkdownRenderer = ({ content }: { content: string }) => {
    // 解析思考过程
    const { thinking, answer } = parseThinkingContent(content);
    
    return (
      <div className="markdown-body">
        {thinking && <ThinkingBlock content={thinking} />}
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={{
            code({ className, children }) {
              const match = /language-(\w+)/.exec(className || '');
              const isInline = !match;
              
              return !isInline ? (
                <SyntaxHighlighter
                  style={oneDark as any}
                  language={match[1]}
                  PreTag="div"
                >
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : (
                <code className={className}>
                  {children}
                </code>
              );
            },
            table({ children }) {
              return (
                <div className="table-wrapper">
                  <table>{children}</table>
                </div>
              );
            },
            p({ children }) {
              return <p>{children}</p>;
            }
          }}
        >
          {answer}
        </ReactMarkdown>
      </div>
    );
  };

  // 加载对话列表
  const loadConversations = async () => {
    try {
      const result = await listConversations();
      setConversations(result.conversations || []);
    } catch (error) {
      console.error('加载对话列表失败:', error);
    }
  };

  // 加载对话历史
  const loadConversationHistory = async (conversationId: string) => {
    try {
      const result = await getConversationHistory(conversationId);
      const msgs: Message[] = result.history.map((item, index) => ({
        id: `msg_${index}_${Date.now()}`,
        role: item.role as 'user' | 'assistant',
        content: item.content,
        timestamp: item.timestamp,
        backendIndex: index
      }));
      setMessages(msgs);
      setCurrentConversationId(conversationId);
    } catch (error) {
      console.error('加载对话历史失败:', error);
      message.error('加载对话历史失败');
    }
  };

  // 新建对话
  const handleNewConversation = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setSources([]);
    setInput('');
  };

  // 切换到指定对话
  const handleSelectConversation = (conversationId: string) => {
    if (conversationId === currentConversationId) return;
    loadConversationHistory(conversationId);
  };

  // 删除对话
  const handleDeleteConversation = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(conversationId);
      message.success('对话已删除');
      if (conversationId === currentConversationId) {
        handleNewConversation();
      }
      loadConversations();
    } catch (error: any) {
      message.error(error.message || '删除失败');
    }
  };

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput('');
    
    const currentMsgCount = messages.length;
    
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
      backendIndex: currentMsgCount
    };
    setMessages(prev => [...prev, userMessage]);

    const loadingMessageId = `loading_${Date.now()}`;
    const loadingMessage: Message = {
      id: loadingMessageId,
      role: 'assistant',
      content: '正在思考...'
    };
    setMessages(prev => [...prev, loadingMessage]);

    setLoading(true);
    setSources([]);

    try {
      if (!selectedModelId) {
        message.error('未找到可用模型，请检查后端 /models 接口配置');
        setLoading(false);
        setMessages(prev => prev.filter(m => m.id !== loadingMessageId));
        return;
      }

      const request: ChatRequest = {
        question,
        conversation_id: currentConversationId || undefined,
        model_id: selectedModelId,
        use_rag: useRAG,
        temperature: 0.1,
        max_tokens: 1000
      };

      const response = await sendChatMessage(request);

      if (!currentConversationId) {
        setCurrentConversationId(response.conversation_id);
        loadConversations();
      } else if (response.title) {
        loadConversations();
      }

      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== loadingMessageId);
        return [
          ...filtered,
          {
            id: `assistant_${Date.now()}`,
            role: 'assistant',
            content: response.answer,
            timestamp: new Date().toISOString(),
            backendIndex: currentMsgCount + 1
          }
        ];
      });

      if (response.sources && response.sources.length > 0) {
        setSources(response.sources);
      } else {
        setSources([]);
      }

      message.success('消息发送成功');
    } catch (error: any) {
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== loadingMessageId);
        return [
          ...filtered,
          {
            id: `error_${Date.now()}`,
            role: 'assistant',
            content: `错误: ${error.message || '发送消息失败，请检查后端服务是否运行'}`
          }
        ];
      });
      message.error(error.message || '发送消息失败');
      console.error('发送消息失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 初始化加载
  useEffect(() => {
    loadConversations();
    (async () => {
      try {
        const modelList = await listModels();
        setModels(modelList);
        if (modelList.length > 0) {
          setSelectedModelId(modelList[0].id);
        }
      } catch (error) {
        console.error('加载模型列表失败:', error);
        message.error('加载模型列表失败');
        setSelectedModelId(undefined);
      }
    })();
  }, []);

  // 回车发送
  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };


  return (
    <div className="chat-page">
      <Row gutter={0} style={{ height: '100%', margin: 0 }} className="chat-layout-card">
        {/* 左侧：对话历史 */}
        <Col span={6} className="conversation-sidebar">
          <div className="sidebar-header">
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              block 
              onClick={handleNewConversation}
              style={{ marginBottom: 16 }}
            >
              新建对话
            </Button>
          </div>
          <div className="conversation-list">
            {conversations.length === 0 ? (
              <Empty 
                description="暂无对话历史" 
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ marginTop: 60 }}
              />
            ) : (
              <List
                dataSource={conversations}
                renderItem={(item) => (
                  <div
                    className={`conversation-item ${item.conversation_id === currentConversationId ? 'active' : ''}`}
                    onClick={() => handleSelectConversation(item.conversation_id)}
                  >
                    <div className="conversation-content">
                      <div className="conversation-title">
                        <MessageOutlined style={{ marginRight: 8, color: '#1890ff' }} />
                        {item.title}
                      </div>
                      {item.message_count !== undefined && (
                        <div className="conversation-meta">
                          {item.message_count} 条消息
                        </div>
                      )}
                    </div>
                    <Button
                      type="text"
                      icon={<DeleteOutlined />}
                      size="small"
                      danger
                      onClick={(e) => handleDeleteConversation(item.conversation_id, e)}
                      className="delete-btn"
                    />
                  </div>
                )}
              />
            )}
          </div>
        </Col>

        {/* 中间：聊天区域 */}
        <Col span={12} className="chat-main">
          <div className="chat-header">
            <Space size="middle">
              <span>模型：</span>
              <Select
                value={selectedModelId}
                onChange={setSelectedModelId}
                style={{ width: 160 }}
                options={models.map((model) => ({
                  value: model.id,
                  label: model.name || model.model_name || model.id
                }))}
                placeholder="请选择模型"
                loading={models.length === 0}
              />
              <Divider type="vertical" />
              <span>RAG：</span>
              <Switch 
                checked={useRAG} 
                onChange={setUseRAG}
                checkedChildren="开启"
                unCheckedChildren="关闭"
              />
              <span style={{ 
                fontSize: '12px', 
                color: useRAG ? '#52c41a' : '#ff7875',
                fontWeight: 500
              }}>
                {useRAG ? '知识库检索模式' : '自由对话模式'}
              </span>
            </Space>
          </div>
          
          <div className="chat-messages" ref={chatAreaRef}>
            {messages.length === 0 ? (
              <div className="empty-chat">
                <Empty 
                  description="开始输入内容与AI对话…" 
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              </div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`message-wrapper ${m.role === 'user' ? 'user-message' : 'assistant-message'}`}
                >
                  <div className="message-bubble">
                    {editingMessageId === m.id ? (
                      <div className="message-edit-mode">
                        <Input.TextArea
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                          autoSize={{ minRows: 2, maxRows: 8 }}
                          onPressEnter={(e) => {
                            if (e.ctrlKey || e.metaKey) {
                              saveEditAndResend();
                            }
                          }}
                        />
                        <div className="edit-actions">
                          <Button size="small" onClick={cancelEdit}>
                            <CloseOutlined /> 取消
                          </Button>
                          <Button 
                            type="primary" 
                            size="small" 
                            onClick={saveEditAndResend}
                            loading={loading}
                          >
                            <CheckOutlined /> 保存并重发
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {m.content === '正在思考...' || m.isRegenerating ? (
                          <div className="thinking">
                            <Spin size="small" />
                            <span>{m.isRegenerating ? '正在重新生成...' : '正在思考...'}</span>
                          </div>
                        ) : (
                          <div className="message-content">
                            {m.role === 'assistant' ? (
                              <MarkdownRenderer content={m.content} />
                            ) : (
                              <div className="user-message-text">{m.content}</div>
                            )}
                          </div>
                        )}
                        
                        {!m.isRegenerating && m.content !== '正在思考...' && (
                          <div className="message-actions">
                            {m.role === 'user' ? (
                              <div className="action-buttons">
                                <Tooltip title="复制">
                                  <Button 
                                    type="text" 
                                    size="small" 
                                    icon={<CopyOutlined />}
                                    onClick={() => copyToClipboard(m.content)}
                                  />
                                </Tooltip>
                                <Tooltip title="编辑并重发">
                                  <Button 
                                    type="text" 
                                    size="small" 
                                    icon={<EditOutlined />}
                                    onClick={() => startEditMessage(m.id, m.content)}
                                  />
                                </Tooltip>
                                <Dropdown
                                  menu={{
                                    items: [
                                      {
                                        key: 'delete',
                                        label: '删除此轮对话',
                                        icon: <DeleteOutlined />,
                                        danger: true,
                                        onClick: () => deleteMessagePair(m.id)
                                      }
                                    ]
                                  }}
                                  trigger={['click']}
                                >
                                  <Button type="text" size="small" icon={<MoreOutlined />} />
                                </Dropdown>
                              </div>
                            ) : (
                              <div className="action-buttons">
                                <Tooltip title="复制">
                                  <Button 
                                    type="text" 
                                    size="small" 
                                    icon={<CopyOutlined />}
                                    onClick={() => copyToClipboard(m.content)}
                                  />
                                </Tooltip>
                                <Tooltip title="重新生成">
                                  <Button 
                                    type="text" 
                                    size="small" 
                                    icon={<ReloadOutlined />}
                                    onClick={() => regenerateResponse(m.id)}
                                    loading={m.isRegenerating}
                                  />
                                </Tooltip>
                                <Dropdown
                                  onOpenChange={(open) => {
                                    if (open) {
                                      // 下拉菜单打开时保存当前选中的文本和选区范围
                                      const selection = window.getSelection();
                                      savedSelectionRef.current = selection ? selection.toString().trim() : '';
                                      // 保存选区范围，用于后续恢复
                                      if (selection && selection.rangeCount > 0) {
                                        savedRangeRef.current = selection.getRangeAt(0).cloneRange();
                                      } else {
                                        savedRangeRef.current = null;
                                      }
                                    }
                                  }}
                                  menu={{
                                    items: [
                                      {
                                        key: 'copy-selected',
                                        label: '复制选中文本',
                                        icon: <CopyOutlined />,
                                        onClick: () => {
                                          const text = savedSelectionRef.current;
                                          if (text) {
                                            copyToClipboard(text);
                                            // 复制后恢复选中状态
                                            if (savedRangeRef.current) {
                                              setTimeout(() => {
                                                const selection = window.getSelection();
                                                if (selection) {
                                                  selection.removeAllRanges();
                                                  selection.addRange(savedRangeRef.current!);
                                                }
                                              }, 10);
                                            }
                                          } else {
                                            message.info('请先选中要复制的文本');
                                          }
                                        }
                                      },
                                      { type: 'divider' },
                                      {
                                        key: 'delete',
                                        label: '删除此轮对话',
                                        icon: <DeleteOutlined />,
                                        danger: true,
                                        onClick: () => deleteMessagePair(m.id)
                                      }
                                    ]
                                  }}
                                  trigger={['click']}
                                >
                                  <Button type="text" size="small" icon={<MoreOutlined />} />
                                </Dropdown>
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            <TextArea
              rows={3}
              placeholder="请输入要提问的内容（Enter发送，Ctrl+Enter换行）"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={loading}
              className="chat-input"
            />
            <div className="input-actions">
              <Button 
                type="primary" 
                onClick={handleSend}
                loading={loading}
                disabled={!input.trim()}
                size="large"
              >
                发送
              </Button>
            </div>
          </div>
        </Col>

        {/* 右侧：知识库检索结果 */}
        <Col span={6} className="sources-sidebar">
          <div className="sources-header">
            <Text strong>知识库检索结果</Text>
          </div>
          <div className="sources-content">
            {sources.length === 0 ? (
              <Empty 
                description="暂无检索结果" 
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ marginTop: 60 }}
              />
            ) : (
              <List
                size="small"
                dataSource={sources}
                renderItem={(item) => (
                  <div className="source-item">
                    <div className="source-title">
                      {item.index}. {item.source}
                    </div>
                    <div className="source-meta">
                      第 {item.page} 页
                    </div>
                    <div className="source-content">
                      {item.content}
                    </div>
                  </div>
                )}
              />
            )}
          </div>
        </Col>
      </Row>
    </div>
  );
}