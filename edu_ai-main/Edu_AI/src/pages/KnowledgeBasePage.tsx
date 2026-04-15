import { useMemo, useState } from 'react';
import {
  Card,
  Col,
  Row,
  Tabs,
  Typography,
  Tag,
  Input,
  List,
  Space,
  Statistic,
  Empty,
  Tooltip,
  Button,
  Checkbox,
  Popconfirm,
} from 'antd';
import {
  DatabaseOutlined,
  FileTextOutlined,
  CloudServerOutlined,
  SearchOutlined,
  ClockCircleOutlined,
  LinkOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import './KnowledgeBasePage.css';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs as any;

interface KnowledgeItem {
  id: string;
  title: string;
  sourceType: 'crawler' | 'pdf';
  sourceName: string;
  tags: string[];
  summary: string;
  updatedAt: string;
}

const MOCK_ITEMS: KnowledgeItem[] = [
  {
    id: '1',
    title: '鸦片战争背景与爆发',
    sourceType: 'crawler',
    sourceName: '历史百科爬取',
    tags: ['近代史', '战争背景', '中国近代化'],
    summary:
      '介绍鸦片战争前清政府的闭关锁国政策、英国对华贸易逆差以及鸦片走私扩张等历史背景，为理解战争爆发提供整体脉络。',
    updatedAt: '2025-11-30 21:15',
  },
  {
    id: '2',
    title: '高中历史必修一·鸦片战争课文精读',
    sourceType: 'pdf',
    sourceName: '教材 PDF',
    tags: ['教材', '精读', '课堂讲解'],
    summary:
      '节选自高中历史必修一教材，对鸦片战争的时间线、主要战役和《南京条约》内容进行了系统梳理，可直接用于课堂讲解。',
    updatedAt: '2025-11-25 09:42',
  },
  {
    id: '3',
    title: '第一次鸦片战争主要战役一览',
    sourceType: 'crawler',
    sourceName: '开放数据接口',
    tags: ['战役', '数据表', '可视化'],
    summary:
      '按时间顺序罗列鸦片战争中的重要战役节点，包括爆发时间、参战双方、战果和历史影响，可支持后续图表与练习题自动生成。',
    updatedAt: '2025-11-20 14:08',
  },
];

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState<'all' | 'crawler' | 'pdf'>('all');
  const [keyword, setKeyword] = useState('');
  const [items, setItems] = useState<KnowledgeItem[]>(MOCK_ITEMS);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (activeTab === 'crawler' && item.sourceType !== 'crawler') return false;
      if (activeTab === 'pdf' && item.sourceType !== 'pdf') return false;
      if (!keyword.trim()) return true;
      const k = keyword.trim();
      return (
        item.title.includes(k) ||
        item.summary.includes(k) ||
        item.tags.some((t) => t.includes(k)) ||
        item.sourceName.includes(k)
      );
    });
  }, [items, activeTab, keyword]);

  const selectedItemsInView = useMemo(() => {
    const visibleIds = new Set(filteredItems.map((item) => item.id));
    return selectedIds.filter((id) => visibleIds.has(id));
  }, [filteredItems, selectedIds]);

  const allVisibleSelected =
    filteredItems.length > 0 && selectedItemsInView.length === filteredItems.length;
  const isIndeterminate =
    selectedItemsInView.length > 0 && selectedItemsInView.length < filteredItems.length;

  const handleSelectAllVisible = (checked: boolean) => {
    if (checked) {
      const visibleIds = filteredItems.map((item) => item.id);
      setSelectedIds((prev) => Array.from(new Set([...prev, ...visibleIds])));
    } else {
      const visibleSet = new Set(filteredItems.map((item) => item.id));
      setSelectedIds((prev) => prev.filter((id) => !visibleSet.has(id)));
    }
  };

  const handleToggleItem = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      if (checked) {
        return prev.includes(id) ? prev : [...prev, id];
      }
      return prev.filter((itemId) => itemId !== id);
    });
  };

  const handleBatchDelete = () => {
    if (selectedIds.length === 0) return;
    setItems((prev) => prev.filter((item) => !selectedIds.includes(item.id)));
    setSelectedIds([]);
  };

  const crawlerCount = items.filter((i) => i.sourceType === 'crawler').length;
  const pdfCount = items.filter((i) => i.sourceType === 'pdf').length;

  return (
    <div className="kb-page">
      <div className="kb-header">
        <Title level={2} className="kb-title">
          <DatabaseOutlined style={{ marginRight: 12, color: '#1890ff' }} />
          知识库
        </Title>
        <Text type="secondary" className="kb-subtitle">
          统一管理数据爬取正文与 PDF 文档内容，作为教学问答与教案生成的底层知识支撑
        </Text>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card className="kb-stat-card">
            <Statistic
              title="知识条目总数"
              value={MOCK_ITEMS.length}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="kb-stat-card">
            <Statistic
              title="爬取数据条目"
              value={crawlerCount}
              prefix={<CloudServerOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="kb-stat-card">
            <Statistic
              title="PDF 文档条目"
              value={pdfCount}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
      </Row>

      <Card className="kb-filter-card">
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Tabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as 'all' | 'crawler' | 'pdf')}
            >
              <TabPane
                tab={
                  <span>
                    <DatabaseOutlined />
                    全部来源
                  </span>
                }
                key="all"
              />
              <TabPane
                tab={
                  <span>
                    <CloudServerOutlined />
                    爬取数据
                  </span>
                }
                key="crawler"
              />
              <TabPane
                tab={
                  <span>
                    <FileTextOutlined />
                    PDF 文档
                  </span>
                }
                key="pdf"
              />
            </Tabs>
          </Col>
          <Col xs={24} md={12} style={{ textAlign: 'right' }}>
            <Space size="middle" className="kb-actions">
              <Input
                allowClear
                prefix={<SearchOutlined />}
                placeholder="按标题 / 标签 / 来源 搜索知识条目"
                style={{ maxWidth: 360, width: '100%' }}
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
              />
              <Popconfirm
                title="确定要删除所选文档吗？"
                okText="删除"
                cancelText="取消"
                onConfirm={handleBatchDelete}
                disabled={selectedIds.length === 0}
              >
                <Button
                  danger
                  type="primary"
                  icon={<DeleteOutlined />}
                  disabled={selectedIds.length === 0}
                >
                  批量删除
                  {selectedIds.length > 0 ? `（${selectedIds.length}）` : ''}
                </Button>
              </Popconfirm>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card className="kb-list-card">
        <div className="kb-batch-bar">
          <Checkbox
            checked={allVisibleSelected}
            indeterminate={isIndeterminate}
            onChange={(e) => handleSelectAllVisible(e.target.checked)}
          >
            全选当前列表
          </Checkbox>
          <Text type="secondary">
            已选 {selectedIds.length} 条
          </Text>
        </div>
        {filteredItems.length === 0 ? (
          <Empty
            description="暂无符合条件的知识条目"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ margin: '60px 0' }}
          />
        ) : (
          <List
            itemLayout="vertical"
            dataSource={filteredItems}
            renderItem={(item) => (
              <List.Item
                key={item.id}
                className="kb-item"
                actions={[
                  <Space key="meta" size="middle">
                    <Text type="secondary">
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      最近更新：{item.updatedAt}
                    </Text>
                    <Text type="secondary">
                      来源：{item.sourceName}
                    </Text>
                  </Space>,
                  <Button
                    key="view"
                    type="link"
                    icon={<LinkOutlined />}
                    disabled
                  >
                    预览内容（待接入后端）
                  </Button>,
                ]}
              >
                <div className="kb-item-select">
                  <Checkbox
                    checked={selectedIds.includes(item.id)}
                    onChange={(e) => handleToggleItem(item.id, e.target.checked)}
                  />
                </div>
                <List.Item.Meta
                  title={
                    <Space size="small">
                      <Text strong className="kb-item-title">
                        {item.title}
                      </Text>
                      <Tag color={item.sourceType === 'crawler' ? 'green' : 'blue'}>
                        {item.sourceType === 'crawler' ? '爬取数据' : 'PDF 文档'}
                      </Tag>
                    </Space>
                  }
                  description={
                    <Space size={[4, 4]} wrap>
                      {item.tags.map((tag) => (
                        <Tag key={tag} color="geekblue">
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                  }
                />
                <Paragraph className="kb-item-summary">
                  {item.summary}
                </Paragraph>
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}


