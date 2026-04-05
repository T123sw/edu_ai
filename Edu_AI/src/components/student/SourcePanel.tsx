import React, { useRef, useState, useEffect } from 'react';
import { Button, Input, Space, Typography, Modal, Divider, Checkbox, Dropdown, MenuProps, Spin, message } from 'antd';
import {
  FilePdfOutlined,
  FileWordOutlined,
  GlobalOutlined,
  LeftOutlined,
  RightOutlined,
  SearchOutlined,
  UploadOutlined,
  MoreOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore'; // 复用教师端的 store
import { useAuth } from '../../context/AuthContext';
import { listDocuments, importDocument, deleteDocument, renameDocument, getDocumentContent, type DocumentContent, type RAGSource } from '../../services/rag';

const { Title, Text } = Typography;

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  onPreviewStateChange?: (open: boolean) => void;
};

interface FileItem {
  key: string;
  title: string;
  type: 'file' | 'web';
  filePath?: string;
}

const getFileIcon = (type: 'file' | 'web', fileName: string, size = 16) => {
  if (type === 'web') {
    return <GlobalOutlined style={{ fontSize: size, color: '#1890ff' }} />;
  }
  const ext = fileName.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') {
    return <FilePdfOutlined style={{ fontSize: size, color: '#D93025' }} />;
  }
  if (ext === 'docx' || ext === 'doc') {
    return <FileWordOutlined style={{ fontSize: size, color: '#2A5699' }} />;
  }
  return <FilePdfOutlined style={{ fontSize: size, color: '#555' }} />;
};

const normalizeFilePath = (raw: string): string => {
  if (!raw) return raw;
  if (raw.startsWith('user_') && raw.includes(':')) {
    return raw.split(':').slice(1).join(':');
  }
  return raw;
};

const SourcePanel: React.FC<Props> = ({ collapsed, onToggleCollapsed, onPreviewStateChange }) => {
  const { selectedDocs, setSelectedDocs, highlightRequest, setHighlightRequest } = useStore();
  const [fileList, setFileList] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>(selectedDocs);
  const [searchValue, setSearchValue] = useState('');
  const [researchModalVisible, setResearchModalVisible] = useState(false);
  const [selectAllChecked, setSelectAllChecked] = useState(false);

  // 预览状态
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [previewContent, setPreviewContent] = useState<DocumentContent | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [highlightedContent, setHighlightedContent] = useState<React.ReactNode>(null);
  const highlightRef = useRef<HTMLElement | null>(null);

  // 重命名
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameSubmitting, setRenameSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const loadDocuments = async () => {
      try {
        setLoading(true);
        const documents = await listDocuments();
        setFileList(documents.map(doc => ({
          key: doc.file_path,
          title: doc.file_name,
          type: 'file' as const,
          filePath: doc.file_path,
        })));
      } catch (error) {
        console.error('获取文档列表失败:', error);
        message.error(error instanceof Error ? error.message : '获取文档列表失败');
        setFileList([]);
      } finally {
        setLoading(false);
      }
    };
    loadDocuments();
  }, []);

  useEffect(() => {
    setCheckedKeys(selectedDocs);
    setSelectAllChecked(fileList.length > 0 && fileList.every(file => selectedDocs.includes(file.key)));
  }, [selectedDocs, fileList]);

  // 监听高亮请求
  useEffect(() => {
    if (!highlightRequest) return;
    const targetPath = normalizeFilePath(highlightRequest.filePath);
    const targetFile = fileList.find(f => normalizeFilePath(f.filePath || f.key) === targetPath);
    if (!targetFile) return;
    openPreview(targetFile.key, true, highlightRequest.source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightRequest?.requestId]);

  const handleHighlight = (fullContent: DocumentContent | null, source: RAGSource | any) => {
    if (!fullContent) {
      setHighlightedContent(null);
      return;
    }
    const highlightText = String((source as any)?.content || '').trim();
    const fullText = fullContent.content;
    if (!highlightText) {
      setHighlightedContent(fullText);
      return;
    }
    const index = fullText.indexOf(highlightText);
    if (index !== -1) {
      const before = fullText.substring(0, index);
      const after = fullText.substring(index + highlightText.length);
      setHighlightedContent(
        <>
          {before}
          <mark ref={el => { highlightRef.current = el; }} style={{ backgroundColor: '#fff59d', padding: '2px 0' }}>
            {highlightText}
          </mark>
          {after}
        </>
      );
    } else {
      setHighlightedContent(fullText);
    }
  };

  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightRequest(null);
    }
  }, [highlightedContent, setHighlightRequest]);

  const onCheck = (key: React.Key, checked: boolean) => {
    const newChecked = checked ? [...checkedKeys, key] : checkedKeys.filter(k => k !== key);
    setCheckedKeys(newChecked);
    setSelectedDocs(newChecked as string[]);
  };

  const handleSelectAll = (checked: boolean) => {
    const allFileKeys = checked ? fileList.map(file => file.key) : [];
    setCheckedKeys(allFileKeys);
    setSelectedDocs(allFileKeys as string[]);
    setSelectAllChecked(checked);
  };

  const reloadDocuments = async () => {
    setLoading(true);
    try {
      const documents = await listDocuments();
      setFileList(documents.map(doc => ({ key: doc.file_path, title: doc.file_name, type: 'file' as const, filePath: doc.file_path })));
    } finally {
      setLoading(false);
    }
  };

  const handleAddSourceClick = () => fileInputRef.current?.click();

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      try {
        message.loading({ content: `正在上传 ${file.name}...`, key: file.name, duration: 0 });
        await importDocument(file);
        message.success({ content: `${file.name} 上传成功`, key: file.name });
      } catch (error) {
        console.error('上传文件失败:', error);
        message.error({ content: error instanceof Error ? error.message : `${file.name} 上传失败`, key: file.name });
      }
    }
    await reloadDocuments();
    event.target.value = '';
  };

  const openPreview = async (fileKey: string, isHighlightTrigger = false, source?: any) => {
    const file = fileList.find(f => f.key === fileKey);
    if (!file || !file.filePath) return;
    try {
      setPreviewOpen(true);
      setPreviewFile(file);
      setPreviewContent(null);
      setHighlightedContent(null);
      onPreviewStateChange?.(true);
      setPreviewLoading(true);
      const content = await getDocumentContent(file.filePath);
      setPreviewContent(content);
      if (isHighlightTrigger && source) {
        handleHighlight(content, source);
      } else {
        setHighlightedContent(content.content);
      }
    } catch (error) {
      console.error('获取文档内容失败:', error);
      message.error(error instanceof Error ? error.message : '获取文档内容失败');
      closePreview();
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setPreviewFile(null);
    setPreviewContent(null);
    setHighlightedContent(null);
    onPreviewStateChange?.(false);
  };

  const openRenameModal = (fileKey: string) => {
    const file = fileList.find(f => f.key === fileKey);
    if (!file) return;
    setRenameTarget(file);
    setRenameValue(file.title);
    setRenameModalVisible(true);
  };

  const handleRenameConfirm = async () => {
    if (!renameTarget) return;
    const newName = renameValue.trim();
    if (!newName) return;
    try {
      setRenameSubmitting(true);
      const updated = await renameDocument(renameTarget.filePath || renameTarget.key, newName);
      setFileList(prev => prev.map(item => (item.key === renameTarget.key ? { ...item, title: updated.file_name } : item)));
      message.success('重命名成功');
      setRenameModalVisible(false);
      if (previewFile?.key === renameTarget.key) {
        setPreviewFile({ ...previewFile, title: updated.file_name });
      }
    } catch (error) {
      console.error('重命名文档失败:', error);
      message.error(error instanceof Error ? error.message : '重命名文档失败');
    } finally {
      setRenameSubmitting(false);
    }
  };

  const handleDeleteFile = async (fileKey: string) => {
    const file = fileList.find(f => f.key === fileKey);
    if (!file || !file.filePath) return;
    try {
      await deleteDocument(file.filePath);
      message.success('删除成功');
      await reloadDocuments();
      if (checkedKeys.includes(fileKey)) {
        setSelectedDocs(checkedKeys.filter(k => k !== fileKey));
      }
      if (previewFile?.key === fileKey) {
        closePreview();
      }
    } catch (error) {
      console.error('删除文档失败:', error);
      message.error(error instanceof Error ? error.message : '删除文档失败');
    }
  };

  if (collapsed) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="展开知识库" style={{ padding: '4px 8px' }} />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {fileList.map(node => (
            <div key={node.key} style={{ marginBottom: 8, display: 'flex', justifyContent: 'center' }}>
              {getFileIcon(node.type, node.title, 20)}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (previewOpen) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 24, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <Space style={{ minWidth: 0 }}>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={closePreview} />
            {previewFile && getFileIcon('file', previewFile.title, 18)}
            <Text strong ellipsis style={{ maxWidth: 320 }}>{previewFile?.title || '文档预览'}</Text>
          </Space>
        </div>
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 8 }}>
          <Spin spinning={previewLoading}>
            {previewContent ? (
              <div>
                <div style={{ marginBottom: 12, padding: '10px', background: '#f5f5f5', borderRadius: 8 }}>
                  <Space wrap><Text strong>总段落数:</Text><Text>{previewContent.total_chunks}</Text></Space>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.8', fontSize: '14px', color: '#333' }}>
                  {highlightedContent}
                </div>
              </div>
            ) : <div style={{ padding: 24, textAlign: 'center' }}><Text type="secondary">加载中...</Text></div>}
          </Spin>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 24, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexShrink: 0 }}>
        <Title level={5} style={{ margin: 0, fontWeight: 600 }}>知识库</Title>
        <Button type="text" icon={<LeftOutlined />} onClick={onToggleCollapsed} aria-label="折叠知识库" style={{ position: 'absolute', right: 0, top: 0, padding: '4px 8px' }} />
      </div>
      <Space.Compact style={{ width: '100%', marginBottom: 16, flexShrink: 0 }}>
        <Input placeholder="深度研究：输入研究主题" size="large" value={searchValue} onChange={(e) => setSearchValue(e.target.value)} />
        <Button type="primary" icon={<SearchOutlined />} size="large" />
      </Space.Compact>
      <div style={{ marginBottom: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 14 }}>选择所有来源</span>
        <Checkbox checked={selectAllChecked} onChange={(e) => handleSelectAll(e.target.checked)} />
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <Spin spinning={loading}>
          {!fileList.length && !loading ? (
            <div style={{ textAlign: 'center', padding: 48 }}><Text type="secondary">暂无文档</Text></div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {fileList.map((file) => {
                const menuItems: MenuProps['items'] = [
                  { key: 'preview', label: '预览文档', icon: <EyeOutlined />, onClick: () => openPreview(file.key) },
                  { key: 'rename', label: '重命名', icon: <EditOutlined />, onClick: () => openRenameModal(file.key) },
                  { key: 'delete', label: '删除', icon: <DeleteOutlined />, danger: true, onClick: () => handleDeleteFile(file.key) },
                ];
                return (
                  <div key={file.key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, cursor: 'pointer' }} onClick={() => openPreview(file.key)} title="点击预览文档">
                      {getFileIcon(file.type, file.title, 16)}
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.title}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
                        <Button type="text" icon={<MoreOutlined />} size="small" style={{ padding: '4px 8px' }} onClick={(e) => e.stopPropagation()} />
                      </Dropdown>
                      <Checkbox checked={checkedKeys.includes(file.key)} onChange={(e) => { e.stopPropagation(); onCheck(file.key, e.target.checked); }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Spin>
      </div>
      <Divider style={{ margin: '16px 0', flexShrink: 0 }} />
      <Space direction="vertical" style={{ width: '100%', flexShrink: 0 }} size="small">
        <input type="file" multiple ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} />
        <Button icon={<UploadOutlined />} type="default" onClick={handleAddSourceClick} size="large" block>上传文档</Button>
      </Space>
      <Modal title="重命名文档" open={renameModalVisible} confirmLoading={renameSubmitting} onOk={handleRenameConfirm} onCancel={() => setRenameModalVisible(false)}>
        <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} onPressEnter={handleRenameConfirm} />
      </Modal>
    </div>
  );
};

export default SourcePanel;
