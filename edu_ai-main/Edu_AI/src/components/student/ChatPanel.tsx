import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, List, Space, Typography, Tag, Tooltip } from 'antd';
import { SendOutlined, SnippetsOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { sendChatMessage } from '../../services/chat';
import ReactMarkdown from 'react-markdown';
import { type RAGSource } from '../../services/rag';
import './ChatPanel.css';

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

    const userMessage: Message = { user: 'You', text: inputValue };
    addMessage(userMessage);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        question: userMessage.text,
        use_rag: selectedDocs.length > 0,
      });
      const aiResponse: Message = {
        user: 'AI',
        text: response.answer,
        sources: response.sources as RAGSource[],
      };
      addMessage(aiResponse);
    } catch (error) {
      console.error('Failed to send message:', error);
      addMessage({ user: 'AI', text: '抱歉，发送消息时出错，请稍后再试。' });
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
    <div className="student-chat-panel">
      <div className="student-chat-panel__header">
        <div>
          <Title level={5} className="student-chat-panel__title">
            对话
          </Title>
          <div className="student-chat-panel__subtitle">基于当前课程上下文与已选资料进行问答</div>
        </div>
      </div>

      <div className="student-chat-panel__messages">
        <List
          dataSource={messages}
          renderItem={(item, index) => (
            <List.Item
              key={index}
              className={`student-chat-panel__item ${item.user === 'You' ? 'student-chat-panel__item--user' : 'student-chat-panel__item--assistant'}`}
            >
              <div className="student-chat-panel__bubble">
                {item.user === 'AI' ? (
                  <ReactMarkdown>{item.text}</ReactMarkdown>
                ) : (
                  <div className="student-chat-panel__user-text">{item.text}</div>
                )}
              </div>

              {item.user === 'AI' && item.sources && item.sources.length > 0 && (
                <div className="student-chat-panel__sources">
                  <Space wrap size={[0, 8]}>
                    {item.sources.map((source, i) => (
                      <Tooltip key={i} title={`来源片段: ${source.content.substring(0, 100)}...`}>
                        <Tag
                          icon={<SnippetsOutlined />}
                          color="blue"
                          onClick={() => handleSourceClick(source)}
                          className="student-chat-panel__source-tag"
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

      <div className="student-chat-panel__composer">
        <Space.Compact className="student-chat-panel__composer-row">
          <TextArea
            autoSize={{ minRows: 1, maxRows: 5 }}
            placeholder="开始输入问题…（Enter 发送，Shift + Enter 换行）"
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
            className="student-chat-panel__input"
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            loading={isLoading}
            size="large"
            className="student-chat-panel__send"
          />
        </Space.Compact>
      </div>
    </div>
  );
};

export default ChatPanel;
