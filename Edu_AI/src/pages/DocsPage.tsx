import {
  Button,
  Card,
  Col,
  List,
  Progress,
  Row,
  Tabs,
  Tag,
  Typography,
  Upload,
  Space,
  Empty,
  Statistic,
  message,
  Popconfirm,
  Tooltip,
  Modal,
  Switch,
  Descriptions,
  Spin,
  Divider
} from 'antd';
import type { UploadProps } from 'antd';
import {
  FilePdfOutlined,
  UploadOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  FolderOutlined,
  CloudUploadOutlined
} from '@ant-design/icons';
import { useState, useEffect } from 'react';
import {
  importDocument,
  getRAGStats,
  deleteDocument,
  listDocuments,
  updateDocumentParticipation,
  getDocumentDetails,
  getDocumentSummary,
  type RAGImportResponse,
  type RAGStats,
  type KnowledgeDocument,
  type DocumentDetail,
} from '../services/rag';
import './DocsPage.css';

const { Title, Paragraph, Text } = Typography;
const { Dragger } = Upload;

const MAX_FILE_MB = 100;

const uploadProps: UploadProps = {
  name: 'file',
  multiple: true,
  accept: '.pdf',
  showUploadList: false,
  beforeUpload: (file) => {
    const isPDF = file.type === 'application/pdf';
    if (!isPDF) {
      message.error('只能上传 PDF 文件！');
      return Upload.LIST_IGNORE;
    }
    const isLtLimit = file.size / 1024 / 1024 < MAX_FILE_MB;
    if (!isLtLimit) {
      message.error(`文件大小不能超过 ${MAX_FILE_MB}MB！`);
      return Upload.LIST_IGNORE;
    }
    return true;
  },
  // TODO: 配置真实上传接口 action
};

interface UploadingFile {
  id: string;
  name: string;
  progress: number;
  status: 'uploading' | 'parsing' | 'success' | 'error' | 'canceled';
  size?: number;
  file?: File;
}

export default function DocsPage() {
  const [uploadingList, setUploadingList] = useState<UploadingFile[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<RAGStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [participationLoading, setParticipationLoading] = useState<string | null>(null);
  const [detailModal, setDetailModal] = useState<{
    visible: boolean;
    loading: boolean;
    data?: DocumentDetail;
  }>({ visible: false, loading: false });
  const [summaryModal, setSummaryModal] = useState<{
    visible: boolean;
    loading: boolean;
    title?: string;
    filePath?: string;
    content?: string;
    updatedAt?: string;
  }>({ visible: false, loading: false });

  const UPLOAD_STORAGE_KEY = 'edu_ai_docs_uploading_tasks';

  // 页面加载时恢复未完成/失败任务（不包含文件本身）
  useEffect(() => {
    try {
      const stored = localStorage.getItem(UPLOAD_STORAGE_KEY);
      if (stored) {
        const parsed: UploadingFile[] = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setUploadingList(parsed);
        }
      }
    } catch {
      // 忽略解析错误
    }
  }, []);

  // 上传任务变化时持久化到 localStorage（去掉 File 对象）
  useEffect(() => {
    const toStore = uploadingList.map(({ file, ...rest }) => rest);
    try {
      localStorage.setItem(UPLOAD_STORAGE_KEY, JSON.stringify(toStore));
    } catch {
      // 忽略存储错误
    }
  }, [uploadingList]);

  // 加载文档列表和统计信息
  useEffect(() => {
    loadDocsAndStats();
  }, []);

  const loadDocsAndStats = async () => {
    try {
      setLoading(true);
      const [statsData, documentsData] = await Promise.all([getRAGStats(), listDocuments()]);
      setStats(statsData);
      setDocuments(documentsData);
    } catch (error) {
      console.error('加载文档列表失败:', error);
      message.error('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    const newFile: UploadingFile = {
      id: Date.now().toString(),
      name: file.name,
      progress: 0,
      status: 'uploading',
      size: file.size / 1024 / 1024,
      file,
    };
    setUploadingList(prev => [...prev, newFile]);
    
    try {
      const result = await importDocument(file, false, (progress) => {
        setUploadingList(prev => prev.map(item => {
          if (item.id === newFile.id) {
            if (item.status === 'canceled') {
              return item;
            }
            let newStatus = item.status;
            if (progress < 50) {
              newStatus = 'uploading';
            } else if (progress < 100) {
              newStatus = 'parsing';
            } else {
              newStatus = 'success';
            }
            return { ...item, progress, status: newStatus };
          }
          return item;
        }));
      });

      if (result.status === 'success') {
        message.success(result.message);
        // 重新加载文档列表
        await loadDocsAndStats();
        // 3秒后从上传列表移除
        setTimeout(() => {
          setUploadingList(prev => prev.filter(item => item.id !== newFile.id));
        }, 3000);
      } else if (result.status === 'skipped') {
        message.info(result.message);
        setUploadingList(prev => prev.map(item => {
          if (item.id === newFile.id) {
            return { ...item, progress: 100, status: 'success' };
          }
          return item;
        }));
        setTimeout(() => {
          setUploadingList(prev => prev.filter(item => item.id !== newFile.id));
        }, 2000);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '上传失败';
      message.error(errorMessage);
      setUploadingList(prev => prev.map(item => {
        if (item.id === newFile.id) {
          return { ...item, status: 'error' as const };
        }
        return item;
      }));
    }
  };

  const handleDelete = async (doc: KnowledgeDocument) => {
    try {
      await deleteDocument(doc.file_path);
      message.success('文档已删除');
      await loadDocsAndStats();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '删除失败';
      message.error(errorMessage);
    }
  };

  const handleParticipationToggle = async (doc: KnowledgeDocument, include: boolean) => {
    try {
      setParticipationLoading(doc.file_path);
      await updateDocumentParticipation(doc.file_path, include);
      setDocuments(prev =>
        prev.map(item =>
          item.file_path === doc.file_path ? { ...item, include_in_search: include } : item
        )
      );
      message.success(include ? '已开启参与检索' : '已从检索中移除');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '更新失败';
      message.error(errorMessage);
    } finally {
      setParticipationLoading(null);
    }
  };

  const handleViewDetails = async (doc: KnowledgeDocument) => {
    setDetailModal({ visible: true, loading: true });
    try {
      const detail = await getDocumentDetails(doc.file_path);
      setDetailModal({ visible: true, loading: false, data: detail });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '获取详情失败';
      message.error(errorMessage);
      setDetailModal({ visible: false, loading: false });
    }
  };

  const handleViewSummary = async (doc: KnowledgeDocument, forceRefresh: boolean = false) => {
    setSummaryModal(prev => ({
      visible: true,
      loading: true,
      title: doc.file_name,
      filePath: doc.file_path,
      content: forceRefresh ? prev.content : undefined,
      updatedAt: doc.summary_updated_at,
    }));
    try {
      const summary = await getDocumentSummary(doc.file_path, forceRefresh);
      setSummaryModal({
        visible: true,
        loading: false,
        title: doc.file_name,
        filePath: doc.file_path,
        content: summary.summary,
        updatedAt: summary.summary_updated_at,
      });
      setDocuments(prev =>
        prev.map(item =>
          item.file_path === doc.file_path
            ? {
                ...item,
                summary: summary.summary,
                summary_updated_at: summary.summary_updated_at,
              }
            : item
        )
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '获取摘要失败';
      message.error(errorMessage);
      setSummaryModal(prev => ({ ...prev, loading: false }));
    }
  };

  const handleRetry = async (id: string) => {
    const target = uploadingList.find(item => item.id === id);
    if (!target || !target.file) {
      message.error('无法重传：原始文件已丢失，请重新选择文件上传');
      return;
    }

    setUploadingList(prev =>
      prev.map(item =>
        item.id === id ? { ...item, progress: 0, status: 'uploading' } : item
      )
    );
    message.info('已重新开始上传');

    try {
      const result = await importDocument(target.file, false, (progress) => {
        setUploadingList(prev =>
          prev.map(item => {
            if (item.id === id) {
              if (item.status === 'canceled') {
                return item;
              }
              let newStatus: UploadingFile['status'] = item.status;
              if (progress < 50) {
                newStatus = 'uploading';
              } else if (progress < 100) {
                newStatus = 'parsing';
              } else {
                newStatus = 'success';
              }
              return { ...item, progress, status: newStatus };
            }
            return item;
          })
        );
      });

      if (result.status === 'success') {
        message.success(result.message);
        await loadDocsAndStats();
        setTimeout(() => {
          setUploadingList(prev => prev.filter(item => item.id !== id));
        }, 3000);
      } else if (result.status === 'skipped') {
        message.info(result.message);
        setUploadingList(prev =>
          prev.map(item =>
            item.id === id ? { ...item, progress: 100, status: 'success' } : item
          )
        );
        setTimeout(() => {
          setUploadingList(prev => prev.filter(item => item.id !== id));
        }, 2000);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '上传失败';
      message.error(errorMessage);
      setUploadingList(prev =>
        prev.map(item =>
          item.id === id ? { ...item, status: 'error' as const } : item
        )
      );
    }
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case '可检索':
        return { color: 'success', icon: <CheckCircleOutlined /> };
      case '处理中':
        return { color: 'processing', icon: <ClockCircleOutlined /> };
      case '已删除':
        return { color: 'default', icon: <DeleteOutlined /> };
      default:
        return { color: 'default', icon: null };
    }
  };

  const getUploadStatusConfig = (status: string) => {
    switch (status) {
      case 'uploading':
        return { text: '上传中', color: '#1890ff' };
      case 'parsing':
        return { text: '解析中', color: '#fa8c16' };
      case 'success':
        return { text: '成功', color: '#52c41a' };
      case 'error':
        return { text: '失败', color: '#ff4d4f' };
      case 'canceled':
        return { text: '已取消', color: '#bfbfbf' };
      default:
        return { text: '未知', color: '#999' };
    }
  };

  const handleCancelUpload = (id: string) => {
    setUploadingList(prev => prev.filter(item => item.id !== id));
    message.info('已取消并移除上传任务');
  };

  const handleClearAllUploads = () => {
    if (uploadingList.length === 0) return;
    setUploadingList([]);
    message.success('已清空上传任务列表');
  };

  const activeDocs = documents.filter(doc => doc.include_in_search);
  const documentCount = stats?.document_count || 0;
  const indexedFilesCount = stats?.indexed_files || 0;

  return (
    <>
    <div className="docs-page">
      <div className="docs-header">
        <Title level={2} className="docs-title">
          <FolderOutlined style={{ marginRight: 12, color: '#1890ff' }} />
          文档管理
        </Title>
        <Text type="secondary" className="docs-subtitle">
          上传和管理您的教学文档，构建专属知识库
        </Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="文档块总数"
              value={documentCount}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="已索引文件"
              value={indexedFilesCount}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="stat-card">
            <Statistic
              title="可检索文档"
              value={activeDocs.length}
              prefix={<CloudUploadOutlined />}
              valueStyle={{ color: '#fa8c16' }}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      <Tabs
        defaultActiveKey="upload"
        size="large"
        className="docs-tabs"
        items={[
          {
            key: 'upload',
            label: (
              <span>
                <UploadOutlined />
                上传文档
              </span>
            ),
            children: (
              <Row gutter={24}>
                <Col xs={24} lg={10}>
                  <Card 
                    className="upload-card"
                    title={
                      <span>
                        <FilePdfOutlined style={{ marginRight: 8, color: '#1890ff' }} />
                        上传 PDF 文档
                      </span>
                    }
                  >
                    <Dragger 
                      {...uploadProps}
                      customRequest={(options) => {
                        if (options.file) {
                          handleUpload(options.file as File);
                        }
                      }}
                      className="upload-dragger"
                    >
                      <p className="ant-upload-drag-icon">
                        <FilePdfOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                      </p>
                      <p className="ant-upload-text">点击或拖拽 PDF 文件到此区域上传</p>
                      <p className="ant-upload-hint">
                        支持单个或批量上传，文件大小不超过 10MB
                      </p>
                    </Dragger>
                    <div className="upload-tips">
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        <FileTextOutlined /> 支持格式：PDF<br />
                        <FileTextOutlined /> 最大文件：{MAX_FILE_MB}MB<br />
                        <FileTextOutlined /> 上传后系统将自动解析文档内容
                      </Text>
                    </div>
                  </Card>
                </Col>
                <Col xs={24} lg={14}>
                  <Card 
                    className="progress-card"
                    title={
                      <Space>
                        <ClockCircleOutlined style={{ marginRight: 8, color: '#fa8c16' }} />
                        <span>上传与解析进度</span>
                        {uploadingList.length > 0 && (
                          <Button type="link" size="small" onClick={handleClearAllUploads}>
                            清空列表
                          </Button>
                        )}
                      </Space>
                    }
                  >
                    {uploadingList.length === 0 ? (
                      <Empty 
                        description="暂无上传任务"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        style={{ margin: '40px 0' }}
                      />
                    ) : (
                      <List
                        dataSource={uploadingList}
                        renderItem={(item) => {
                          const statusConfig = getUploadStatusConfig(item.status);
                          return (
                            <List.Item className="upload-item">
                              <div className="upload-item-content">
                                <div className="upload-item-header">
                                  <FilePdfOutlined style={{ marginRight: 8, color: '#ff4d4f' }} />
                                  <Text strong>{item.name}</Text>
                                  <Tag color={statusConfig.color} style={{ marginLeft: 8 }}>
                                    {statusConfig.text}
                                  </Tag>
                                  {item.size && (
                                    <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                                      ({item.size.toFixed(2)} MB)
                                    </Text>
                                  )}
                                </div>
                                <Progress 
                                  percent={item.progress} 
                                  status={item.status === 'error' ? 'exception' : item.status === 'success' ? 'success' : 'active'}
                                  strokeColor={statusConfig.color}
                                  style={{ marginTop: 8 }}
                                />
                              </div>
                              <Space>
                                {item.status === 'success' ? (
                                  <Tooltip title="查看详情">
                                    <Button type="link" icon={<EyeOutlined />} size="small">
                                      查看
                                    </Button>
                                  </Tooltip>
                                ) : item.status === 'error' ? (
                                  <Tooltip title="重新上传">
                                    <Button 
                                      type="link" 
                                      icon={<ReloadOutlined />} 
                                      size="small"
                                      onClick={() => handleRetry(item.id)}
                                    >
                                      重试
                                    </Button>
                                  </Tooltip>
                                ) : item.status === 'uploading' || item.status === 'parsing' ? (
                                  <Tooltip title="取消解析任务">
                                    <Button
                                      type="link"
                                      danger
                                      size="small"
                                      onClick={() => handleCancelUpload(item.id)}
                                    >
                                      取消
                                    </Button>
                                  </Tooltip>
                                ) : null}
                              </Space>
                            </List.Item>
                          );
                        }}
                      />
                    )}
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: 'list',
            label: (
              <span>
                <FileTextOutlined />
                文档列表
              </span>
            ),
            children: (
              <Card className="docs-list-card">
                {documents.length === 0 ? (
                  <Empty 
                    description="暂无文档"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    style={{ margin: '60px 0' }}
                  />
                ) : (
                  <List
                    dataSource={documents}
                    renderItem={(item) => {
                      const statusConfig = getStatusConfig(item.include_in_search ? '可检索' : '已删除');
                      return (
                        <List.Item className="doc-item" key={item.file_path}>
                          <div className="doc-item-content">
                            <div className="doc-icon">
                              <FilePdfOutlined />
                            </div>
                            <div className="doc-info">
                              <div className="doc-header">
                                <Text strong className="doc-name">{item.file_name}</Text>
                                <Tag 
                                  color={statusConfig.color} 
                                  icon={statusConfig.icon}
                                  style={{ marginLeft: 8 }}
                                >
                                  {item.include_in_search ? '可检索' : '已禁用'}
                                </Tag>
                              </div>
                              <Paragraph 
                                ellipsis={{ rows: 2 }} 
                                className="doc-summary"
                                type="secondary"
                              >
                                {item.summary || '尚未生成摘要，点击“总结”即可获取。'}
                              </Paragraph>
                              <div className="doc-meta">
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  <FileTextOutlined /> {item.file_size ? `${(item.file_size / 1024 / 1024).toFixed(2)} MB` : '大小未知'}
                                  {item.page_count && ` · ${item.page_count} 页`}
                                  {' · '}块数 {item.chunk_count}
                                  {' · '}图片 {item.image_chunk_count ?? 0}
                                  {item.imported_at && (
                                    <>
                                      {' · '}
                                      <ClockCircleOutlined /> {new Date(item.imported_at).toLocaleString('zh-CN')}
                                    </>
                                  )}
                                </Text>
                              </div>
                            </div>
                          </div>
                          <Space className="doc-actions">
                            <Switch
                              checkedChildren="参与"
                              unCheckedChildren="禁用"
                              checked={item.include_in_search}
                              loading={participationLoading === item.file_path}
                              onChange={(checked) => handleParticipationToggle(item, checked)}
                            />
                            <Tooltip title="查看详情">
                              <Button 
                                type="text" 
                                icon={<EyeOutlined />}
                                size="small"
                                onClick={() => handleViewDetails(item)}
                              >
                                详情
                              </Button>
                            </Tooltip>
                            <Tooltip title="查看摘要">
                              <Button 
                                type="text" 
                                icon={<FileTextOutlined />}
                                size="small"
                                onClick={() => handleViewSummary(item)}
                              >
                                总结
                              </Button>
                            </Tooltip>
                            <Popconfirm
                              title="确定要删除这个文档吗？"
                              description="删除后无法恢复"
                              onConfirm={() => handleDelete(item)}
                              okText="确定"
                              cancelText="取消"
                            >
                              <Tooltip title="删除文档">
                                <Button 
                                  type="text" 
                                  danger
                                  icon={<DeleteOutlined />}
                                  size="small"
                                >
                                  删除
                                </Button>
                              </Tooltip>
                            </Popconfirm>
                          </Space>
                        </List.Item>
                      );
                    }}
                  />
                )}
              </Card>
            )
          }
        ]}
      />
    </div>

    <Modal
      open={detailModal.visible}
      onCancel={() => setDetailModal({ visible: false, loading: false })}
      title="文档详情"
      footer={null}
      width={720}
      destroyOnClose
    >
      {detailModal.loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : detailModal.data ? (
        <>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="文件名">{detailModal.data.file_name}</Descriptions.Item>
            <Descriptions.Item label="参与检索">
              {detailModal.data.include_in_search ? '是' : '否'}
            </Descriptions.Item>
            <Descriptions.Item label="导入时间">
              {detailModal.data.imported_at ? new Date(detailModal.data.imported_at).toLocaleString('zh-CN') : '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="文档块数量">{detailModal.data.chunk_count}</Descriptions.Item>
            <Descriptions.Item label="图片块数量">{detailModal.data.image_chunk_count ?? 0}</Descriptions.Item>
            <Descriptions.Item label="页数">{detailModal.data.page_count ?? '未知'}</Descriptions.Item>
          </Descriptions>
          <Divider />
          <Title level={5}>示例片段</Title>
          {detailModal.data.samples.length === 0 ? (
            <Empty description="暂无片段" />
          ) : (
            detailModal.data.samples.map(sample => (
              <Card key={sample.id || `${sample.page}-${sample.content.slice(0, 10)}`} size="small" className="doc-sample-card">
                <Space size={8}>
                  <Text type="secondary">页面：{sample.page ?? '未知'}</Text>
                  <Tag color={sample.modality === 'image' ? 'purple' : 'blue'}>
                    {sample.modality === 'image' ? '图片' : '文本'}
                  </Tag>
                </Space>
                <Paragraph style={{ marginTop: 8 }}>{sample.content}</Paragraph>
                {sample.modality === 'image' && sample.image_path && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    图片路径：{sample.image_path}
                  </Text>
                )}
              </Card>
            ))
          )}
        </>
      ) : (
        <Empty />
      )}
    </Modal>

    <Modal
      open={summaryModal.visible}
      onCancel={() => setSummaryModal({ visible: false, loading: false })}
      title={summaryModal.title || '文档摘要'}
      width={640}
      destroyOnClose
      footer={
        <Space>
          <Button onClick={() => setSummaryModal({ visible: false, loading: false })}>关闭</Button>
          {summaryModal.filePath && (
            <Button
              type="primary"
              loading={summaryModal.loading}
              onClick={() =>
                handleViewSummary(
                  documents.find(doc => doc.file_path === summaryModal.filePath)!,
                  true
                )
              }
            >
              重新生成
            </Button>
          )}
        </Space>
      }
    >
      {summaryModal.loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : summaryModal.content ? (
        <>
          <Paragraph>{summaryModal.content}</Paragraph>
          {summaryModal.updatedAt && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              更新于：{new Date(summaryModal.updatedAt).toLocaleString('zh-CN')}
            </Text>
          )}
        </>
      ) : (
        <Empty description="尚未生成摘要" />
      )}
    </Modal>
    </>
  );
}
