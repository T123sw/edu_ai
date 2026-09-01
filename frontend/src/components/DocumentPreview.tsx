import React, { useState, useEffect } from 'react';
import { Modal, Spin, message, Tabs, Typography, Button, Card } from 'antd';
import { FileTextOutlined, DownloadOutlined, CloseOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { getDocumentDetails, getDocumentSummary, type DocumentDetail } from '../services/rag';

const { Title, Paragraph, Text } = Typography;

interface DocumentPreviewProps {
  visible: boolean;
  filePath: string;
  fileName: string;
  onClose: () => void;
}

export default function DocumentPreview({ visible, filePath, fileName, onClose }: DocumentPreviewProps) {
  const [loading, setLoading] = useState(false);
  const [documentDetail, setDocumentDetail] = useState<DocumentDetail | null>(null);
  const [summary, setSummary] = useState<string>('');
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<string>('content');

  useEffect(() => {
    if (visible && filePath) {
      // 重置状态，确保每次打开新文档时都重新加载
      setSummary('');
      setSummaryLoading(false);
      setDocumentDetail(null);
      
      // 加载文档详情；摘要页按需手动加载，避免预览时触发旧 LLM 摘要链路。
      loadDocumentDetails();
    } else {
      setDocumentDetail(null);
      setSummary('');
      setSummaryLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, filePath]);

  const loadDocumentDetails = async () => {
    try {
      setLoading(true);
      const detail = await getDocumentDetails(filePath);
      setDocumentDetail(detail);
    } catch (error) {
      console.error('获取文档详情失败:', error);
      message.error(error instanceof Error ? error.message : '获取文档详情失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    if (!filePath) {
      console.warn('loadSummary: filePath 为空');
      return;
    }
    
    try {
      console.log('loadSummary: 开始加载摘要，filePath:', filePath);
      setSummaryLoading(true);
      const summaryData = await getDocumentSummary(filePath, false);
      console.log('loadSummary: 摘要加载成功', summaryData);
      setSummary(summaryData.summary || '');
    } catch (error) {
      console.error('获取文档摘要失败:', error);
      // 摘要加载失败不阻塞预览，只提示
      message.warning(error instanceof Error ? error.message : '获取文档摘要失败，可稍后重试');
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'summary' && !summary) {
      loadSummary();
    }
  };

  const getFileExtension = (filename: string): string => {
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
  };

  const getFileType = (filename: string): 'pdf' | 'doc' | 'docx' | 'txt' | 'other' => {
    const ext = getFileExtension(filename);
    if (ext === 'pdf') return 'pdf';
    if (ext === 'doc') return 'doc';
    if (ext === 'docx') return 'docx';
    if (ext === 'txt') return 'txt';
    return 'other';
  };

  const renderPDFPreview = () => {
    // 构建PDF预览URL（需要后端提供文件访问接口）
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
    // 注意：这里需要后端提供文件访问接口，或者使用文件路径
    const pdfUrl = `${API_BASE_URL}/api/files/${encodeURIComponent(filePath)}`;
    
    return (
      <div style={{ width: '100%', height: '70vh', border: '1px solid #d9d9d9', borderRadius: 4 }}>
        <iframe
          src={pdfUrl}
          style={{ width: '100%', height: '100%', border: 'none' }}
          title={fileName}
          onError={() => {
            message.error('PDF预览失败，请尝试下载文件');
          }}
        />
      </div>
    );
  };

  const renderDocumentContent = () => {
    if (!documentDetail) return null;

    // 如果是PDF，使用iframe预览
    const fileType = getFileType(fileName);
    if (fileType === 'pdf') {
      return renderPDFPreview();
    }

    // 对于其他格式，显示文档样本内容
    const samples = documentDetail.samples || [];
    if (samples.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Text type="secondary">暂无内容预览</Text>
        </div>
      );
    }

    return (
      <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
        {samples.map((sample, index) => (
          <div
            key={index}
            style={{
              marginBottom: 24,
              padding: 16,
              background: '#fafafa',
              borderRadius: 4,
              border: '1px solid #e8e8e8',
            }}
          >
            {sample.page && (
              <Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                第 {sample.page} 页
              </Text>
            )}
            <div style={{ marginBottom: 0, lineHeight: 1.8 }}>
              <ReactMarkdown
                components={{
                  img: ({ src, alt }) => (
                    <img
                      src={String(src || '')}
                      alt={String(alt || '')}
                      style={{
                        maxWidth: '100%',
                        maxHeight: '50vh',
                        objectFit: 'contain',
                        display: 'block',
                        margin: '16px auto',
                        borderRadius: 8,
                        background: '#f5f5f5',
                      }}
                    />
                  ),
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {sample.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const tabItems = [
    {
      key: 'content',
      label: '文档内容',
      children: (
        <Spin spinning={loading}>
          {renderDocumentContent()}
        </Spin>
      ),
    },
    {
      key: 'summary',
      label: '文档摘要',
      children: (
        <Spin spinning={summaryLoading}>
          {summary ? (
            <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8 }}>
              {summary}
            </Paragraph>
          ) : (
            <div style={{ textAlign: 'center', padding: 48 }}>
              <Text type="secondary">点击加载文档摘要</Text>
            </div>
          )}
        </Spin>
      ),
    },
    {
      key: 'info',
      label: '文档信息',
      children: documentDetail ? (
        <div>
          <Paragraph>
            <Text strong>文件名：</Text>
            <Text>{documentDetail.file_name}</Text>
          </Paragraph>
          <Paragraph>
            <Text strong>文件路径：</Text>
            <Text code style={{ fontSize: 12 }}>{documentDetail.file_path}</Text>
          </Paragraph>
          {documentDetail.file_size && (
            <Paragraph>
              <Text strong>文件大小：</Text>
              <Text>{(documentDetail.file_size / 1024 / 1024).toFixed(2)} MB</Text>
            </Paragraph>
          )}
          {documentDetail.page_count && (
            <Paragraph>
              <Text strong>页数：</Text>
              <Text>{documentDetail.page_count} 页</Text>
            </Paragraph>
          )}
          <Paragraph>
            <Text strong>分块数量：</Text>
            <Text>{documentDetail.chunk_count}</Text>
          </Paragraph>
          <Paragraph>
            <Text strong>参与检索：</Text>
            <Text>{documentDetail.include_in_search ? '是' : '否'}</Text>
          </Paragraph>
          {documentDetail.imported_at && (
            <Paragraph>
              <Text strong>导入时间：</Text>
              <Text>{new Date(documentDetail.imported_at).toLocaleString('zh-CN')}</Text>
            </Paragraph>
          )}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Text type="secondary">加载中...</Text>
        </div>
      ),
    },
  ];

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined />
          <span>{fileName}</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="download" icon={<DownloadOutlined />} onClick={() => {
          // 下载文件功能
          const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
          const downloadUrl = `${API_BASE_URL}/api/files/${encodeURIComponent(filePath)}`;
          window.open(downloadUrl, '_blank');
        }}>
          下载文件
        </Button>,
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
      ]}
      width={900}
      style={{ top: 20 }}
      styles={{ body: { maxHeight: '80vh', overflow: 'auto' } }}
    >
      {/* 文档概述：预览时自动显示在顶部 */}
      <Card
        title="文档概述"
        size="small"
        style={{ marginBottom: 16 }}
        loading={summaryLoading}
      >
        {summary ? (
          <div style={{ fontSize: 14, lineHeight: 1.8 }}>
            <ReactMarkdown>{summary}</ReactMarkdown>
          </div>
        ) : (
          <Text type="secondary">
            {summaryLoading ? '正在生成文档概述...' : '暂无概述（点击"文档摘要"标签可手动生成）'}
          </Text>
        )}
      </Card>

      <Tabs
        activeKey={activeTab}
        onChange={handleTabChange}
        items={tabItems}
      />
    </Modal>
  );
}

