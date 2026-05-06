import { 
  Card, 
  Col, 
  Form, 
  Input, 
  Radio, 
  Row, 
  Select,
  Tabs, 
  Tag, 
  Button, 
  List, 
  Typography,
  Space,
  Divider,
  message,
  Spin,
  Empty,
  Modal,
  Popconfirm
} from 'antd';
import {
  QuestionCircleOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  CheckOutlined,
  CloseOutlined
} from '@ant-design/icons';
import { useEffect, useState } from 'react';
import './TeacherToolsPage.css';
import { 
  generateQuestions,
  type Question as APIQuestion
} from '../../services/teacher';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

type Question = APIQuestion;

// 闪卡类型定义
interface Flashcard {
  id: string;
  front: string;  // 正面（问题）
  back: string;   // 背面（答案）
  category?: string; // 分类
  difficulty?: 'easy' | 'medium' | 'hard'; // 难度
  mastery?: 'new' | 'learning' | 'mastered'; // 掌握程度
  createdAt: string;
  lastReviewed?: string;
  reviewCount: number;
}

export default function TeacherToolsPage() {
  const [questionsForm] = Form.useForm();
  const [flashcardForm] = Form.useForm();
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [activeTab, setActiveTab] = useState<string>('questions');
  const [answerVisibility, setAnswerVisibility] = useState<Record<number, { showAnswer: boolean; showAnalysis: boolean }>>({});
  
  // 闪卡相关状态
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [currentCardIndex, setCurrentCardIndex] = useState<number>(0);
  const [isFlipped, setIsFlipped] = useState<boolean>(false);
  const [studyMode, setStudyMode] = useState<boolean>(false);
  const [flashcardModalVisible, setFlashcardModalVisible] = useState<boolean>(false);
  const [editingFlashcard, setEditingFlashcard] = useState<Flashcard | null>(null);

  // 从localStorage加载闪卡
  useEffect(() => {
    const saved = localStorage.getItem('flashcards');
    if (saved) {
      try {
        setFlashcards(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load flashcards:', e);
      }
    }
  }, []);

  // 保存闪卡到localStorage
  const saveFlashcards = (cards: Flashcard[]) => {
    localStorage.setItem('flashcards', JSON.stringify(cards));
    setFlashcards(cards);
  };

  const handleGenerateQuestions = async (values: any) => {
    try {
      setGeneratingQuestions(true);

      const knowledgeInput: string = values.knowledgePointsText || '';
      const knowledgePoints = knowledgeInput
        .split(/[,，、\n]/)
        .map((item: string) => item.trim())
        .filter(Boolean);

      const payload = {
        knowledgePoints,
        types: values.types || [],
        difficulty: values.difficulty || 'medium',
        count: values.count || 10,
      };

      const generated = await generateQuestions(payload);
      setQuestions(generated);
      setAnswerVisibility({});
      message.success(`成功生成 ${generated.length} 道题目！`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成题目失败，请稍后重试';
      message.error(msg);
    } finally {
      setGeneratingQuestions(false);
    }
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case '高':
        return 'red';
      case '中':
        return 'orange';
      case '低':
        return 'green';
      default:
        return 'default';
    }
  };

  // 闪卡相关函数
  const handleCreateFlashcard = (values: any) => {
    const newCard: Flashcard = {
      id: `flashcard-${Date.now()}`,
      front: values.front,
      back: values.back,
      category: values.category || '未分类',
      difficulty: values.difficulty || 'medium',
      mastery: 'new',
      createdAt: new Date().toISOString(),
      reviewCount: 0,
    };
    const updated = [...flashcards, newCard];
    saveFlashcards(updated);
    flashcardForm.resetFields();
    setFlashcardModalVisible(false);
    message.success('闪卡创建成功！');
  };

  const handleEditFlashcard = (card: Flashcard) => {
    setEditingFlashcard(card);
    flashcardForm.setFieldsValue({
      front: card.front,
      back: card.back,
      category: card.category,
      difficulty: card.difficulty,
    });
    setFlashcardModalVisible(true);
  };

  const handleUpdateFlashcard = (values: any) => {
    if (!editingFlashcard) return;
    const updated = flashcards.map(card =>
      card.id === editingFlashcard.id
        ? {
            ...card,
            front: values.front,
            back: values.back,
            category: values.category || '未分类',
            difficulty: values.difficulty || 'medium',
          }
        : card
    );
    saveFlashcards(updated);
    flashcardForm.resetFields();
    setFlashcardModalVisible(false);
    setEditingFlashcard(null);
    message.success('闪卡更新成功！');
  };

  const handleDeleteFlashcard = (id: string) => {
    const updated = flashcards.filter(card => card.id !== id);
    saveFlashcards(updated);
    message.success('闪卡已删除');
    if (studyMode && currentCardIndex >= updated.length && updated.length > 0) {
      setCurrentCardIndex(updated.length - 1);
    } else if (updated.length === 0) {
      setStudyMode(false);
      setCurrentCardIndex(0);
    }
  };

  const handleStartStudy = () => {
    if (flashcards.length === 0) {
      message.warning('请先创建闪卡');
      return;
    }
    setStudyMode(true);
    setCurrentCardIndex(0);
    setIsFlipped(false);
  };

  const handleFlipCard = () => {
    setIsFlipped(!isFlipped);
  };

  const handleNextCard = () => {
    if (currentCardIndex < flashcards.length - 1) {
      setCurrentCardIndex(currentCardIndex + 1);
      setIsFlipped(false);
    } else {
      message.info('已经是最后一张卡片了');
    }
  };

  const handlePrevCard = () => {
    if (currentCardIndex > 0) {
      setCurrentCardIndex(currentCardIndex - 1);
      setIsFlipped(false);
    } else {
      message.info('已经是第一张卡片了');
    }
  };

  const handleMarkMastery = (mastery: 'new' | 'learning' | 'mastered') => {
    const currentCard = flashcards[currentCardIndex];
    if (!currentCard) return;
    
    const updated = flashcards.map((card, index) =>
      index === currentCardIndex
        ? {
            ...card,
            mastery,
            lastReviewed: new Date().toISOString(),
            reviewCount: card.reviewCount + 1,
          }
        : card
    );
    saveFlashcards(updated);
    
    // 自动进入下一张卡片
    if (currentCardIndex < flashcards.length - 1) {
      setCurrentCardIndex(currentCardIndex + 1);
      setIsFlipped(false);
    } else {
      message.success('所有卡片已学习完成！');
      setStudyMode(false);
    }
  };

  const handleEndStudy = () => {
    setStudyMode(false);
    setCurrentCardIndex(0);
    setIsFlipped(false);
  };

  const questionsFormContent = (
    <Row gutter={24}>
      <Col xs={24} lg={10}>
        <Card 
          className="form-card"
          title={
            <span>
              <QuestionCircleOutlined style={{ marginRight: 8, color: '#1890ff' }} />
              题目生成参数
            </span>
          }
        >
          <Form 
            form={questionsForm}
            layout="vertical"
            onFinish={handleGenerateQuestions}
          >
            <Form.Item 
              label={
                <span>
                  <RocketOutlined style={{ marginRight: 4 }} />
                  知识点
                </span>
              }
              name="knowledgePointsText"
            >
              <TextArea
                rows={3}
                placeholder="请输入与本次出题相关的知识点，用逗号或换行分隔（例如：鸦片战争背景，战争经过，历史影响）"
                size="large"
              />
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <QuestionCircleOutlined style={{ marginRight: 4 }} />
                  题目类型
                </span>
              }
              name="types"
            >
              <Select
                mode="multiple"
                placeholder="选择题型"
                size="large"
                options={[
                  { value: 'choice', label: '选择题' },
                  { value: 'blank', label: '填空题' },
                  { value: 'short', label: '简答题' }
                ]}
              />
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <CheckCircleOutlined style={{ marginRight: 4 }} />
                  难度
                </span>
              }
              name="difficulty" 
              initialValue="medium"
            >
              <Radio.Group size="large">
                <Radio.Button value="low">低</Radio.Button>
                <Radio.Button value="medium">中</Radio.Button>
                <Radio.Button value="high">高</Radio.Button>
              </Radio.Group>
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <CheckCircleOutlined style={{ marginRight: 4 }} />
                  题目数量
                </span>
              }
              name="count" 
              initialValue={10}
            >
              <Input 
                type="number"
                min={1}
                max={100}
                size="large"
                placeholder="请输入题目数量"
              />
            </Form.Item>
            <Form.Item>
              <Button 
                type="primary" 
                block 
                size="large"
                htmlType="submit"
                loading={generatingQuestions}
                icon={<RocketOutlined />}
              >
                {generatingQuestions ? '生成中...' : '生成题目'}
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </Col>
      <Col xs={24} lg={14}>
        <Card 
          className="result-card"
          title={
            <span>
              <QuestionCircleOutlined style={{ marginRight: 8, color: '#52c41a' }} />
              生成的题目列表
            </span>
          }
          extra={
            questions.length > 0 && (
              <Text type="secondary">
                共 {questions.length} 道题目
              </Text>
            )
          }
        >
          {questions.length === 0 ? (
            <Empty 
              description="填写左侧表单并点击生成题目"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ margin: '60px 0' }}
            />
          ) : (
            <Spin spinning={generatingQuestions}>
              <List
                dataSource={questions}
                renderItem={(item) => (
                  <List.Item className="question-item">
                    <div className="question-content">
                      <div className="question-header">
                        <Space>
                          <Tag color="blue">{item.type}</Tag>
                          <Tag color={getDifficultyColor(item.difficulty)}>
                            难度：{item.difficulty}
                          </Tag>
                        </Space>
                      </div>
                      <Paragraph className="question-text">
                        {item.id}. {item.content}
                      </Paragraph>
                      {item.options && (
                        <div className="question-options">
                          {item.options.map((option, index) => (
                            <div key={index} className="option-item">
                              {option}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="question-actions">
                        <Space>
                          {item.answer && (
                            <Button 
                              type="link" 
                              size="small"
                              onClick={() =>
                                setAnswerVisibility((prev) => ({
                                  ...prev,
                                  [item.id]: {
                                    showAnswer: !prev[item.id]?.showAnswer,
                                    showAnalysis: prev[item.id]?.showAnalysis ?? false,
                                  },
                                }))
                              }
                            >
                              {answerVisibility[item.id]?.showAnswer ? '收起答案' : '查看答案'}
                            </Button>
                          )}
                          {item.analysis && (
                            <Button 
                              type="link" 
                              size="small"
                              onClick={() =>
                                setAnswerVisibility((prev) => ({
                                  ...prev,
                                  [item.id]: {
                                    showAnswer: true,
                                    showAnalysis: !prev[item.id]?.showAnalysis,
                                  },
                                }))
                              }
                            >
                              {answerVisibility[item.id]?.showAnalysis ? '收起解析' : '查看解析'}
                            </Button>
                          )}
                        </Space>
                      </div>
                      {(answerVisibility[item.id]?.showAnswer || answerVisibility[item.id]?.showAnalysis) && (
                        <div className="question-answer">
                          {answerVisibility[item.id]?.showAnswer && item.answer && (
                            <Paragraph className="answer-text">
                              <strong>答案：</strong>{item.answer}
                            </Paragraph>
                          )}
                          {answerVisibility[item.id]?.showAnalysis && item.analysis && (
                            <Paragraph className="analysis-text">
                              <strong>解析：</strong>{item.analysis}
                            </Paragraph>
                          )}
                        </div>
                      )}
                    </div>
                  </List.Item>
                )}
              />
            </Spin>
          )}
        </Card>
      </Col>
    </Row>
  );

  const flashcardManageContent = (
    <div>
      <Card
        className="result-card"
        title={
          <span>
            <QuestionCircleOutlined style={{ marginRight: 8, color: '#1890ff' }} />
            闪卡管理
          </span>
        }
        extra={
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingFlashcard(null);
                flashcardForm.resetFields();
                setFlashcardModalVisible(true);
              }}
            >
              创建闪卡
            </Button>
            {flashcards.length > 0 && (
              <Button
                type="default"
                icon={<ReloadOutlined />}
                onClick={handleStartStudy}
              >
                开始学习
              </Button>
            )}
          </Space>
        }
      >
        {flashcards.length === 0 ? (
          <Empty
            description="暂无闪卡，点击右上角按钮创建"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ margin: '60px 0' }}
          />
        ) : (
          <List
            itemLayout="horizontal"
            dataSource={flashcards}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    key="edit"
                    type="link"
                    icon={<EditOutlined />}
                    onClick={() => handleEditFlashcard(item)}
                  >
                    编辑
                  </Button>,
                  <Popconfirm
                    key="delete"
                    title="确认删除该闪卡？"
                    onConfirm={() => handleDeleteFlashcard(item.id)}
                  >
                    <Button type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{item.front}</Text>
                      {item.category && <Tag>{item.category}</Tag>}
                      {item.mastery === 'mastered' && <Tag color="green">已掌握</Tag>}
                      {item.mastery === 'learning' && <Tag color="orange">学习中</Tag>}
                      {item.mastery === 'new' && <Tag color="blue">新卡片</Tag>}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Text type="secondary">背面：{item.back}</Text>
                      <Space size="middle">
                        <Text type="secondary">复习次数：{item.reviewCount}</Text>
                        {item.lastReviewed && (
                          <Text type="secondary">
                            最后复习：{new Date(item.lastReviewed).toLocaleString()}
                          </Text>
                        )}
                      </Space>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <Modal
        open={flashcardModalVisible}
        onCancel={() => {
          setFlashcardModalVisible(false);
          setEditingFlashcard(null);
          flashcardForm.resetFields();
        }}
        title={editingFlashcard ? '编辑闪卡' : '创建闪卡'}
        footer={null}
        width={600}
      >
        <Form
          form={flashcardForm}
          layout="vertical"
          onFinish={editingFlashcard ? handleUpdateFlashcard : handleCreateFlashcard}
        >
          <Form.Item
            label="正面（问题）"
            name="front"
            rules={[{ required: true, message: '请输入正面内容' }]}
          >
            <TextArea
              rows={3}
              placeholder="输入问题或提示"
              size="large"
            />
          </Form.Item>
          <Form.Item
            label="背面（答案）"
            name="back"
            rules={[{ required: true, message: '请输入背面内容' }]}
          >
            <TextArea
              rows={3}
              placeholder="输入答案或解释"
              size="large"
            />
          </Form.Item>
          <Form.Item
            label="分类"
            name="category"
          >
            <Input placeholder="输入分类名称（可选）" size="large" />
          </Form.Item>
          <Form.Item
            label="难度"
            name="difficulty"
            initialValue="medium"
          >
            <Radio.Group size="large">
              <Radio.Button value="easy">简单</Radio.Button>
              <Radio.Button value="medium">中等</Radio.Button>
              <Radio.Button value="hard">困难</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" size="large">
                {editingFlashcard ? '更新' : '创建'}
              </Button>
              <Button onClick={() => {
                setFlashcardModalVisible(false);
                setEditingFlashcard(null);
                flashcardForm.resetFields();
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );

  const flashcardStudyContent = flashcards.length > 0 && studyMode ? (
    <Card
      className="result-card"
      style={{ minHeight: '500px' }}
      title={
        <Space>
          <Text strong>
            第 {currentCardIndex + 1} / {flashcards.length} 张
          </Text>
          <Tag color="blue">{flashcards[currentCardIndex]?.category || '未分类'}</Tag>
        </Space>
      }
      extra={
        <Button onClick={handleEndStudy}>
          结束学习
        </Button>
      }
    >
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center',
        minHeight: '400px',
        padding: '40px 20px'
      }}>
        <div
          onClick={handleFlipCard}
          style={{
            width: '100%',
            maxWidth: '600px',
            minHeight: '300px',
            padding: '40px',
            background: isFlipped ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            borderRadius: '16px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.3s ease',
            color: 'white',
            textAlign: 'center',
          }}
        >
          <Title level={2} style={{ color: 'white', margin: 0 }}>
            {isFlipped 
              ? flashcards[currentCardIndex]?.back 
              : flashcards[currentCardIndex]?.front}
          </Title>
        </div>
        
        <div style={{ marginTop: '30px', textAlign: 'center' }}>
          <Text type="secondary">点击卡片翻转</Text>
        </div>

        {isFlipped && (
          <div style={{ marginTop: '30px', width: '100%', maxWidth: '600px' }}>
            <Space size="large" style={{ width: '100%', justifyContent: 'center' }}>
              <Button
                type="default"
                danger
                icon={<CloseOutlined />}
                size="large"
                onClick={() => handleMarkMastery('new')}
              >
                未掌握
              </Button>
              <Button
                type="default"
                icon={<ReloadOutlined />}
                size="large"
                onClick={() => handleMarkMastery('learning')}
              >
                学习中
              </Button>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                size="large"
                onClick={() => handleMarkMastery('mastered')}
              >
                已掌握
              </Button>
            </Space>
          </div>
        )}

        <div style={{ marginTop: '30px', width: '100%', maxWidth: '600px' }}>
          <Space size="large" style={{ width: '100%', justifyContent: 'center' }}>
            <Button
              onClick={handlePrevCard}
              disabled={currentCardIndex === 0}
              icon={<ReloadOutlined style={{ transform: 'scaleX(-1)' }} />}
            >
              上一张
            </Button>
            <Button
              onClick={handleNextCard}
              disabled={currentCardIndex === flashcards.length - 1}
              icon={<ReloadOutlined />}
            >
              下一张
            </Button>
          </Space>
        </div>
      </div>
    </Card>
  ) : (
    <Card className="result-card">
      <Empty
        description="请先创建闪卡，然后点击'开始学习'按钮"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        style={{ margin: '60px 0' }}
      />
    </Card>
  );

  return (
    <div className="teacher-tools-page">
      <div className="tools-header">
        <Title level={2} className="tools-title">
          <QuestionCircleOutlined style={{ marginRight: 12, color: '#1890ff' }} />
          学生工具
        </Title>
        <Text type="secondary" className="tools-subtitle">
          智能生成题目，创建闪卡辅助学习
        </Text>
      </div>

      <Tabs
        defaultActiveKey="questions"
        size="large"
        className="tools-tabs"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { 
            key: 'questions', 
            label: (
              <span>
                <QuestionCircleOutlined />
                题目生成
              </span>
            ), 
            children: questionsFormContent 
          },
          { 
            key: 'flashcards', 
            label: (
              <span>
                <QuestionCircleOutlined />
                闪卡管理
              </span>
            ), 
            children: flashcardManageContent 
          },
          {
            key: 'study',
            label: (
              <span>
                <RocketOutlined />
                学习闪卡
              </span>
            ),
            children: flashcardStudyContent
          }
        ]}
      />
    </div>
  );
}
