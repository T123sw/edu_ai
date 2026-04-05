import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Space, Typography, Tag, Tooltip } from 'antd';
import { SendOutlined, SnippetsOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore'; // 复用教师端的 store
import { sendChatMessage } from '../../services/chat'; // 学生端用独立的 chat service
import ReactMarkdown from 'react-markdown';
import { type RAGSource } from '../../services/rag';

const { TextArea } = Input;
const { Title } = Typography;

interface Message {
  user: 'You' | 'AI';
  text: string;
  sources?: RAGSource[];
}

const ChatPanel: React.FC = () => {
  const { messages, addMessage, selectedDocs, setHighlightRequest } = useStore();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (inputValue.trim() === '' || isLoading) return;

    const userMessage: Message = { user: 'You' as const, text: inputValue };
    addMessage(userMessage);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        question: userMessage.text,
        use_rag: selectedDocs.length > 0,
      });
      const aiResponse: Message = {
        user: 'AI' as const,
        text: response.answer,
        sources: response.sources as RAGSource[],
      };
      addMessage(aiResponse);
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorResponse: Message = { user: 'AI' as const, text: '抱歉，发送消息时出错，请稍后再试。' };
      addMessage(errorResponse);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSourceClick = (source: RAGSource) => {
    const path = (source as any).source_path;
    if (path) {
      setHighlightRequest({ filePath: path, source });
    }
  };

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
      <Title level={5} style={{ marginTop: 0, marginBottom: '20px', fontWeight: 600, flexShrink: 0 }}>
        对话
      </Title>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '20px', padding: '0 12px', minHeight: 0 }}>
        <List
          dataSource={messages}
          renderItem={(item, index) => (
            <List.Item key={index} style={{ border: 'none', display: 'flex', flexDirection: 'column', alignItems: item.user === 'You' ? 'flex-end' : 'flex-start', marginBottom: 16 }}>
              <div
                style={{
                  maxWidth: '80%',
                  padding: '10px 15px',
                  borderRadius: '18px',
                  background: item.user === 'You' ? '#1677ff' : '#f0f0f0',
                  color: item.user === 'You' ? 'white' : 'black',
                }}
              >
                {item.user === 'AI' ? (
                  <ReactMarkdown>{item.text}</ReactMarkdown>
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap' }}>{item.text}</div>
                )}
              </div>
              {item.user === 'AI' && item.sources && item.sources.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Space wrap size={[0, 8]}>
                    {item.sources.map((source, i) => (
                      <Tooltip key={i} title={`来源片段: ${source.content.substring(0, 100)}...`}>
                        <Tag
                          icon={<SnippetsOutlined />}
                          color="blue"
                          onClick={() => handleSourceClick(source)}
                          style={{ cursor: 'pointer' }}
                        >
                          {source.source || `来源 ${i + 1}`}
                        </Tag>
                      </Tooltip>
                    ))}
                  </Space>
                </div>
              )}
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
              handleSendMessage();
            }
          }}
          disabled={isLoading}
          size="large"
          style={{ borderRadius: '8px 0 0 8px' }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSendMessage}
          loading={isLoading}
          size="large"
          style={{ borderRadius: '0 8px 8px 0' }}
        />
      </Space.Compact>
    </div>
  );
};

export default ChatPanel;
