import { 
  Card, 
  Col, 
  Form, 
  Input, 
  InputNumber, 
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
  Modal
} from 'antd';
import {
  FileTextOutlined,
  EditOutlined,
  BookOutlined,
  QuestionCircleOutlined,
  ClockCircleOutlined,
  TrophyOutlined,
  BulbOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DownloadOutlined,
  EyeOutlined
} from '@ant-design/icons';
import { useEffect, useState } from 'react';
import './TeacherToolsPage.css';
import { 
  generateLessonPlan, 
  suggestKnowledgePoints, 
  type LessonPlan as APILessonPlan,
  type LessonPlanMeta,
  listLessonPlans,
  getLessonPlanDetails,
  generateQuestions,
  type Question as APIQuestion
} from '../../services/teacher';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

type LessonPlan = APILessonPlan;
type Question = APIQuestion;

export default function TeacherToolsPage() {
  const [lessonPlanForm] = Form.useForm();
  const [questionsForm] = Form.useForm();
  const [generatingLesson, setGeneratingLesson] = useState(false);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [lessonPlan, setLessonPlan] = useState<LessonPlan | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [kpLoading, setKpLoading] = useState(false);
  const [kpOptions, setKpOptions] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<string>('lesson');
  const [plans, setPlans] = useState<LessonPlanMeta[]>([]);
  const [plansLoading, setPlansLoading] = useState(false);
  const [viewingPlan, setViewingPlan] = useState<{ meta: LessonPlanMeta; plan: LessonPlan } | null>(null);
  const [viewModalVisible, setViewModalVisible] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [answerVisibility, setAnswerVisibility] = useState<Record<number, { showAnswer: boolean; showAnalysis: boolean }>>({});

  const handleGenerateLesson = async (values: any) => {
    try {
      setGeneratingLesson(true);

      const payload = {
        courseName: values.courseName,
        duration: values.duration,
        knowledgePoints: values.knowledgePoints || [],
        difficulty: values.difficulty || 'medium',
        keyPoints: values.keyPoints,
        hardPoints: values.hardPoints,
      };

      const generated = await generateLessonPlan(payload);
      setLessonPlan(generated);
      message.success('教案生成成功！');
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败，请稍后重试';
      message.error(msg);
    } finally {
      setGeneratingLesson(false);
    }
  };

  const handleSuggestKnowledgePoints = async () => {
    try {
      const courseName = lessonPlanForm.getFieldValue('courseName');
      if (!courseName || !courseName.trim()) {
        message.warning('请先输入课程名称');
        return;
      }
      setKpLoading(true);
      const points = await suggestKnowledgePoints(courseName.trim());
      if (!points.length) {
        message.warning('模型未返回有效的知识点，请稍后重试');
        return;
      }
      setKpOptions(points);
      // 默认全选推荐知识点，用户可自行删减
      lessonPlanForm.setFieldsValue({ knowledgePoints: points });
      message.success('已根据课程名称推荐知识点');
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成知识点失败，请稍后重试';
      message.error(msg);
    } finally {
      setKpLoading(false);
    }
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

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('已复制到剪贴板');
  };

  const formatLessonPlanToMarkdown = (plan: LessonPlan, meta?: { topic?: string; difficulty?: string; knowledgePoints?: string[] }) => {
    const lines: string[] = [];
    lines.push(`# ${plan.title || '教案'}`);
    if (meta?.topic || meta?.difficulty || (meta?.knowledgePoints && meta.knowledgePoints.length > 0)) {
      lines.push('');
      lines.push('## 基本信息');
      if (meta.topic) lines.push(`- 课程名称：${meta.topic}`);
      if (meta.difficulty) lines.push(`- 教学难度：${meta.difficulty}`);
      if (meta.knowledgePoints && meta.knowledgePoints.length > 0) {
        lines.push(`- 知识点：${meta.knowledgePoints.join('、')}`);
      }
    }
    lines.push('');
    lines.push('## 教学目标');
    plan.objectives.forEach(obj => lines.push(`- ${obj}`));
    lines.push('');
    lines.push('## 教学重点');
    plan.keyPoints.forEach(point => lines.push(`- ${point}`));
    lines.push('');
    lines.push('## 教学难点');
    plan.hardPoints.forEach(point => lines.push(`- ${point}`));
    lines.push('');
    lines.push('## 教学过程');
    plan.process.forEach(step => {
      lines.push(`### ${step.step}（${step.duration}）`);
      lines.push(step.content);
      lines.push('');
    });
    lines.push('## 课后作业');
    lines.push(plan.homework);
    return lines.join('\n').trim();
  };

  const exportLessonPlan = (plan: LessonPlan, filename: string, meta?: { topic?: string; difficulty?: string; knowledgePoints?: string[] }) => {
    try {
      const safeName = (filename || 'lesson_plan').replace(/[\\/:*?"<>|]/g, '_');
      const content = formatLessonPlanToMarkdown(plan, meta);
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${safeName}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success('教案已导出');
    } catch (error) {
      message.error('导出失败，请稍后重试');
    }
  };

  const handleExportCurrentPlan = () => {
    if (!lessonPlan) return;
    exportLessonPlan(lessonPlan, lessonPlan.title || '教案');
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

  const loadLessonPlans = async () => {
    try {
      setPlansLoading(true);
      const data = await listLessonPlans();
      setPlans(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '获取教案列表失败';
      message.error(msg);
    } finally {
      setPlansLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'plans') {
      loadLessonPlans();
    }
  }, [activeTab]);

  const handleViewLessonPlan = async (meta: LessonPlanMeta) => {
    try {
      const detail = await getLessonPlanDetails(meta.id);
      setViewingPlan({ meta, plan: detail });
      setViewModalVisible(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '获取教案详情失败';
      message.error(msg);
    }
  };

  const lessonPlanFormContent = (
    <Row gutter={24}>
      <Col xs={24} lg={10}>
        <Card 
          className="form-card"
          title={
            <span>
              <EditOutlined style={{ marginRight: 8, color: '#1890ff' }} />
              教案参数设置
            </span>
          }
        >
          <Form 
            form={lessonPlanForm}
            layout="vertical"
            onFinish={handleGenerateLesson}
          >
            <Form.Item 
              label={
                <span>
                  <BookOutlined style={{ marginRight: 4 }} />
                  课程名称
                </span>
              }
              name="courseName" 
              rules={[{ required: true, message: '请输入课程名称' }]}
            >
              <Input placeholder="如：数据结构——数组与指针" size="large" />
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <ClockCircleOutlined style={{ marginRight: 4 }} />
                  课时长度（分钟）
                </span>
              }
              name="duration" 
              initialValue={45}
            >
              <InputNumber 
                min={10} 
                max={180} 
                style={{ width: '100%' }} 
                size="large"
                placeholder="请输入课时长度"
              />
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <BulbOutlined style={{ marginRight: 4 }} />
                  知识点（可选）
                </span>
              }
              name="knowledgePoints"
            >
              <Space.Compact style={{ width: '100%' }}>
                <Select
                  mode="tags"
                  placeholder="可手动输入，或点击右侧按钮智能推荐"
                  size="large"
                  style={{ flex: 1 }}
                  options={kpOptions.map(k => ({ value: k, label: k }))}
                />
                <Button
                  type="default"
                  size="large"
                  loading={kpLoading}
                  onClick={handleSuggestKnowledgePoints}
                >
                  智能推荐
                </Button>
              </Space.Compact>
            </Form.Item>
            <Form.Item 
              label={
                <span>
                  <TrophyOutlined style={{ marginRight: 4 }} />
                  教学难度
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
              label="教学重点" 
              name="keyPoints"
            >
              <TextArea 
                rows={3} 
                placeholder="说明本节课的教学重点" 
                size="large"
              />
            </Form.Item>
            <Form.Item 
              label="教学难点" 
              name="hardPoints"
            >
              <TextArea 
                rows={3} 
                placeholder="说明本节课的教学难点" 
                size="large"
              />
            </Form.Item>
            <Form.Item>
              <Button 
                type="primary" 
                block 
                size="large"
                htmlType="submit"
                loading={generatingLesson}
                icon={<RocketOutlined />}
              >
                {generatingLesson ? '生成中...' : '生成教案'}
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
              <FileTextOutlined style={{ marginRight: 8, color: '#52c41a' }} />
              生成的教案
            </span>
          }
          extra={
            lessonPlan && (
              <Space>
                <Button 
                  type="text" 
                  icon={<CopyOutlined />}
                  onClick={() => handleCopy(JSON.stringify(lessonPlan, null, 2))}
                >
                  复制
                </Button>
                <Button 
                  type="text" 
                  icon={<DownloadOutlined />}
                  onClick={handleExportCurrentPlan}
                >
                  导出
                </Button>
              </Space>
            )
          }
        >
          {!lessonPlan ? (
            <Empty 
              description="填写左侧表单并点击生成教案"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ margin: '60px 0' }}
            />
          ) : (
            <Spin spinning={generatingLesson}>
              <div className="lesson-plan-content">
                <Title level={3} className="lesson-title">
                  {lessonPlan.title}
                </Title>
                
                <Divider orientation="left">
                  <TrophyOutlined style={{ marginRight: 4 }} />
                  教学目标
                </Divider>
                <ul className="lesson-list">
                  {lessonPlan.objectives.map((obj, index) => (
                    <li key={index}>{obj}</li>
                  ))}
                </ul>

                <Divider orientation="left">
                  <BulbOutlined style={{ marginRight: 4 }} />
                  教学重点
                </Divider>
                <div className="points-container">
                  {lessonPlan.keyPoints.map((point, index) => (
                    <Tag key={index} color="blue" style={{ marginBottom: 8 }}>
                      {point}
                    </Tag>
                  ))}
                </div>

                <Divider orientation="left">
                  <QuestionCircleOutlined style={{ marginRight: 4 }} />
                  教学难点
                </Divider>
                <div className="points-container">
                  {lessonPlan.hardPoints.map((point, index) => (
                    <Tag key={index} color="red" style={{ marginBottom: 8 }}>
                      {point}
                    </Tag>
                  ))}
                </div>

                <Divider orientation="left">
                  <ClockCircleOutlined style={{ marginRight: 4 }} />
                  教学过程
                </Divider>
                {lessonPlan.process.map((step, index) => (
                  <div key={index} className="process-step">
                    <div className="step-header">
                      <Tag color="processing" style={{ fontSize: 14, padding: '4px 12px' }}>
                        {step.step}
                      </Tag>
                      <Text type="secondary">
                        <ClockCircleOutlined style={{ marginRight: 4 }} />
                        {step.duration}
                      </Text>
                    </div>
                    <Paragraph style={{ marginTop: 8, marginBottom: 16 }}>
                      {step.content}
                    </Paragraph>
                  </div>
                ))}

                <Divider orientation="left">
                  <BookOutlined style={{ marginRight: 4 }} />
                  课后作业
                </Divider>
                <Paragraph className="homework-content">
                  {lessonPlan.homework}
                </Paragraph>
              </div>
            </Spin>
          )}
        </Card>
      </Col>
    </Row>
  );

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
                  <BulbOutlined style={{ marginRight: 4 }} />
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
                  <FileTextOutlined style={{ marginRight: 4 }} />
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
                  <TrophyOutlined style={{ marginRight: 4 }} />
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
              <InputNumber 
                min={1} 
                max={100} 
                style={{ width: '100%' }} 
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
              <FileTextOutlined style={{ marginRight: 8, color: '#52c41a' }} />
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

  const renderLessonPlanDetail = (plan: LessonPlan) => (
    <div className="lesson-plan-content">
      <Title level={3} className="lesson-title">
        {plan.title}
      </Title>

      <Divider orientation="left">
        <TrophyOutlined style={{ marginRight: 4 }} />
        教学目标
      </Divider>
      <ul className="lesson-list">
        {plan.objectives.map((obj, index) => (
          <li key={index}>{obj}</li>
        ))}
      </ul>

      <Divider orientation="left">
        <BulbOutlined style={{ marginRight: 4 }} />
        教学重点
      </Divider>
      <div className="points-container">
        {plan.keyPoints.map((point, index) => (
          <Tag key={index} color="blue" style={{ marginBottom: 8 }}>
            {point}
          </Tag>
        ))}
      </div>

      <Divider orientation="left">
        <QuestionCircleOutlined style={{ marginRight: 4 }} />
        教学难点
      </Divider>
      <div className="points-container">
        {plan.hardPoints.map((point, index) => (
          <Tag key={index} color="red" style={{ marginBottom: 8 }}>
            {point}
          </Tag>
        ))}
      </div>

      <Divider orientation="left">
        <ClockCircleOutlined style={{ marginRight: 4 }} />
        教学过程
      </Divider>
      {plan.process.map((step, index) => (
        <div key={index} className="process-step">
          <div className="step-header">
            <Tag color="processing" style={{ fontSize: 14, padding: '4px 12px' }}>
              {step.step}
            </Tag>
            <Text type="secondary">
              <ClockCircleOutlined style={{ marginRight: 4 }} />
              {step.duration}
            </Text>
          </div>
          <Paragraph style={{ marginTop: 8, marginBottom: 16 }}>
            {step.content}
          </Paragraph>
        </div>
      ))}

      <Divider orientation="left">
        <BookOutlined style={{ marginRight: 4 }} />
        课后作业
      </Divider>
      <Paragraph className="homework-content">
        {plan.homework}
      </Paragraph>
    </div>
  );

  const lessonPlanManageContent = (
    <Card
      className="result-card"
      title={
        <span>
          <FileTextOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          教案管理
        </span>
      }
    >
      <Spin spinning={plansLoading}>
        {plans.length === 0 ? (
          <Empty
            description="暂无已保存的教案"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ margin: '60px 0' }}
          />
        ) : (
          <List
            itemLayout="horizontal"
            dataSource={plans}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    key="view"
                    type="link"
                    icon={<EyeOutlined />}
                    onClick={() => handleViewLessonPlan(item)}
                  >
                    查看
                  </Button>,
                  <Button
                    key="export"
                    type="link"
                    icon={<DownloadOutlined />}
                    onClick={async () => {
                      try {
                        const detail = await getLessonPlanDetails(item.id);
                        exportLessonPlan(detail, item.title || item.topic || '教案', {
                          topic: item.topic,
                          difficulty: item.difficulty,
                          knowledgePoints: item.knowledge_points,
                        });
                      } catch (e) {
                        const msg = e instanceof Error ? e.message : '导出失败';
                        message.error(msg);
                      }
                    }}
                  >
                    导出
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{item.title}</Text>
                      <Tag>{item.topic}</Tag>
                    </Space>
                  }
                  description={
                    <Space size="middle">
                      <Text type="secondary">
                        难度：{item.difficulty || '中'}
                      </Text>
                      {item.knowledge_points && item.knowledge_points.length > 0 && (
                        <Text type="secondary">
                          知识点：{item.knowledge_points.join('、')}
                        </Text>
                      )}
                      <Text type="secondary">
                        创建时间：{item.created_at?.slice(0, 19).replace('T', ' ')}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>

      <Modal
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        title={viewingPlan?.meta.title || '教案详情'}
        footer={null}
        width={900}
      >
        {viewingPlan ? renderLessonPlanDetail(viewingPlan.plan) : null}
      </Modal>
    </Card>
  );

  return (
    <div className="teacher-tools-page">
      <div className="tools-header">
        <Title level={2} className="tools-title">
          <EditOutlined style={{ marginRight: 12, color: '#1890ff' }} />
          教师工具
        </Title>
        <Text type="secondary" className="tools-subtitle">
          智能生成教案和题目，提升教学效率
        </Text>
      </div>

      <Tabs
        defaultActiveKey="lesson"
        size="large"
        className="tools-tabs"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { 
            key: 'lesson', 
            label: (
              <span>
                <FileTextOutlined />
                教案生成
              </span>
            ), 
            children: lessonPlanFormContent 
          },
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
            key: 'plans',
            label: (
              <span>
                <BookOutlined />
                教案管理
              </span>
            ),
            children: lessonPlanManageContent
          }
        ]}
      />
    </div>
  );
}
