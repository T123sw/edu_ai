import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Empty,
  Input,
  Popconfirm,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CloudUploadOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  FileTextOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { useCourseStore } from '../store/course/useCourseStore';
import {
  deleteKnowledgeBaseDocument,
  getKnowledgeBaseDocuments,
  type KnowledgeBaseDocument,
  uploadKnowledgeBaseDocument,
} from '../services/knowledgeBase';
import { registerCreatedJob } from '../jobs/jobStore';
import './KnowledgeBasePage.css';

const { Title, Text, Paragraph } = Typography;

type FilterType = 'all' | 'file' | 'web';

const CATEGORY_STORAGE_KEY = 'edu-ai-kb-category-map';

function loadCategoryMap() {
  try {
    const raw = localStorage.getItem(CATEGORY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function saveCategoryMap(categoryMap: Record<string, string>) {
  localStorage.setItem(CATEGORY_STORAGE_KEY, JSON.stringify(categoryMap));
}

function inferCategory(document: KnowledgeBaseDocument) {
  const name = document.name.toLowerCase();
  if (name.endsWith('.ppt') || name.endsWith('.pptx')) return 'PPT';
  if (name.endsWith('.pdf')) return '教材资料';
  if (name.endsWith('.doc') || name.endsWith('.docx')) return '讲义文档';
  if (document.type === 'web') return '网页采集';
  return '课程素材';
}

export default function KnowledgeBasePage() {
  const { token } = useAuth();
  const { courses, currentCourse, loadCoursesFromBackend } = useCourseStore();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [keyword, setKeyword] = useState('');
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [activeCourseId, setActiveCourseId] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [categoryMap, setCategoryMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!courses.length) {
      void loadCoursesFromBackend();
    }
    setCategoryMap(loadCategoryMap());
  }, [courses.length, loadCoursesFromBackend]);

  useEffect(() => {
    if (activeCourseId) return;
    const preferredId = currentCourse?.id || courses[0]?.id || '';
    if (preferredId) {
      setActiveCourseId(preferredId);
    }
  }, [activeCourseId, courses, currentCourse]);

  useEffect(() => {
    if (!activeCourseId || !token) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function run() {
      try {
        setLoading(true);
        const data = await getKnowledgeBaseDocuments(activeCourseId, token, {
          scopeType: 'course',
          libraryType: 'course',
          aggregate: true,
        });

        if (cancelled) return;

        setDocuments(data);
        setCategoryMap((current) => {
          const next = { ...current };
          let changed = false;
          for (const item of data) {
            if (!next[item.id]) {
              next[item.id] = inferCategory(item);
              changed = true;
            }
          }
          if (changed) {
            saveCategoryMap(next);
          }
          return next;
        });
      } catch (error) {
        if (!cancelled) {
          message.error(error instanceof Error ? error.message : '课程知识库加载失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [activeCourseId, token]);

  const activeCourse = courses.find((course) => course.id === activeCourseId) || currentCourse || null;

  const stats = useMemo(() => {
    const fileCount = documents.filter((item) => item.type === 'file').length;
    const webCount = documents.filter((item) => item.type === 'web').length;
    const selectedCount = selectedIds.length;
    return { fileCount, webCount, selectedCount };
  }, [documents, selectedIds.length]);

  const filteredDocuments = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return documents.filter((item) => {
      if (filterType !== 'all' && item.type !== filterType) {
        return false;
      }
      if (!normalizedKeyword) {
        return true;
      }
      return [item.name, item.course_id, item.url || '', categoryMap[item.id] || inferCategory(item)]
        .join(' ')
        .toLowerCase()
        .includes(normalizedKeyword);
    });
  }, [categoryMap, documents, filterType, keyword]);

  const visibleSelection = useMemo(() => {
    const visibleIds = new Set(filteredDocuments.map((item) => item.id));
    return selectedIds.filter((id) => visibleIds.has(id));
  }, [filteredDocuments, selectedIds]);

  const allVisibleSelected = filteredDocuments.length > 0 && visibleSelection.length === filteredDocuments.length;

  const toggleVisibleSelection = () => {
    if (allVisibleSelected) {
      const visibleSet = new Set(filteredDocuments.map((item) => item.id));
      setSelectedIds((current) => current.filter((id) => !visibleSet.has(id)));
      return;
    }

    const visibleIds = filteredDocuments.map((item) => item.id);
    setSelectedIds((current) => Array.from(new Set([...current, ...visibleIds])));
  };

  const handleUploadFiles = async (fileList: FileList | null) => {
    if (!fileList?.length || !token || !activeCourseId) return;

    setUploading(true);
    try {
      const uploaded: KnowledgeBaseDocument[] = [];
      for (const file of Array.from(fileList)) {
        const result = await uploadKnowledgeBaseDocument(activeCourseId, file, token, undefined, {
          scopeType: 'course',
          libraryType: 'course',
        });
        registerCreatedJob(result.job);
        uploaded.push(result.document);
      }

      setDocuments((current) => [...uploaded, ...current]);
      setCategoryMap((current) => {
        const next = { ...current };
        for (const item of uploaded) {
          next[item.id] = inferCategory(item);
        }
        saveCategoryMap(next);
        return next;
      });

      message.success(`已上传 ${uploaded.length} 个知识库文件`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteSelected = async () => {
    if (!token || !activeCourseId || !selectedIds.length) return;

    try {
      await Promise.all(selectedIds.map((id) => deleteKnowledgeBaseDocument(activeCourseId, id, token)));
      const selectedSet = new Set(selectedIds);
      setDocuments((current) => current.filter((item) => !selectedSet.has(item.id)));
      setSelectedIds([]);
      message.success('已删除选中的知识库条目');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除失败');
    }
  };

  const handleDeleteOne = async (documentId: string) => {
    if (!token || !activeCourseId) return;

    try {
      await deleteKnowledgeBaseDocument(activeCourseId, documentId, token);
      setDocuments((current) => current.filter((item) => item.id !== documentId));
      setSelectedIds((current) => current.filter((id) => id !== documentId));
      message.success('条目已删除');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除失败');
    }
  };

  return (
    <div className="kb-page">
      <section className="kb-shell">
        <div className="kb-shell-copy">
          <div className="kb-shell-kicker">Course Knowledge Base</div>
          <Title level={1} className="kb-shell-title">
            {activeCourse?.title || '课程知识库'}
          </Title>
          <Paragraph className="kb-shell-text">
            保留现有课程知识库接口，直接接入新的页面结构与视觉语言，支持检索、批量选择、上传和删除。
          </Paragraph>
          <Space wrap className="kb-shell-actions">
            <Select
              value={activeCourseId || undefined}
              onChange={setActiveCourseId}
              className="kb-course-select"
              placeholder="选择课程"
              options={courses.map((course) => ({ label: course.title, value: course.id }))}
            />
            <Button
              type="primary"
              icon={<UploadOutlined />}
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              上传文件
            </Button>
            <Popconfirm
              title="确认删除当前勾选的知识库条目吗？"
              okText="删除"
              cancelText="取消"
              disabled={!selectedIds.length}
              onConfirm={() => void handleDeleteSelected()}
            >
              <Button danger icon={<DeleteOutlined />} disabled={!selectedIds.length}>
                批量删除
              </Button>
            </Popconfirm>
          </Space>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="kb-hidden-input"
            onChange={(event) => void handleUploadFiles(event.target.files)}
          />
        </div>

        <div className="kb-shell-stats">
          <div>
            <span>当前课程</span>
            <strong>{activeCourse ? 1 : 0}</strong>
          </div>
          <div>
            <span>文件条目</span>
            <strong>{stats.fileCount}</strong>
          </div>
          <div>
            <span>网页条目</span>
            <strong>{stats.webCount}</strong>
          </div>
          <div>
            <span>已勾选</span>
            <strong>{stats.selectedCount}</strong>
          </div>
        </div>
      </section>

      <div className="kb-stats-grid">
        <Card className="kb-stat-card">
          <Statistic title="知识库总数" value={documents.length} prefix={<DatabaseOutlined />} />
        </Card>
        <Card className="kb-stat-card">
          <Statistic title="文件型素材" value={stats.fileCount} prefix={<FileTextOutlined />} />
        </Card>
        <Card className="kb-stat-card">
          <Statistic title="网页型素材" value={stats.webCount} prefix={<CloudUploadOutlined />} />
        </Card>
      </div>

      <Card className="kb-filter-card">
        <div className="kb-toolbar">
          <div className="kb-filter-chips">
            {(['all', 'file', 'web'] as FilterType[]).map((type) => (
              <button
                key={type}
                type="button"
                className={`kb-filter-chip ${filterType === type ? 'is-active' : ''}`}
                onClick={() => setFilterType(type)}
              >
                {type === 'all' ? '全部' : type === 'file' ? '文件' : '网页'}
              </button>
            ))}
          </div>
          <Input
            allowClear
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            prefix={<SearchOutlined />}
            placeholder="搜索标题、课程、类别或链接"
            className="kb-search"
          />
        </div>
      </Card>

      <Card className="kb-list-card">
        <div className="kb-list-head">
          <button type="button" className="kb-batch-toggle" onClick={toggleVisibleSelection}>
            {allVisibleSelected ? '取消当前页全选' : '全选当前结果'}
          </button>
          <Text type="secondary">共 {filteredDocuments.length} 条结果</Text>
        </div>

        {loading ? (
          <div className="kb-state-block">
            <Spin />
            <span>正在加载课程知识库…</span>
          </div>
        ) : !token ? (
          <div className="kb-state-block">
            <span>当前未登录，无法读取知识库。</span>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <Empty description="当前没有匹配的知识库内容" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div className="kb-document-grid">
            {filteredDocuments.map((item) => {
              const selected = selectedIds.includes(item.id);
              const category = categoryMap[item.id] || inferCategory(item);
              return (
                <article key={item.id} className={`kb-document-card ${selected ? 'is-selected' : ''}`}>
                  <label className="kb-document-check">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={(event) => {
                        setSelectedIds((current) =>
                          event.target.checked
                            ? Array.from(new Set([...current, item.id]))
                            : current.filter((id) => id !== item.id),
                        );
                      }}
                    />
                    <span>选择</span>
                  </label>

                  <div className="kb-document-head">
                    <Tag color={item.type === 'web' ? 'blue' : 'green'}>{item.type === 'web' ? '网页' : '文件'}</Tag>
                    <Tag>{category}</Tag>
                  </div>

                  <h3>{item.name}</h3>
                  <p>{item.url || item.file_path || '课程知识库文档'}</p>

                  <div className="kb-document-meta">
                    <span>{item.course_id}</span>
                    <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
                  </div>

                  <div className="kb-document-actions">
                    {item.url ? (
                      <Button type="link" onClick={() => window.open(item.url, '_blank', 'noopener,noreferrer')}>
                        打开链接
                      </Button>
                    ) : null}
                    <Popconfirm
                      title="确认删除这个知识库条目吗？"
                      okText="删除"
                      cancelText="取消"
                      onConfirm={() => void handleDeleteOne(item.id)}
                    >
                      <Button type="link" danger>
                        删除
                      </Button>
                    </Popconfirm>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
