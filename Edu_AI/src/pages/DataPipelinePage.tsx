import {
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Tabs,
  Table,
  Tag,
  Button,
  Typography,
  Progress,
  Tooltip,
  message
} from 'antd';
import {
  DatabaseOutlined,
  SettingOutlined,
  MonitorOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { useState, useEffect } from 'react';
import './DataPipelinePage.css';
import { startCrawl, getOverview, Task, TaskStatus } from '../services/pipeline';

const { Title, Text } = Typography;

export default function DataPipelinePage() {
  const [form] = Form.useForm();
  const [isRunning, setIsRunning] = useState(false);
  const [crawlRows, setCrawlRows] = useState<any[]>([]);
  const [parseRows, setParseRows] = useState<any[]>([]);
  const [chunkRows, setChunkRows] = useState<any[]>([]);

  // 任务状态渲染
  const statusColor: Record<TaskStatus, { color: string; icon: JSX.Element }> = {
    PENDING: { color: 'default', icon: <ClockCircleOutlined /> },
    RUNNING: { color: 'processing', icon: <SyncOutlined spin /> },
    SUCCESS: { color: 'success', icon: <CheckCircleOutlined /> },
    FAILED: { color: 'error', icon: <CloseCircleOutlined /> }
  };
  const renderStatus = (status: TaskStatus | string) => {
    if (typeof status !== 'string') return status;
    const cfg = statusColor[status as TaskStatus] || { color: 'default', icon: null };
    return (
      <Tag color={cfg.color} icon={cfg.icon}>
        {status}
      </Tag>
    );
  };

  // 表头
  const crawlColumns = [
    { title: '任务ID', dataIndex: 'key' },
    { title: '状态', dataIndex: 'status', render: renderStatus },
    {
      title: '进度',
      dataIndex: 'progress',
      render: (p: number) => <Progress percent={p} size="small" status={p === 100 ? 'success' : 'active'} />
    },
    {
      title: '当前',
      dataIndex: 'title',
      render: (t: string) => (
        <Tooltip title={t}>
          <Text ellipsis style={{ maxWidth: 260 }}>
            {t}
          </Text>
        </Tooltip>
      )
    }
  ];

  const simpleColumns = [
    { title: '任务ID', dataIndex: 'key' },
    { title: '状态', dataIndex: 'status', render: renderStatus },
    {
      title: '进度',
      dataIndex: 'progress',
      render: (p: number) => <Progress percent={p} size="small" status={p === 100 ? 'success' : 'active'} />
    },
    {
      title: '文件',
      dataIndex: 'name',
      render: (t: string) => (
        <Tooltip title={t}>
          <Text ellipsis style={{ maxWidth: 260 }}>
            {t}
          </Text>
        </Tooltip>
      )
    }
  ];

  // 定时拉取 overview
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getOverview();
        setCrawlRows(mapCrawl(data.crawl));
        setParseRows(mapSimple(data.parse));
        setChunkRows(mapSimple(data.chunk));
      } catch (e) {
        console.error('overview 获取失败', e);
      }
    };
    fetchData();
    const timer = setInterval(fetchData, 3000);
    return () => clearInterval(timer);
  }, []);

  // map 函数
  const mapCrawl = (tasks: Task[]) =>
    tasks.map(t => ({
      key: t.task_id,
      title: t.details?.current || '--',
      status: t.status,
      progress: t.progress || 0
    }));
  const mapSimple = (tasks: Task[]) =>
    tasks.map(t => ({
      key: t.task_id,
      name: t.details?.current || '--',
      status: t.status,
      progress: t.progress || 0
    }));

  // 表单提交
  const onFinish = async (values: any) => {
    try {
      setIsRunning(true);
      const { task_id } = await startCrawl({ keywords: [values.keyword], pages: values.siteCount || 1 });
      message.success(`已启动任务 ${task_id}`);
    } catch (e: any) {
      message.error(`启动失败: ${e.message || '未知错误'}`);
    } finally {
      setIsRunning(false);
    }
  };

  const onFinishFailed = (info: any) => {
    const msg = info.errorFields?.[0]?.errors?.[0] || '表单校验失败';
    message.error(`启动失败: ${msg}`);
  };

  return (
    <div className="data-pipeline-page">
      <Title level={2}>
        <DatabaseOutlined /> 数据采集管道
      </Title>
      <Tabs defaultActiveKey="config">
        <Tabs.TabPane
          key="config"
          tab={
            <span>
              <SettingOutlined /> 任务配置
            </span>
          }
        >
          <Card>
            <Form form={form} layout="vertical" onFinish={onFinish} onFinishFailed={onFinishFailed}>
              <Form.Item label="关键词" name="keyword" rules={[{ required: true, message: '请输入关键词' }]}> 
                <Input placeholder="输入关键词" />
              </Form.Item>
              <Form.Item label="爬取页数" name="siteCount" initialValue={1}> 
                <InputNumber min={1} max={10} />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={isRunning}>
                  启动
                </Button>
                <Button style={{ marginLeft: 8 }} icon={<PauseCircleOutlined />} onClick={() => setIsRunning(false)}>
                  停止
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Tabs.TabPane>
        <Tabs.TabPane
          key="monitor"
          tab={
            <span>
              <MonitorOutlined /> 流程监控
            </span>
          }
        >
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card title="爬虫任务">
                <Table columns={crawlColumns} dataSource={crawlRows} size="small" pagination={false} />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="PDF 解析">
                <Table columns={simpleColumns} dataSource={parseRows} size="small" pagination={false} />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="文本切块">
                <Table columns={simpleColumns} dataSource={chunkRows} size="small" pagination={false} />
              </Card>
            </Col>
          </Row>
        </Tabs.TabPane>
      </Tabs>
    </div>
  );
}
