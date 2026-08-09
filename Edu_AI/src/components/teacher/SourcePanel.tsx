import React, { useRef, useState, useEffect } from 'react';
import { Button, Input, Space, Typography, Modal, Checkbox, Dropdown, MenuProps, Spin, message, Card, Tag } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import {
  FilePdfOutlined,
  FileWordOutlined,
  FileTextOutlined,
  FileMarkdownOutlined,
  GlobalOutlined,
  PictureOutlined,
  LeftOutlined,
  RightOutlined,
  SearchOutlined,
  UploadOutlined,
  MoreOutlined,
  PlusOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
  ArrowLeftOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { useAuth } from '../../context/AuthContext';
import { getKnowledgeGraph, type KnowledgeGraphNode } from '../../services/teacher/api';
import {
  listDocuments,
  importDocument,
  importImageDocument,
  isImageFileName,
  loadPreviewMediaUrl,
  revokePreviewMediaUrl,
  deleteDocument,
  renameDocument,
  getDocumentContent,
  getDocumentSummary,
  type DocumentContent,
  type RAGSource,
} from '../../services/rag';
import { decodeDisplayText } from '../../services/teacher/displayText.helpers';
import {
  addRAGDocumentToCourseKB,
  deleteKnowledgeBaseDocument,
  getKnowledgeBaseDocumentContent,
  getKnowledgeBaseDocuments,
  reindexKnowledgeBaseDocument,
  retryKnowledgeBaseDocument,
  testKnowledgeBaseDocumentRetrieval,
  uploadKnowledgeBaseDocument,
  type KnowledgeBaseDocument,
  type KnowledgeBaseRetrievalTestResponse,
} from '../../services/knowledgeBase';
import { registerCreatedJob, requestJobRefresh } from '../../jobs/jobStore';
import { deepSearchAndCrawl, getCrawlResults, type CrawlResult } from '../../services/deepsearch';
import { uploadVideo } from '../../services/video';
import type { WorkspaceScope } from '../../services/teacher/workspaceScope';
import {
  collectKnowledgeSubtreeNodeIds,
  collectScopedKnowledgeNodeIds,
} from './knowledgeScopeSelection';
import {
  buildWebsiteFaviconUrl,
  inferWebsiteUrlFromFileName,
} from './websiteIcon';
import {
  locateSourceHighlightRange,
  stripRetrievalContextPrefix,
} from './sourceHighlight';
import './SourcePanel.css';
import { normalizeKnowledgeMarkdown } from '../../stitch/components/knowledgeMarkdown';
import { AUTH_STORAGE_KEY, parseStoredAuthSession } from '../../stitch/authSession';

const { Title, Text } = Typography;
const COURSE_LIBRARY_TYPE = 'course';
const PERSONAL_LIBRARY_TYPE = 'personal';

type Props = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onPreviewStateChange?: (open: boolean) => void;
};

interface FileItem {
  key: string;
  documentId?: string;
  title: string;
  storageName?: string;
  type: 'file' | 'web' | 'image';
  filePath?: string;
  imageUrl?: string;
  sourceIconUrl?: string;
  sourceUrl?: string;
  libraryType?: typeof COURSE_LIBRARY_TYPE | typeof PERSONAL_LIBRARY_TYPE;
  scopeType?: WorkspaceScope['scopeType'];
  scopeId?: string;
  knowledgeStatus?: KnowledgeBaseDocument['status'];
  chunkCount?: number;
  pageCount?: number;
  activeIndexVersion?: string | null;
  knowledgeError?: string | null;
}

const KNOWLEDGE_STATUS_META: Record<
  KnowledgeBaseDocument['status'],
  { label: string; color: string }
> = {
  received: { label: '已接收', color: 'default' },
  parsing: { label: '解析中', color: 'processing' },
  chunking: { label: '切分中', color: 'processing' },
  embedding: { label: '向量化', color: 'processing' },
  indexing: { label: '建索引', color: 'processing' },
  ready: { label: '可检索', color: 'success' },
  partially_ready: { label: '部分可用', color: 'warning' },
  failed: { label: '处理失败', color: 'error' },
};

const imageExts = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'];

const WebsiteIcon: React.FC<{
  iconUrl?: string;
  sourceUrl?: string;
  size: number;
}> = ({ iconUrl, sourceUrl, size }) => {
  const [failed, setFailed] = useState(false);
  const activeIconUrl = iconUrl || buildWebsiteFaviconUrl(sourceUrl);

  useEffect(() => {
    setFailed(false);
  }, [activeIconUrl]);

  if (!activeIconUrl || failed) {
    return <GlobalOutlined style={{ fontSize: size, color: '#1890ff' }} />;
  }

  return (
    <img
      src={activeIconUrl}
      alt=""
      onError={() => setFailed(true)}
      style={{
        width: size,
        height: size,
        borderRadius: 4,
        objectFit: 'cover',
        display: 'block',
      }}
    />
  );
};

const getFileIcon = (
  type: 'file' | 'web' | 'image',
  fileName: string,
  size = 16,
  sourceIconObjectUrl?: string,
  sourceUrl?: string,
) => {
  if (type === 'web') {
    return <WebsiteIcon iconUrl={sourceIconObjectUrl} sourceUrl={sourceUrl} size={size} />;
  }
  if (type === 'image' || isImageFileName(fileName)) {
    return <PictureOutlined style={{ fontSize: size, color: '#13a8a8' }} />;
  }
  const ext = fileName.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') {
    return <FilePdfOutlined style={{ fontSize: size, color: '#D93025' }} />;
  }
  if (ext === 'docx' || ext === 'doc') {
    return <FileWordOutlined style={{ fontSize: size, color: '#2A5699' }} />;
  }
  if (ext === 'md' || ext === 'markdown') {
    return <FileMarkdownOutlined style={{ fontSize: size, color: '#1890ff' }} />;
  }
  if (ext === 'txt') {
    return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
  }
  return <FileTextOutlined style={{ fontSize: size, color: '#555' }} />;
};

const normalizeFilePath = (raw: string): string => {
  // 兼容：source_path 可能是物理路径，也可能是 index_key(user_xxx:...)
  if (!raw) return raw;
  if (raw.startsWith('user_') && raw.includes(':')) {
    return raw.split(':').slice(1).join(':');
  }
  return raw;
};

const isCourseKnowledgeStoragePath = (raw: string | null | undefined): boolean => {
  const normalized = normalizeFilePath(String(raw || '')).replace(/\\/g, '/').toLowerCase();
  return normalized.includes('/course_data/courses/')
    && /\/knowledge_base\/documents(?:-[^/]+)?\//.test(normalized);
};

const toFileItem = (
  doc: any,
  libraryType: typeof COURSE_LIBRARY_TYPE | typeof PERSONAL_LIBRARY_TYPE = PERSONAL_LIBRARY_TYPE,
): FileItem => {
  let displayTitle = decodeDisplayText(doc.file_name);
  if (!displayTitle && doc.source_url) {
    const sourceFallbackTitle = decodeDisplayText(doc.source_title);
    if (sourceFallbackTitle) {
      displayTitle = sourceFallbackTitle;
    } else if (doc.source_domain) {
      displayTitle = `${doc.source_domain} - 网页内容`;
    } else {
      try {
        const url = new URL(doc.source_url);
        displayTitle = `${url.hostname} - 网页内容`;
      } catch {
        displayTitle = doc.file_name;
      }
    }
  }

  const isImage = String(doc.modality || '').toLowerCase() === 'image'
    || String(doc.doc_kind || '').toLowerCase() === 'image'
    || isImageFileName(displayTitle);
  const inferredSourceUrl = inferWebsiteUrlFromFileName(displayTitle);
  const sourceUrl = doc.source_url || inferredSourceUrl;
  const isWeb = Boolean(sourceUrl) || String(doc.doc_kind || '').toLowerCase() === 'web';

  return {
    key: doc.file_path,
    documentId: doc.id,
    title: displayTitle,
    type: isImage ? 'image' : (isWeb ? 'web' : 'file'),
    filePath: doc.file_path,
    imageUrl: doc.image_url,
    sourceIconUrl: doc.source_icon_url,
    sourceUrl,
    libraryType,
  };
};

const toKnowledgeBaseFileItem = (
  doc: KnowledgeBaseDocument,
  fallbackLibraryType: typeof COURSE_LIBRARY_TYPE | typeof PERSONAL_LIBRARY_TYPE,
): FileItem => {
  const title = decodeDisplayText(doc.display_name || doc.name) || doc.display_name || doc.name || doc.url || doc.id;
  const filePath = doc.file_path || doc.url || doc.id;
  const sourceUrl = doc.url || inferWebsiteUrlFromFileName(title);
  const type = doc.type === 'web' || sourceUrl
    ? 'web'
    : (isImageFileName(title) ? 'image' : 'file');

  return {
    key: filePath,
    documentId: doc.id,
    title,
    storageName: doc.name,
    type,
    filePath,
    sourceIconUrl: doc.source_icon_url,
    sourceUrl,
    libraryType: doc.library_type || fallbackLibraryType,
    scopeType: doc.scope_type,
    scopeId: doc.scope_id,
    knowledgeStatus: doc.status,
    chunkCount: doc.chunk_count,
    pageCount: doc.page_count,
    activeIndexVersion: doc.active_index_version,
    knowledgeError: doc.error_message,
  };
};

const findKnowledgeGraphNode = (
  node: KnowledgeGraphNode | null | undefined,
  targetId?: string,
): KnowledgeGraphNode | null => {
  if (!node || !targetId) {
    return null;
  }
  if (node.id === targetId) {
    return node;
  }
  for (const child of node.children || []) {
    const matchedNode = findKnowledgeGraphNode(child, targetId);
    if (matchedNode) {
      return matchedNode;
    }
  }
  return null;
};

const isRenderableImageChunk = (chunk: DocumentContent['chunks'][number] | null | undefined): boolean => {
  return String(chunk?.metadata?.modality || '').toLowerCase() === 'image' && Boolean(chunk?.metadata?.image_url);
};

const buildPreviewTextContent = (content: DocumentContent | null): string => {
  if (!content) {
    return '';
  }

  const textChunks = content.chunks.filter((chunk) => !isRenderableImageChunk(chunk));
  if (textChunks.length === 0) {
    return '';
  }

  return normalizeKnowledgeMarkdown(textChunks.map((chunk) => chunk.content).join('\n\n'));
};

const extractMarkdownImageUrls = (markdownContent: string): string[] => {
  if (!markdownContent) {
    return [];
  }

  const matches = Array.from(markdownContent.matchAll(/!\[[^\]]*]\(([^)]+)\)/g));
  const urls = matches
    .map((match) => (match[1] || '').trim().split(/\s+/)[0]?.replace(/^<|>$/g, ''))
    .filter((value): value is string => Boolean(value));

  return Array.from(new Set(urls));
};

const SourcePanel: React.FC<Props> = ({ collapsed, onToggleCollapsed, courseId, workspaceScope, onPreviewStateChange }) => {
  const { selectedDocs, setSelectedDocs, setScopedSourceDocIds, highlightRequest, setHighlightRequest } = useStore();
  const [videoUploading, setVideoUploading] = useState(false);
  const { token: contextToken } = useAuth();
  // The Stitch shell persists login before this panel mounts, while the legacy
  // AuthContext can still hold its initial empty value. Both use the same
  // canonical session, so fall back to that freshly persisted token.
  const token = parseStoredAuthSession(window.localStorage.getItem(AUTH_STORAGE_KEY))?.token || contextToken || null;
  const [fileList, setFileList] = useState<FileItem[]>([]);
  const [courseFileList, setCourseFileList] = useState<FileItem[]>([]);
  const [personalFileList, setPersonalFileList] = useState<FileItem[]>([]);
  const [courseKnowledgeGraphRoot, setCourseKnowledgeGraphRoot] = useState<KnowledgeGraphNode | null>(null);
  const [expandedCourseNodeIds, setExpandedCourseNodeIds] = useState<string[]>([]);
  const [checkedCourseNodeIds, setCheckedCourseNodeIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>(selectedDocs);
  const [searchValue, setSearchValue] = useState('');
  const [searchDraftValue, setSearchDraftValue] = useState('');
  const [researchModalVisible, setResearchModalVisible] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchResults, setResearchResults] = useState<CrawlResult[]>([]);
  const [selectAllChecked, setSelectAllChecked] = useState(false);
  const [libraryTab, setLibraryTab] = useState<typeof COURSE_LIBRARY_TYPE | typeof PERSONAL_LIBRARY_TYPE>(COURSE_LIBRARY_TYPE);

  // 预览（覆盖列表）
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [previewContent, setPreviewContent] = useState<DocumentContent | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewMediaUrls, setPreviewMediaUrls] = useState<Record<string, string>>({});
  const [listMediaUrls, setListMediaUrls] = useState<Record<string, string>>({});
  const [highlightedContent, setHighlightedContent] = useState<React.ReactNode>(null);
  const [highlightRetrievalMethod, setHighlightRetrievalMethod] = useState<string | null>(null);
  const [unmatchedHighlightText, setUnmatchedHighlightText] = useState<string | null>(null);
  const highlightRef = useRef<HTMLElement | null>(null);
  // 文档摘要
  const [previewSummary, setPreviewSummary] = useState<string>('');
  const [summaryLoading, setSummaryLoading] = useState(false);

  // 重命名
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameSubmitting, setRenameSubmitting] = useState(false);
  const [retrievalTarget, setRetrievalTarget] = useState<FileItem | null>(null);
  const [retrievalQuery, setRetrievalQuery] = useState('');
  const [retrievalResult, setRetrievalResult] = useState<KnowledgeBaseRetrievalTestResponse | null>(null);
  const [retrievalLoading, setRetrievalLoading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const researchAbortRef = useRef<AbortController | null>(null);
  const loadRequestSequenceRef = useRef(0);

  const loadDocumentsForCurrentScope = React.useCallback(async () => {
    const shouldLoadLegacyRagDocuments = workspaceScope?.scopeType !== 'knowledge_point';
    if (courseId && token) {
      const scopeType = workspaceScope?.scopeType || 'course';
      const scopeId = workspaceScope?.scopeId;
      const [courseDocuments, personalDocuments, legacyRagDocuments] = await Promise.all([
        getKnowledgeBaseDocuments(courseId, token, {
          scopeType,
          scopeId,
          aggregate: scopeType === 'course',
          libraryType: COURSE_LIBRARY_TYPE,
          includeDescendants: true,
          sort: 'created_desc',
          limit: 500,
        }),
        getKnowledgeBaseDocuments(courseId, token, {
          scopeType,
          scopeId,
          aggregate: false,
          libraryType: PERSONAL_LIBRARY_TYPE,
          includeDescendants: false,
          sort: 'created_desc',
          limit: 500,
        }),
        shouldLoadLegacyRagDocuments ? listDocuments() : Promise.resolve([]),
      ]);
      return {
        courseFiles: courseDocuments.map((doc) => toKnowledgeBaseFileItem(doc, COURSE_LIBRARY_TYPE)),
        personalFiles: [
          ...personalDocuments.map((doc) => toKnowledgeBaseFileItem(doc, PERSONAL_LIBRARY_TYPE)),
          ...legacyRagDocuments
            .filter((doc) => (
              doc.library_type !== COURSE_LIBRARY_TYPE
              && !doc.course_id
              && !isCourseKnowledgeStoragePath(doc.file_path || doc.source_path)
            ))
            .map((doc) => toFileItem(doc, PERSONAL_LIBRARY_TYPE)),
        ],
      };
    }

    const documents = await listDocuments();
    return {
      courseFiles: [],
      personalFiles: documents.map((doc) => toFileItem(doc, PERSONAL_LIBRARY_TYPE)),
    };
  }, [courseId, token, workspaceScope?.scopeId, workspaceScope?.scopeType]);

  const applyScopedFileList = React.useCallback((formattedFiles: {
    courseFiles: FileItem[];
    personalFiles: FileItem[];
  }) => {
    const combinedFiles = [...formattedFiles.courseFiles, ...formattedFiles.personalFiles];
    setCourseFileList(formattedFiles.courseFiles);
    setPersonalFileList(formattedFiles.personalFiles);
    setFileList(combinedFiles);
    setScopedSourceDocIds(combinedFiles.map((file) => file.key));

    const visibleKeys = new Set(combinedFiles.map((file) => file.key));
    const currentSelectedDocs = useStore.getState().selectedDocs;
    const nextSelectedDocs = workspaceScope?.scopeType === 'knowledge_point'
      ? formattedFiles.courseFiles.map((file) => file.key)
      : currentSelectedDocs.filter((docId) => visibleKeys.has(docId));
    if (nextSelectedDocs.length !== currentSelectedDocs.length || nextSelectedDocs.some((id, index) => id !== currentSelectedDocs[index])) {
      setSelectedDocs(nextSelectedDocs);
    }
  }, [setScopedSourceDocIds, setSelectedDocs, workspaceScope?.scopeType]);

  useEffect(() => {
    if (!courseId) {
      setCourseKnowledgeGraphRoot(null);
      setExpandedCourseNodeIds([]);
      return undefined;
    }

    let cancelled = false;

    const loadCourseKnowledgeGraph = async () => {
      try {
        const graphData = await getKnowledgeGraph(courseId);
        if (cancelled) {
          return;
        }
        setCourseKnowledgeGraphRoot(graphData.root);
        setExpandedCourseNodeIds((current) => {
          if (current.length > 0) {
            return current;
          }
          const defaultNodeId = workspaceScope?.scopeType === 'knowledge_point' && workspaceScope.scopeId
            ? workspaceScope.scopeId
            : graphData.root.id;
          return defaultNodeId ? [defaultNodeId] : [];
        });
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load knowledge graph for source panel:', error);
          setCourseKnowledgeGraphRoot(null);
        }
      }
    };

    void loadCourseKnowledgeGraph();

    return () => {
      cancelled = true;
    };
  }, [courseId, workspaceScope?.scopeId, workspaceScope?.scopeType]);

  useEffect(() => {
    const activeNodeId = workspaceScope?.scopeType === 'knowledge_point' && workspaceScope.scopeId
      ? workspaceScope.scopeId
      : courseKnowledgeGraphRoot?.id;
    if (!activeNodeId) {
      return;
    }
    setExpandedCourseNodeIds((current) => (
      current.includes(activeNodeId) ? current : [...current, activeNodeId]
    ));
  }, [courseKnowledgeGraphRoot?.id, workspaceScope?.scopeId, workspaceScope?.scopeType]);

  useEffect(() => {
    if (workspaceScope?.scopeType !== 'knowledge_point') {
      setCheckedCourseNodeIds([]);
      return;
    }
    setCheckedCourseNodeIds(
      collectScopedKnowledgeNodeIds(
        courseKnowledgeGraphRoot,
        workspaceScope.scopeId,
      ),
    );
  }, [courseKnowledgeGraphRoot, workspaceScope?.scopeId, workspaceScope?.scopeType]);

  useEffect(() => {
    return () => {
      setPreviewMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      setListMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
    };
  }, []);

  useEffect(() => {
    const targetUrls = new Set<string>();
    for (const file of fileList) {
      if (file.sourceIconUrl) {
        targetUrls.add(file.sourceIconUrl);
      }
    }

    if (targetUrls.size === 0) {
      setListMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllListMedia = async () => {
      const resolvedEntries = await Promise.all(
        Array.from(targetUrls).map(async (iconUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(iconUrl);
            return [iconUrl, objectUrl] as const;
          } catch (error) {
            console.error('加载站点图标失败:', iconUrl, error);
            return [iconUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextMediaUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setListMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextMediaUrls;
      });
    };

    loadAllListMedia();

    return () => {
      cancelled = true;
    };
  }, [fileList]);

  useEffect(() => {
    const targetUrls = new Set<string>();
    const previewTextContent = buildPreviewTextContent(previewContent);

    if (previewFile?.type === 'image' && previewFile.imageUrl) {
      targetUrls.add(previewFile.imageUrl);
    }

    for (const imageUrl of extractMarkdownImageUrls(previewTextContent)) {
      targetUrls.add(imageUrl);
    }

    for (const chunk of previewContent?.chunks ?? []) {
      const imageUrl = chunk.metadata?.image_url;
      if (isRenderableImageChunk(chunk) && typeof imageUrl === 'string' && imageUrl) {
        targetUrls.add(imageUrl);
      }
    }

    if (targetUrls.size === 0) {
      setPreviewMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllPreviewMedia = async () => {
      const resolvedEntries = await Promise.all(
        Array.from(targetUrls).map(async (imageUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(imageUrl);
            return [imageUrl, objectUrl] as const;
          } catch (error) {
            console.error('加载预览图片失败:', imageUrl, error);
            return [imageUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextMediaUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setPreviewMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextMediaUrls;
      });
    };

    loadAllPreviewMedia();

    return () => {
      cancelled = true;
    };
  }, [previewFile?.imageUrl, previewFile?.type, previewContent]);

  useEffect(() => {
    let cancelled = false;

    const loadDocuments = async () => {
      const requestId = ++loadRequestSequenceRef.current;
      try {
        setLoading(true);
        const formattedFiles = await loadDocumentsForCurrentScope();
        if (cancelled || requestId !== loadRequestSequenceRef.current) {
          return;
        }
        applyScopedFileList(formattedFiles);
      } catch (error) {
        if (cancelled || requestId !== loadRequestSequenceRef.current) {
          return;
        }
        console.error('获取文档列表失败:', error);
        message.error(error instanceof Error ? error.message : '获取文档列表失败');
        setFileList([]);
      } finally {
        if (!cancelled && requestId === loadRequestSequenceRef.current) {
          setLoading(false);
        }
      }
    };

    void loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [applyScopedFileList, loadDocumentsForCurrentScope]);

  useEffect(() => {
    setCheckedKeys(selectedDocs);
    setSelectAllChecked(
      fileList.length > 0 && fileList.every((file) => selectedDocs.includes(file.key)),
    );
  }, [selectedDocs, fileList]);

  // 监听高亮请求（依赖 requestId，确保重复点击也触发）
  useEffect(() => {
    if (!highlightRequest) {
      console.log('SourcePanel: 没有高亮请求');
      return;
    }

    console.log('SourcePanel: 收到高亮请求:', highlightRequest);

    // 如果文件列表为空，等待一下再重试（最多等待3秒）
    if (fileList.length === 0) {
      console.log('SourcePanel: 文件列表为空，等待加载...');
      const timeoutId = setTimeout(() => {
        console.log('SourcePanel: 文件列表加载超时，尝试直接处理');
        // 即使文件列表为空，也尝试处理（可能文件列表还在加载中）
      }, 1000);
      return () => clearTimeout(timeoutId);
    }

    const requestPath = highlightRequest.filePath;
    console.log('SourcePanel: 查找文件路径:', requestPath);
    console.log('SourcePanel: 当前文件列表:', fileList.map(f => ({ key: f.key, filePath: f.filePath, title: f.title })));
    
    // 兼容多种路径格式的匹配：
    // 1. requestPath 可能是文件名（如：adac374b89a04df79413f80e23311cb9_第1章计算思维与问题求解.pdf）
    // 2. requestPath 可能是 source_key（user_owner:physical_path）
    // 3. requestPath 可能是物理路径
    // fileList 中的 filePath 是 source_key 格式（user_owner:physical_path）
    const targetFile = fileList.find(f => {
      const filePath = f.filePath || f.key;
      const fileName = f.title;
      const storageName = f.storageName || fileName;
      
      // 1. 直接匹配（完全一致）
      if (filePath === requestPath) {
        console.log('SourcePanel: 直接匹配成功:', filePath);
        return true;
      }
      
      // 2. 文件名匹配（requestPath 是文件名，filePath 是 source_key）
      if ((fileName && requestPath.includes(fileName)) || (storageName && requestPath.includes(storageName))) {
        console.log('SourcePanel: 文件名匹配成功:', storageName);
        return true;
      }
      if (filePath && requestPath.includes(fileName)) {
        console.log('SourcePanel: 文件名包含匹配成功:', fileName);
        return true;
      }
      
      // 3. 规范化后匹配
      const normalizedRequest = normalizeFilePath(requestPath);
      const normalizedFile = normalizeFilePath(filePath);
      if (normalizedRequest === normalizedFile) {
        console.log('SourcePanel: 规范化匹配成功:', normalizedRequest);
        return true;
      }
      
      // 4. 如果 filePath 是 source_key 格式，提取物理路径部分进行匹配
      if (filePath.startsWith('user_') && filePath.includes(':')) {
        const physicalPath = filePath.split(':', 1)[1] || filePath.substring(filePath.indexOf(':') + 1);
        // 检查 requestPath 是否包含物理路径的文件名部分
        const physicalFileName = physicalPath.split(/[/\\]/).pop() || '';
        if (requestPath.includes(physicalFileName) || physicalFileName.includes(requestPath)) {
          console.log('SourcePanel: 物理路径文件名匹配成功:', physicalFileName);
          return true;
        }
        // 检查 requestPath 是否包含物理路径
        if (physicalPath.includes(requestPath) || requestPath.includes(physicalPath)) {
          console.log('SourcePanel: 物理路径匹配成功:', physicalPath);
          return true;
        }
      }
      
      // 5. 如果 requestPath 是 source_key 格式，提取物理路径部分进行匹配
      if (requestPath.startsWith('user_') && requestPath.includes(':')) {
        const physicalPath = requestPath.split(':', 1)[1] || requestPath.substring(requestPath.indexOf(':') + 1);
        if (filePath.includes(physicalPath) || physicalPath.includes(filePath)) {
          console.log('SourcePanel: requestPath 物理路径匹配成功:', physicalPath);
          return true;
        }
      }
      
      return false;
    });

    if (!targetFile) {
      console.warn('SourcePanel: 未在知识库列表中找到对应文件，无法打开预览:', {
        requestPath,
        fileList: fileList.map(f => f.filePath || f.key),
        fileListLength: fileList.length
      });
      return;
    }

    console.log('SourcePanel: 找到目标文件，打开预览:', targetFile.key);
    // 打开预览并加载文档
    openPreview(targetFile.key, true, highlightRequest.source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightRequest?.requestId, fileList.length]);

  const handleHighlight = (fullContent: DocumentContent | null, source: RAGSource | any) => {
    if (!fullContent) {
      setHighlightedContent(null);
      setHighlightRetrievalMethod(null);
      setUnmatchedHighlightText(null);
      return;
    }

    setHighlightRetrievalMethod(String((source as any)?.retrieval_method || '').trim() || null);
    setUnmatchedHighlightText(null);

    // 获取完整的文本块内容（这是要高亮的完整内容）
    const highlightText = String((source as any)?.content || '').trim();
    const fullText = buildPreviewTextContent(fullContent);

    if (!highlightText) {
      setHighlightedContent(fullText);
      return;
    }

    // 规范化文本：移除多余空格和换行，便于匹配
    const normalizeText = (text: string) => {
      return text.replace(/\s+/g, ' ').trim();
    };

    const normalizedHighlight = normalizeText(highlightText);
    const normalizedFull = normalizeText(fullText);

    // Match the complete retrieved child chunk and map normalized whitespace
    // back to its exact range in the original document.
    const locatedRange = locateSourceHighlightRange(fullText, highlightText);
    let index = locatedRange?.start ?? -1;
    let matchLength = locatedRange ? locatedRange.end - locatedRange.start : 0;

    if (index === -1) {
      // Never present repeated keywords as if they were the retrieved chunk.
      setUnmatchedHighlightText(stripRetrievalContextPrefix(highlightText));
      setHighlightedContent(fullText);
      return;
    }

    // 策略2：如果精确匹配失败，尝试规范化后的匹配
    if (index === -1) {
      const normalizedIndex = normalizedFull.indexOf(normalizedHighlight);
      if (normalizedIndex !== -1) {
        // 找到规范化后的位置，需要在原始文本中找到对应的位置
        // 使用滑动窗口方法找到最接近的匹配位置
        const targetLength = highlightText.length;
        let bestMatch = { index: -1, similarity: 0 };
        
        // 在原始文本中搜索，找到与 highlightText 最相似的位置
        for (let i = 0; i <= fullText.length - targetLength; i++) {
          const candidate = fullText.substring(i, i + targetLength);
          const normalizedCandidate = normalizeText(candidate);
          
          // 计算相似度（简单方法：计算公共字符数）
          let commonChars = 0;
          const minLen = Math.min(normalizedHighlight.length, normalizedCandidate.length);
          for (let j = 0; j < minLen; j++) {
            if (normalizedHighlight[j] === normalizedCandidate[j]) {
              commonChars++;
            }
          }
          const similarity = commonChars / Math.max(normalizedHighlight.length, normalizedCandidate.length);
          
          if (similarity > bestMatch.similarity && similarity > 0.7) {
            bestMatch = { index: i, similarity };
          }
        }
        
        if (bestMatch.index !== -1) {
          index = bestMatch.index;
          matchLength = targetLength;
        }
      }
    }

    // Legacy fuzzy fallback remains unreachable for unmatched chunks. It is
    // retained temporarily to keep this focused fix isolated from rendering.
    if (index === -1) {
      const keywords = highlightText.split(/\s+/).filter(k => k.length > 2);
      if (keywords.length > 0) {
        // 查找第一个关键词的位置
        const firstKeyword = keywords[0];
        const keywordIndex = fullText.indexOf(firstKeyword);
        if (keywordIndex !== -1) {
          // 找到关键词，尝试在其周围查找整个文本块
          // 向前和向后扩展，寻找最匹配的区域
          const searchWindow = Math.min(highlightText.length * 2, fullText.length - keywordIndex);
          let bestStart = keywordIndex;
          let bestEnd = keywordIndex + searchWindow;
          let bestSimilarity = 0;
          
          // 尝试不同的起始位置
          for (let start = Math.max(0, keywordIndex - 200); start <= keywordIndex; start++) {
            const end = Math.min(fullText.length, start + highlightText.length);
            const candidate = fullText.substring(start, end);
            const normalizedCandidate = normalizeText(candidate);
            
            // 计算相似度
            let commonChars = 0;
            const minLen = Math.min(normalizedHighlight.length, normalizedCandidate.length);
            for (let j = 0; j < minLen; j++) {
              if (normalizedHighlight[j] === normalizedCandidate[j]) {
                commonChars++;
              }
            }
            const similarity = commonChars / Math.max(normalizedHighlight.length, normalizedCandidate.length);
            
            if (similarity > bestSimilarity && similarity > 0.6) {
              bestSimilarity = similarity;
              bestStart = start;
              bestEnd = Math.min(fullText.length, start + highlightText.length);
            }
          }
          
          if (bestSimilarity > 0.6) {
            index = bestStart;
            matchLength = bestEnd - bestStart;
          }
        }
      }
    }

    // 如果找到了匹配位置，高亮整个文本块
    if (index !== -1) {
      const before = fullText.substring(0, index);
      const highlighted = fullText.substring(index, index + matchLength);
      const after = fullText.substring(index + matchLength);
      
      setHighlightedContent(
        <>
          {before}
          <mark
            ref={(el) => {
              highlightRef.current = el;
            }}
            style={{ 
              backgroundColor: '#fff59d', 
              padding: '4px 2px', 
              fontWeight: 500,
              borderRadius: '3px',
              display: 'inline-block',
              width: '100%'
            }}
          >
            {highlighted}
          </mark>
          {after}
        </>
      );
    } else {
      // 如果完全找不到匹配，高亮所有关键词
      const keywords = highlightText.split(/\s+/).filter(k => k.length > 2).slice(0, 5);
      if (keywords.length > 0) {
        const parts: (string | JSX.Element)[] = [];
        let lastIndex = 0;
        let firstMarkIndex = -1;
        
        // 查找所有关键词位置
        const matches: Array<{ start: number; end: number; keyword: string }> = [];
        keywords.forEach(keyword => {
          let searchIndex = 0;
          while (searchIndex < fullText.length) {
            const foundIndex = fullText.indexOf(keyword, searchIndex);
            if (foundIndex === -1) break;
            matches.push({ start: foundIndex, end: foundIndex + keyword.length, keyword });
            searchIndex = foundIndex + 1;
          }
        });
        
        // 按位置排序并合并重叠
        matches.sort((a, b) => a.start - b.start);
        const mergedMatches: Array<{ start: number; end: number }> = [];
        matches.forEach(match => {
          if (mergedMatches.length === 0 || match.start > mergedMatches[mergedMatches.length - 1].end) {
            mergedMatches.push({ start: match.start, end: match.end });
            if (firstMarkIndex === -1) firstMarkIndex = mergedMatches.length - 1;
          } else {
            mergedMatches[mergedMatches.length - 1].end = Math.max(
              mergedMatches[mergedMatches.length - 1].end,
              match.end
            );
          }
        });
        
        // 构建高亮内容
        mergedMatches.forEach((match, idx) => {
          if (match.start > lastIndex) {
            parts.push(fullText.substring(lastIndex, match.start));
          }
          const markContent = fullText.substring(match.start, match.end);
          parts.push(
            <mark
              key={idx}
              ref={idx === firstMarkIndex ? (el) => {
                highlightRef.current = el;
              } : undefined}
              style={{ backgroundColor: '#fff59d', padding: '2px 0', fontWeight: 500 }}
            >
              {markContent}
            </mark>
          );
          lastIndex = match.end;
        });
        
        if (lastIndex < fullText.length) {
          parts.push(fullText.substring(lastIndex));
        }
        
        setHighlightedContent(<>{parts}</>);
      } else {
        // 完全找不到，直接展示全文
        setHighlightedContent(fullText);
      }
    }
  };

  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightRequest(null);
    }
  }, [highlightedContent, setHighlightRequest]);

  const applyCheckedFileKeys = React.useCallback((nextKeys: React.Key[]) => {
    const dedupedKeys = Array.from(new Set(nextKeys));
    setCheckedKeys(dedupedKeys);
    setSelectedDocs(dedupedKeys as string[]);
    setSelectAllChecked(fileList.length > 0 && fileList.every((file) => dedupedKeys.includes(file.key)));
  }, [fileList, setSelectedDocs]);

  const onCheck = (key: React.Key, checked: boolean) => {
    const newChecked = checked ? [...checkedKeys, key] : checkedKeys.filter(k => k !== key);
    applyCheckedFileKeys(newChecked);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allFileKeys = fileList.map(file => file.key);
      applyCheckedFileKeys(allFileKeys);
    } else {
      applyCheckedFileKeys([]);
    }
  };

  const reloadDocuments = React.useCallback(async () => {
    setLoading(true);
    try {
      const formattedFiles = await loadDocumentsForCurrentScope();
      applyScopedFileList(formattedFiles);
    } finally {
      setLoading(false);
    }
  }, [applyScopedFileList, loadDocumentsForCurrentScope]);

  useEffect(() => {
    const handleKnowledgeDocumentUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ courseId?: string }>).detail;
      if (!detail?.courseId || detail.courseId === courseId) {
        void reloadDocuments();
      }
    };
    window.addEventListener('edu-ai:knowledge-document-updated', handleKnowledgeDocumentUpdated);
    return () => {
      window.removeEventListener('edu-ai:knowledge-document-updated', handleKnowledgeDocumentUpdated);
    };
  }, [courseId, reloadDocuments]);

  const handleAddSourceClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext = `.${(file.name.split('.').pop() || '').toLowerCase()}`;
      const videoExts = ['.mp4', '.mov', '.mkv', '.avi', '.webm'];

      try {
        message.loading({ content: `正在上传 ${file.name}...`, key: `upload-${i}`, duration: 0 });

        if (!videoExts.includes(ext) && courseId && token) {
          const uploadResult = await uploadKnowledgeBaseDocument(courseId, file, token, (progress) => {
            console.log(`知识库上传进度: ${progress}%`);
          }, {
            scopeType: workspaceScope?.scopeType,
            scopeId: workspaceScope?.scopeId,
            libraryType: PERSONAL_LIBRARY_TYPE,
          });
          registerCreatedJob(uploadResult.job);
          message.success({
            content: `${file.name} 已接收，正在后台建立索引`,
            key: `upload-${i}`,
          });
        } else if (imageExts.includes(ext)) {
          await importImageDocument(file, (progress) => {
            console.log(`图片上传进度: ${progress}%`);
          });
          message.success({ content: `${file.name} 图片入库完成`, key: `upload-${i}` });
        } else if (videoExts.includes(ext)) {
          if (!courseId) {
            throw new Error('请先进入具体课程后再上传视频');
          }
          setVideoUploading(true);
          const uploadRes = await uploadVideo({
            file,
            courseId,
            windowSeconds: 30,
            strideSeconds: 20,
          });
          requestJobRefresh(uploadRes.job_id);
          message.success({
            content: `${file.name} 已上传，后台入库任务可在任务中心查看`,
            key: `upload-${i}`,
          });
        } else {
          await importDocument(file, false, (progress) => {
            console.log(`上传进度: ${progress}%`);
          });
          message.success({ content: `${file.name} 上传成功`, key: `upload-${i}` });
        }
      } catch (error) {
        console.error('上传文件失败:', error);
        message.error({
          content: error instanceof Error ? error.message : `${file.name} 上传失败`,
          key: `upload-${i}`,
        });
      } finally {
        setVideoUploading(false);
      }
    }

    await reloadDocuments();
    event.target.value = '';
  };

  const closeResearchModal = (showCancelMessage = false) => {
    if (researchAbortRef.current) {
      researchAbortRef.current.abort();
      researchAbortRef.current = null;
    }
    setResearchLoading(false);
    setResearchModalVisible(false);
    setSearchValue('');
    setSearchDraftValue('');
    setResearchResults([]);
    if (showCancelMessage) {
      message.info('已取消深度研究');
    }
  };

  const handleResearchConfirm = async () => {
    // 已有结果时，点击确认应关闭弹窗，而不是再次触发研究
    if (researchResults.length > 0 && !researchLoading) {
      closeResearchModal(false);
      return;
    }

    const normalizedQuery = searchDraftValue.trim();

    if (!normalizedQuery) {
      message.warning('请输入研究主题');
      return;
    }

    setSearchValue(normalizedQuery);
    setResearchLoading(true);
    setResearchResults([]);

    try {
      // 取消上一次未完成的研究请求
      if (researchAbortRef.current) {
        researchAbortRef.current.abort();
      }
      const controller = new AbortController();
      researchAbortRef.current = controller;

      console.log('[深度研究] 开始搜索:', normalizedQuery);
      message.info('开始深度搜索和爬取，这可能需要几分钟时间...', 10);
      
      const response = await deepSearchAndCrawl({
        query: normalizedQuery,
        depth: 'full',
        max_urls: 5,
        crawl_timeout: 60,
        course_id: courseId,
        scope_type: workspaceScope?.scopeType,
        scope_id: workspaceScope?.scopeId,
      }, { signal: controller.signal });

      console.log('[深度研究] 搜索响应:', response);

      if (!response.ok) {
        message.error(response.message || '搜索失败');
        return;
      }

      if (!response.batch_id) {
        message.warning('未找到相关链接');
        return;
      }

      // 获取详细结果
      console.log('[深度研究] 获取详细结果，batch_id:', response.batch_id);
      const resultsResponse = await getCrawlResults(response.batch_id, { signal: controller.signal });
      
      console.log('[深度研究] 详细结果响应:', resultsResponse);
      
      if (resultsResponse.ok && resultsResponse.results) {
        setResearchResults(resultsResponse.results);
        // 深度研究结果已在后端入库到知识库（RAG文档），刷新列表即可看到
        await reloadDocuments();
        message.success(`研究完成，已同步到文档列表（成功: ${resultsResponse.success_count}, 失败: ${resultsResponse.failed_count}）`);
        closeResearchModal(false);
      } else {
        // 如果响应中已包含结果
        if (response.results && response.results.length > 0) {
          setResearchResults(response.results);
          await reloadDocuments();
          message.success(`研究完成，已同步到文档列表（成功: ${response.success_count}, 失败: ${response.failed_count}）`);
          closeResearchModal(false);
        } else {
          message.warning(resultsResponse.message || '获取结果详情失败');
        }
      }
    } catch (error: any) {
      console.error('[深度研究] 搜索错误:', error);
      // AbortController 触发的取消
      if (error?.name === 'AbortError' || String(error?.message || '').toLowerCase().includes('abort')) {
        message.info('已取消深度研究');
        return;
      }
      message.error(`搜索失败: ${error.message || '未知错误'}`);
    } finally {
      setResearchLoading(false);
      researchAbortRef.current = null;
    }
  };

  const handleResearchCancel = () => {
    closeResearchModal(true);
  };

  const handleAddToCourseKB = async (fileKey: string) => {
    if (!courseId || !token) {
      message.error('缺少必要参数');
      return;
    }

    const file = fileList.find(f => f.key === fileKey);
    if (!file || !file.filePath) {
      message.error('文件信息不完整');
      return;
    }

    try {
      const result = await addRAGDocumentToCourseKB(courseId, file.filePath, token, {
        scopeType: workspaceScope?.scopeType,
        scopeId: workspaceScope?.scopeId,
        libraryType: COURSE_LIBRARY_TYPE,
        promotedFromDocumentId: file.documentId,
      });
      registerCreatedJob(result.job);
      message.success('已转入课程知识库，正在后台建立索引');
      await reloadDocuments();
    } catch (error) {
      console.error('添加到课程知识库失败:', error);
      message.error(error instanceof Error ? error.message : '添加到课程知识库失败');
    }
  };

  const openPreview = async (fileKey: string, isHighlightTrigger = false, source?: any) => {
    const file = fileList.find(f => f.key === fileKey);
    if (!file || !file.filePath) {
      message.error('文件信息不完整');
      return;
    }

    try {
      setPreviewOpen(true);
      setPreviewFile(file);
      setPreviewContent(null);
      setPreviewMediaUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      setHighlightedContent(null);
      setHighlightRetrievalMethod(null);
      setUnmatchedHighlightText(null);
      setPreviewSummary(''); // 重置摘要
      onPreviewStateChange?.(true);

      if (file.type === 'image' && file.imageUrl) {
        setPreviewLoading(false);
        return;
      }

      setPreviewLoading(true);
      // 并行加载文档内容和摘要
      const isCourseKnowledgeDocument = Boolean(courseId && token && file.documentId && file.knowledgeStatus);
      const [content, summaryData] = await Promise.all([
        isCourseKnowledgeDocument
          ? getKnowledgeBaseDocumentContent(courseId!, file.documentId!, token!)
          : getDocumentContent(file.filePath),
        isCourseKnowledgeDocument ? Promise.resolve(null) : getDocumentSummary(file.filePath, false).catch(err => {
          console.warn('获取文档摘要失败:', err);
          return null; // 摘要加载失败不影响预览
        })
      ]);
      
      setPreviewContent(content);
      if (summaryData?.summary) {
        setPreviewSummary(summaryData.summary);
      }

      if (isHighlightTrigger && source) {
        handleHighlight(content, source);
      } else {
        setHighlightedContent(null);
        setHighlightRetrievalMethod(null);
        setUnmatchedHighlightText(null);
      }
    } catch (error) {
      console.error('获取文档内容失败:', error);
      message.error(error instanceof Error ? error.message : '获取文档内容失败');
      setPreviewOpen(false);
      setPreviewFile(null);
      setPreviewContent(null);
      setUnmatchedHighlightText(null);
      setPreviewSummary('');
      onPreviewStateChange?.(false);
    } finally {
      setPreviewLoading(false);
      setSummaryLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setPreviewFile(null);
    setPreviewContent(null);
    setPreviewMediaUrls((current) => {
      Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
      return {};
    });
    setHighlightedContent(null);
    setHighlightRetrievalMethod(null);
    setUnmatchedHighlightText(null);
    setPreviewSummary('');
    onPreviewStateChange?.(false);
  };

  const openRenameModal = (fileKey: string) => {
    const file = fileList.find(f => f.key === fileKey);
    if (!file) {
      message.error('文件信息不完整');
      return;
    }
    setRenameTarget(file);
    setRenameValue(file.title);
    setRenameModalVisible(true);
  };

  const handleRenameConfirm = async () => {
    if (!renameTarget) return;
    const newName = renameValue.trim();
    if (!newName) {
      message.error('新名称不能为空');
      return;
    }

    try {
      setRenameSubmitting(true);
      const updated = await renameDocument(renameTarget.filePath || renameTarget.key, newName);
      setFileList(prev => prev.map(item => (
        item.key === renameTarget.key
          ? { ...item, title: decodeDisplayText(updated.file_name) }
          : item
      )));
      message.success('重命名成功');
      setRenameModalVisible(false);
      setRenameTarget(null);
      setRenameValue('');

      if (previewFile?.key === renameTarget.key) {
        setPreviewFile({ ...previewFile, title: decodeDisplayText(updated.file_name) });
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
    if (!file) {
      message.error('文件信息不完整');
      return;
    }

    try {
      if (courseId && token && file.documentId) {
        await deleteKnowledgeBaseDocument(courseId, file.documentId, token);
      } else if (file.filePath) {
        await deleteDocument(file.filePath);
      } else {
        message.error('文件信息不完整');
        return;
      }
      message.success('删除成功');
      await reloadDocuments();

    if (checkedKeys.includes(fileKey)) {
      const newChecked = checkedKeys.filter(k => k !== fileKey);
      setCheckedKeys(newChecked);
      setSelectedDocs(newChecked as string[]);
      }

      if (previewFile?.key === fileKey) {
        closePreview();
      }
    } catch (error) {
      console.error('删除文档失败:', error);
      message.error(error instanceof Error ? error.message : '删除文档失败');
    }
  };

  const getAllFileIcons = (): React.ReactNode[] => {
    return fileList.map(node => (
      <div key={node.key} style={{ marginBottom: 8, display: 'flex', justifyContent: 'center' }}>
        {getFileIcon(
          node.type,
          node.title,
          20,
          node.sourceIconUrl ? listMediaUrls[node.sourceIconUrl] : undefined,
          node.sourceUrl,
        )}
      </div>
    ));
  };

  const toggleCourseNodeExpanded = (nodeId: string) => {
    setExpandedCourseNodeIds((current) => (
      current.includes(nodeId)
        ? current.filter((currentNodeId) => currentNodeId !== nodeId)
        : [...current, nodeId]
    ));
  };

  const getCourseFilesForNode = (node: KnowledgeGraphNode): FileItem[] => {
    const isCourseRootNode = node.id === courseKnowledgeGraphRoot?.id;
    return courseFileList.filter((file) => {
      if (file.libraryType !== COURSE_LIBRARY_TYPE) {
        return false;
      }
      if (isCourseRootNode && (file.scopeType === 'course' || !file.scopeType)) {
        return true;
      }
      return file.scopeType === 'knowledge_point' && file.scopeId === node.id;
    });
  };

  const collectCourseNodeIdsForNode = (node: KnowledgeGraphNode): string[] => {
    return collectKnowledgeSubtreeNodeIds(node);
  };

  const collectCourseFileKeysForNode = (node: KnowledgeGraphNode): React.Key[] => {
    const directFileKeys = getCourseFilesForNode(node).map((file) => file.key);
    const descendantFileKeys = (node.children || []).flatMap((childNode) => collectCourseFileKeysForNode(childNode));
    return Array.from(new Set([...directFileKeys, ...descendantFileKeys]));
  };

  const collectCourseDocumentCountForNode = (node: KnowledgeGraphNode): number => {
    const directCount = getCourseFilesForNode(node).length;
    const descendantCount = (node.children || []).reduce(
      (sum, childNode) => sum + collectCourseDocumentCountForNode(childNode),
      0,
    );
    return directCount + descendantCount;
  };

  const handleCourseNodeSelectAll = (node: KnowledgeGraphNode, checked: boolean) => {
    const subtreeNodeIds = collectCourseNodeIdsForNode(node);
    const subtreeFileKeys = collectCourseFileKeysForNode(node);
    const nextCheckedNodeIds = new Set(checkedCourseNodeIds);
    const nextCheckedKeys = new Set(checkedKeys);

    subtreeNodeIds.forEach((nodeId) => {
      if (checked) {
        nextCheckedNodeIds.add(nodeId);
      } else {
        nextCheckedNodeIds.delete(nodeId);
      }
    });

    subtreeFileKeys.forEach((fileKey) => {
      if (checked) {
        nextCheckedKeys.add(fileKey);
      } else {
        nextCheckedKeys.delete(fileKey);
      }
    });

    setCheckedCourseNodeIds(Array.from(nextCheckedNodeIds));
    applyCheckedFileKeys(Array.from(nextCheckedKeys));
  };

  const renderCourseLibraryTreeNode = (
    node: KnowledgeGraphNode,
    depth = 0,
  ): React.ReactNode => {
    const childNodes = node.children || [];
    const renderedChildren: React.ReactNode[] = [];

    childNodes.forEach((childNode) => {
      const renderedChildNode = renderCourseLibraryTreeNode(childNode, depth + 1);
      if (renderedChildNode) {
        renderedChildren.push(renderedChildNode);
      }
    });

    const nodeFiles = getCourseFilesForNode(node);
    const subtreeNodeIds = collectCourseNodeIdsForNode(node);
    const subtreeFileKeys = collectCourseFileKeysForNode(node);
    const subtreeDocumentCount = collectCourseDocumentCountForNode(node);
    const selectedSubtreeNodeCount = subtreeNodeIds.filter((nodeId) => checkedCourseNodeIds.includes(nodeId)).length;
    const selectedSubtreeFileCount = subtreeFileKeys.filter((fileKey) => checkedKeys.includes(fileKey)).length;
    const subtreeFullyChecked = subtreeFileKeys.length > 0
      ? selectedSubtreeFileCount === subtreeFileKeys.length
      : selectedSubtreeNodeCount > 0 && selectedSubtreeNodeCount === subtreeNodeIds.length;
    const subtreeIndeterminate = subtreeFileKeys.length > 0
      ? selectedSubtreeFileCount > 0 && selectedSubtreeFileCount < subtreeFileKeys.length
      : selectedSubtreeNodeCount > 0 && selectedSubtreeNodeCount < subtreeNodeIds.length;
    const isExpanded = expandedCourseNodeIds.includes(node.id);
    const showToggle = childNodes.length > 0;

    return (
      <div
        key={`course-library-node-${node.id}`}
        className="source-panel__tree-node"
        style={{ ['--source-tree-depth' as const]: depth } as React.CSSProperties}
      >
        <div className="source-panel__tree-node-header">
          {showToggle ? (
            <Button
              type="text"
              size="small"
              className="source-panel__tree-node-toggle"
              onClick={() => toggleCourseNodeExpanded(node.id)}
            >
              {isExpanded ? 'v' : '>'}
            </Button>
          ) : (
            <span className="source-panel__tree-node-spacer" />
          )}
          <span className="source-panel__tree-node-label" title={node.label}>{node.label}</span>
          <Text type="secondary" className="source-panel__tree-node-count">{subtreeDocumentCount}</Text>
          <Checkbox
            checked={subtreeFullyChecked}
            indeterminate={subtreeIndeterminate}
            onChange={(e) => {
              e.stopPropagation();
              handleCourseNodeSelectAll(node, e.target.checked);
            }}
            onClick={(e) => e.stopPropagation()}
          />
        </div>

        {nodeFiles.length > 0 ? (
          <div className="source-panel__tree-node-files">
            {nodeFiles.map(renderFileItem)}
          </div>
        ) : null}

        {showToggle && isExpanded ? (
          <div className="source-panel__tree-node-children">
            {renderedChildren}
          </div>
        ) : null}
      </div>
    );
  };

  const courseLibraryTreeRoot = courseKnowledgeGraphRoot
    ? (
      workspaceScope?.scopeType === 'knowledge_point' && workspaceScope.scopeId
        ? findKnowledgeGraphNode(courseKnowledgeGraphRoot, workspaceScope.scopeId) || courseKnowledgeGraphRoot
        : courseKnowledgeGraphRoot
    )
    : null;

  const handleKnowledgeAction = async (
    file: FileItem,
    action: 'retry' | 'reindex',
  ) => {
    if (!courseId || !token || !file.documentId) {
      message.error('缺少文档任务信息');
      return;
    }
    try {
      const job = action === 'retry'
        ? await retryKnowledgeBaseDocument(courseId, file.documentId, token)
        : await reindexKnowledgeBaseDocument(courseId, file.documentId, token);
      registerCreatedJob(job);
      message.success(action === 'retry' ? '已重新提交处理任务' : '已提交重建索引任务');
      await reloadDocuments();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '提交任务失败');
    }
  };

  const openRetrievalTest = (file: FileItem) => {
    setRetrievalTarget(file);
    setRetrievalQuery('');
    setRetrievalResult(null);
  };

  const runRetrievalTest = async () => {
    if (!courseId || !token || !retrievalTarget?.documentId || !retrievalQuery.trim()) {
      message.warning('请输入要检索的问题');
      return;
    }
    setRetrievalLoading(true);
    try {
      const result = await testKnowledgeBaseDocumentRetrieval(
        courseId,
        retrievalTarget.documentId,
        token,
        retrievalQuery.trim(),
      );
      setRetrievalResult(result);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '检索测试失败');
    } finally {
      setRetrievalLoading(false);
    }
  };

  const renderFileItem = (file: FileItem) => {
    const canRetrieve = file.knowledgeStatus === 'ready' || file.knowledgeStatus === 'partially_ready';
    const canReindex = Boolean(
      file.knowledgeStatus
      && ['received', 'ready', 'partially_ready'].includes(file.knowledgeStatus),
    );
    const isKnowledgeDocument = Boolean(file.documentId && file.knowledgeStatus);
    const menuItems: MenuProps['items'] = [
      { key: 'preview', label: '预览文档', icon: <EyeOutlined />, onClick: () => openPreview(file.key) },
      ...(!isKnowledgeDocument
        ? [{ key: 'rename', label: '重命名', icon: <EditOutlined />, onClick: () => openRenameModal(file.key) }]
        : []),
      ...(canRetrieve
        ? [{
          key: 'test-retrieval',
          label: '测试检索',
          icon: <SearchOutlined />,
          onClick: () => openRetrievalTest(file),
        }]
        : []),
      ...(file.knowledgeStatus === 'failed'
        ? [{
          key: 'retry-index',
          label: '重试处理',
          icon: <ReloadOutlined />,
          onClick: () => void handleKnowledgeAction(file, 'retry'),
        }]
        : []),
      ...(canReindex
        ? [{
          key: 'reindex',
          label: '重建索引',
          icon: <ReloadOutlined />,
          onClick: () => void handleKnowledgeAction(file, 'reindex'),
        }]
        : []),
      ...(file.libraryType === PERSONAL_LIBRARY_TYPE
        ? [{ key: 'add-to-course', label: '转入课程知识库', icon: <PlusOutlined />, onClick: () => handleAddToCourseKB(file.key) }]
        : []),
      { key: 'delete', label: '删除', icon: <DeleteOutlined />, danger: true, onClick: () => handleDeleteFile(file.key) },
    ];

    return (
      <div key={file.documentId || file.key} className="source-panel__item">
        <div
          className="source-panel__item-main"
          onClick={() => openPreview(file.key)}
          title="点击预览文档"
        >
          <span className="source-panel__item-icon">
            {getFileIcon(
              file.type,
              file.title,
              16,
              file.sourceIconUrl ? listMediaUrls[file.sourceIconUrl] : undefined,
              file.sourceUrl,
            )}
          </span>
          <span className="source-panel__item-copy">
            <span className="source-panel__item-title">{file.title}</span>
            {file.knowledgeStatus && file.knowledgeStatus !== 'received' ? (
              <span className="source-panel__item-meta">
                <Tag color={KNOWLEDGE_STATUS_META[file.knowledgeStatus].color}>
                  {KNOWLEDGE_STATUS_META[file.knowledgeStatus].label}
                </Tag>
                {canRetrieve ? (
                  <span>{file.chunkCount || 0} 个片段</span>
                ) : null}
              </span>
            ) : null}
          </span>
        </div>
        <div className="source-panel__item-actions">
          <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
            <Button
              type="text"
              icon={<MoreOutlined />}
              size="small"
              className="source-panel__item-more"
              onClick={(e) => e.stopPropagation()}
            />
          </Dropdown>
          <Checkbox checked={checkedKeys.includes(file.key)} onChange={(e) => {
            e.stopPropagation();
            onCheck(file.key, e.target.checked);
          }} className="source-panel__item-checkbox" />
        </div>
      </div>
    );
  };

  if (collapsed) {
    const fileIcons = getAllFileIcons();
    return (
      <div className="source-panel source-panel--collapsed">
        <div className="source-panel__collapsed-top">
          <Button
            type="text"
            icon={<RightOutlined />}
            onClick={onToggleCollapsed}
            aria-label="展开知识库"
            className="source-panel__collapse-trigger"
          />
        </div>
        <div className="source-panel__collapsed-list">
          {fileIcons.length > 0 ? fileIcons : (
            <Text type="secondary" className="source-panel__collapsed-empty">暂无文档</Text>
          )}
        </div>
      </div>
    );
  }

  if (previewOpen) {
    const previewImageChunks = previewContent?.chunks.filter((chunk) => isRenderableImageChunk(chunk)) ?? [];
    const previewTextContent = buildPreviewTextContent(previewContent);
    const inlineMarkdownImageUrls = extractMarkdownImageUrls(previewTextContent);
    const hasInlineMarkdownImages = inlineMarkdownImageUrls.length > 0;
    const directPreviewImageUrl = previewFile?.imageUrl ? previewMediaUrls[previewFile.imageUrl] : undefined;
    const previewMarkdownComponents = {
      img: ({ src, alt }: any) => {
        const rawSrc = typeof src === 'string' ? src : '';
        const resolvedSrc = rawSrc ? previewMediaUrls[rawSrc] || rawSrc : '';
        if (!resolvedSrc) {
          return <Text type="secondary">图片加载中...</Text>;
        }

        return (
          <img
            src={resolvedSrc}
            alt={alt || ''}
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
        );
      },
      a: ({ href, children }: any) => (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      ),
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 24, boxShadow: '0 12px 28px rgba(15,23,42,0.08)', minHeight: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <Space style={{ minWidth: 0 }}>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={closePreview} />
            {previewFile && getFileIcon(
              previewFile.type,
              previewFile.title,
              18,
              previewFile.sourceIconUrl ? listMediaUrls[previewFile.sourceIconUrl] : undefined,
              previewFile.sourceUrl,
            )}
            <Text strong ellipsis style={{ maxWidth: 320 }}>{previewFile?.title || '文档预览'}</Text>
          </Space>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 8 }}>
          <Spin spinning={previewLoading}>
            {previewFile?.type === 'image' && previewFile.imageUrl ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <Card size="small" title="图片预览">
                  {directPreviewImageUrl ? (
                    <img
                      src={directPreviewImageUrl}
                      alt={previewFile.title}
                      style={{
                        maxWidth: '100%',
                        maxHeight: '65vh',
                        objectFit: 'contain',
                        display: 'block',
                        margin: '0 auto',
                        borderRadius: 8,
                        background: '#f5f5f5',
                      }}
                    />
                  ) : (
                    <Text type="secondary">图片加载中...</Text>
                  )}
                </Card>
              </div>
            ) : previewContent ? (
              <div>
                {/* 文档摘要：显示在顶部 */}
                {previewSummary && (
                  <Card
                    title="文档概述"
                    size="small"
                    style={{ marginBottom: 16 }}
                    loading={summaryLoading}
                  >
                    <div style={{ fontSize: 14, lineHeight: 1.8 }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{normalizeKnowledgeMarkdown(previewSummary)}</ReactMarkdown>
                    </div>
                  </Card>
                )}

                {previewImageChunks.length > 0 && !hasInlineMarkdownImages && (
                  <Card
                    title={`文档图片 (${previewImageChunks.length})`}
                    size="small"
                    style={{ marginBottom: 16 }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      {previewImageChunks.map((chunk) => {
                        const imageUrl = chunk.metadata?.image_url as string | undefined;
                        const previewUrl = imageUrl ? previewMediaUrls[imageUrl] : undefined;
                        const imageTitle = decodeDisplayText(
                          chunk.metadata?.image_alt || chunk.metadata?.image_name || `文档图片 ${chunk.id + 1}`,
                        );
                        const pageLabel = chunk.page || chunk.metadata?.page;

                        if (!imageUrl) {
                          return null;
                        }

                        return (
                          <div
                            key={`preview-image-${chunk.id}`}
                            style={{
                              padding: 12,
                              border: '1px solid #f0f0f0',
                              borderRadius: 10,
                              background: '#fafafa',
                            }}
                          >
                            <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                              <Text strong>{imageTitle}</Text>
                              {pageLabel ? <Text type="secondary">第 {pageLabel} 页</Text> : null}
                            </div>
                            {previewUrl ? (
                              <img
                                src={previewUrl}
                                alt={imageTitle}
                                style={{
                                  maxWidth: '100%',
                                  maxHeight: '50vh',
                                  objectFit: 'contain',
                                  display: 'block',
                                  margin: '0 auto',
                                  borderRadius: 8,
                                  background: '#f5f5f5',
                                }}
                              />
                            ) : (
                              <Text type="secondary">图片加载中...</Text>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}
                
                <div style={{ marginBottom: 12, padding: '10px', background: '#f5f5f5', borderRadius: 8 }}>
                  <Space wrap>
                    <Text strong>总段落数:</Text>
                    <Text>{previewContent.total_chunks}</Text>
                  </Space>
                </div>
                {highlightedContent ? (
                  <>
                    <div style={{ marginBottom: 12, padding: '10px 12px', background: unmatchedHighlightText ? '#fff7e6' : '#eef4ff', border: `1px solid ${unmatchedHighlightText ? '#ffd591' : '#c9dcff'}`, borderRadius: 8, color: unmatchedHighlightText ? '#ad6800' : '#2458a6' }}>
                      {unmatchedHighlightText
                        ? '当前文档版本无法精确对齐该片段，已单独展示实际检索内容，未使用关键词伪高亮'
                        : highlightRetrievalMethod === 'hybrid_rerank'
                        ? '已定位：向量检索与 BM25 融合、重排后的完整命中片段'
                        : highlightRetrievalMethod === 'hybrid'
                          ? '已定位：向量检索与 BM25 融合后的完整命中片段'
                          : highlightRetrievalMethod === 'vector'
                            ? '已定位：向量检索返回的完整命中片段'
                            : '已定位：完整检索命中片段'}
                    </div>
                    {unmatchedHighlightText ? (
                      <pre style={{ margin: '0 0 16px', padding: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: '#fffdf5', border: '1px solid #ffe7ba', borderRadius: 8 }}>
                        {unmatchedHighlightText}
                      </pre>
                    ) : null}
                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.8', fontSize: '14px', color: '#333', fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, "source-code-pro", monospace' }}>
                      {highlightedContent}
                    </div>
                  </>
                ) : previewTextContent ? (
                  <div style={{ padding: '12px 0', wordBreak: 'break-word', lineHeight: '1.8', fontSize: '14px', color: '#333' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={previewMarkdownComponents}>
                      {previewTextContent}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div style={{ padding: '12px 0' }}>
                    <Text type="secondary">该文档当前没有可展示的正文文本，已在上方展示提取出的图片内容。</Text>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: 24, textAlign: 'center' }}>
                <Text type="secondary">加载中...</Text>
              </div>
            )}
          </Spin>
        </div>
      </div>
    );
  }

  return (
    <div className="source-panel">
      <div className="source-panel__header">
        <div className="source-panel__header-main">
          <Title level={5} className="source-panel__title">知识库</Title>
          <Text className="source-panel__header-meta">
            当前已接入 <span className="source-panel__header-count">{fileList.length}</span> 份资料
          </Text>
        </div>
        <Button
          type="text"
          icon={<LeftOutlined />}
          onClick={onToggleCollapsed}
          aria-label="折叠知识库"
          className="source-panel__collapse-trigger"
        />
      </div>

      <div className="source-panel__tools">
        <div className="source-panel__library-tabs" role="tablist" aria-label="知识库范围">
          <button type="button" role="tab" aria-selected={libraryTab === COURSE_LIBRARY_TYPE} onClick={() => setLibraryTab(COURSE_LIBRARY_TYPE)}>
            课程知识库 <span>{courseFileList.length}</span>
          </button>
          <button type="button" role="tab" aria-selected={libraryTab === PERSONAL_LIBRARY_TYPE} onClick={() => setLibraryTab(PERSONAL_LIBRARY_TYPE)}>
            个人知识库 <span>{personalFileList.length}</span>
          </button>
        </div>
        <div className="source-panel__search-shell">
          <Input
            value={searchDraftValue}
            onChange={(e) => setSearchDraftValue(e.target.value)}
            onPressEnter={() => {
              setResearchModalVisible(true);
              void handleResearchConfirm();
            }}
            placeholder="输入关键词后开始深度研究"
            size="large"
            prefix={<SearchOutlined />}
            className="source-panel__search-input"
          />
          <Button
            type="text"
            icon={<RightOutlined />}
            size="large"
            className="source-panel__search-submit"
            aria-label="开始深度研究"
            onClick={() => {
              setResearchModalVisible(true);
              void handleResearchConfirm();
            }}
          />
        </div>
      </div>

      <div className="source-panel__list-section">
        <div className="source-panel__list-toolbar">
          <div className="source-panel__section-heading">
            <span className="source-panel__section-label">资料列表</span>
            <Text className="source-panel__section-meta">已加载 {fileList.length} 项</Text>
          </div>
          <div className="source-panel__select-all">
            <span className="source-panel__select-all-text">选择所有来源</span>
            <Checkbox checked={selectAllChecked} onChange={(e) => handleSelectAll(e.target.checked)} />
          </div>
        </div>

        <div className="source-panel__list">
          <Spin spinning={loading}>
            <div className="source-panel__items">
              <div className="source-panel__empty"><Text type="secondary">暂无文档</Text></div>
                {false && fileList.map((file) => {
                  const menuItems: MenuProps['items'] = [
                    { key: 'preview', label: '预览文档', icon: <EyeOutlined />, onClick: () => openPreview(file.key) },
                    { key: 'rename', label: '重命名', icon: <EditOutlined />, onClick: () => openRenameModal(file.key) },
                    { key: 'add-to-course', label: '增加到课程知识库', icon: <PlusOutlined />, onClick: () => handleAddToCourseKB(file.key) },
                    { key: 'delete', label: '删除', icon: <DeleteOutlined />, danger: true, onClick: () => handleDeleteFile(file.key) },
                  ];

                  return (
                    <div key={file.key} className="source-panel__item">
                      <div
                        className="source-panel__item-main"
                        onClick={() => openPreview(file.key)}
                        title="点击预览文档"
                      >
                        <span className="source-panel__item-icon">
                          {getFileIcon(
                            file.type,
                            file.title,
                            16,
                            file.sourceIconUrl ? listMediaUrls[file.sourceIconUrl] : undefined,
                            file.sourceUrl,
                          )}
                        </span>
                        <span className="source-panel__item-title">{file.title}</span>
                      </div>
                      <div className="source-panel__item-actions">
                        <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
                          <Button
                            type="text"
                            icon={<MoreOutlined />}
                            size="small"
                            className="source-panel__item-more"
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Dropdown>
                        <Checkbox checked={checkedKeys.includes(file.key)} onChange={(e) => {
                          e.stopPropagation();
                          onCheck(file.key, e.target.checked);
                        }} className="source-panel__item-checkbox" />
                      </div>
                    </div>
                  );
                })}
                {libraryTab === COURSE_LIBRARY_TYPE ? <div className="source-panel__library-group">
                  <div className="source-panel__library-heading">
                    <span>课程知识库</span>
                    <Text type="secondary">{courseFileList.length} 项</Text>
                  </div>
                  {courseLibraryTreeRoot ? (
                    renderCourseLibraryTreeNode(courseLibraryTreeRoot)
                  ) : courseFileList.length > 0 ? (
                    courseFileList.map(renderFileItem)
                  ) : (
                    <div className="source-panel__empty"><Text type="secondary">暂无课程资料</Text></div>
                  )}
                </div> : null}
                {libraryTab === PERSONAL_LIBRARY_TYPE ? <div className="source-panel__library-group">
                  <div className="source-panel__library-heading">
                    <span>个人知识库</span>
                    <Text type="secondary">{personalFileList.length} 项</Text>
                  </div>
                  {personalFileList.length > 0 ? (
                    personalFileList.map(renderFileItem)
                  ) : (
                    <div className="source-panel__empty"><Text type="secondary">暂无个人资料</Text></div>
                  )}
                </div> : null}
              </div>
          </Spin>
        </div>
      </div>

      <div className="source-panel__footer">
        <Space direction="vertical" className="source-panel__footer-actions" size="small">
          <input
            type="file"
            multiple
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.bmp,.gif,.mp4,.mov,.mkv,.avi,.webm"
            style={{ display: 'none' }}
          />
          <Button icon={<UploadOutlined />} type="default" onClick={handleAddSourceClick} size="large" block loading={videoUploading}>
            上传文档/图片/视频
          </Button>
        </Space>
      </div>

      <Modal 
        title="深度研究" 
        open={researchModalVisible} 
        onOk={handleResearchConfirm} 
        onCancel={handleResearchCancel}
        okText={researchResults.length > 0 && !researchLoading ? '完成' : '开始研究'}
        cancelText="取消"
        confirmLoading={researchLoading}
        width={800}
      >
        <div>
          <Text strong>研究主题：</Text>
        </div>
        <Input
          style={{ marginTop: 12 }}
          placeholder="请输入关键词或研究主题"
          size="large"
          value={searchDraftValue}
          onChange={(e) => setSearchDraftValue(e.target.value)}
          onPressEnter={() => void handleResearchConfirm()}
        />
        {searchValue ? (
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">当前搜索：</Text>
            <Text>{searchValue}</Text>
          </div>
        ) : null}
        
        <Spin spinning={researchLoading} tip="正在搜索和爬取，请耐心等待...">
          {researchLoading && (
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">正在研究...（这可能需要几分钟时间）</Text>
            </div>
          )}
          
          {!researchLoading && researchResults.length > 0 && (
            <div style={{ marginTop: 16, maxHeight: 400, overflowY: 'auto' }}>
              <Text strong>搜索结果（{researchResults.length}条）：</Text>
              {researchResults.map((result, index) => (
                <Card key={index} size="small" style={{ marginTop: 8 }}>
                  <div>
                    <Text strong>{result.title || result.url}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>{result.url}</Text>
                    <br />
                    {result.status === 'success' && result.content && (
                      <Text style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
                        {result.content.substring(0, 200)}...
                      </Text>
                    )}
                    {result.status === 'failed' && (
                      <Text type="danger" style={{ fontSize: 12 }}>失败: {result.error_message}</Text>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
          
          {!researchLoading && researchResults.length === 0 && (
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">点击"开始研究"按钮开始搜索</Text>
            </div>
          )}
        </Spin>
      </Modal>

      <Modal
        title={`测试检索${retrievalTarget ? ` · ${retrievalTarget.title}` : ''}`}
        open={Boolean(retrievalTarget)}
        onCancel={() => {
          setRetrievalTarget(null);
          setRetrievalResult(null);
          setRetrievalQuery('');
        }}
        onOk={() => void runRetrievalTest()}
        okText="开始检索"
        cancelText="关闭"
        confirmLoading={retrievalLoading}
        width={720}
      >
        <Text type="secondary">
          只在当前文档的活动索引版本中检索，不调用大模型生成答案。
        </Text>
        <Input.Search
          value={retrievalQuery}
          onChange={(event) => setRetrievalQuery(event.target.value)}
          onSearch={() => void runRetrievalTest()}
          placeholder="输入一个可以由该文档回答的问题"
          enterButton="检索"
          loading={retrievalLoading}
          style={{ marginTop: 12 }}
        />
        {retrievalTarget ? (
          <div className="source-panel__retrieval-summary">
            <span>索引版本：{retrievalTarget.activeIndexVersion || '—'}</span>
            <span>片段：{retrievalTarget.chunkCount || 0}</span>
            <span>页数：{retrievalTarget.pageCount || 0}</span>
          </div>
        ) : null}
        {retrievalResult ? (
          <div className="source-panel__retrieval-results">
            <Text strong>
              命中 {retrievalResult.hits.length} 条 · {retrievalResult.elapsed_ms}ms
            </Text>
            {retrievalResult.hits.length > 0 ? retrievalResult.hits.map((hit, index) => (
              <Card
                key={hit.chunk_id || `${index}`}
                size="small"
                title={`#${index + 1} · 匹配度 ${Math.round(hit.score * 100)}%${hit.page ? ` · 第 ${hit.page} 页` : ''}`}
              >
                <Text>{hit.content}</Text>
              </Card>
            )) : (
              <div className="source-panel__retrieval-empty">没有找到匹配片段，请换一个关键词测试。</div>
            )}
          </div>
        ) : null}
      </Modal>

      <Modal title="重命名文档" open={renameModalVisible} confirmLoading={renameSubmitting} onOk={handleRenameConfirm} okText="确定" cancelText="取消" onCancel={() => { setRenameModalVisible(false); setRenameTarget(null); setRenameValue(''); }}>
        <Input value={renameValue} placeholder="请输入新的文档名称" onChange={(e) => setRenameValue(e.target.value)} onPressEnter={handleRenameConfirm} maxLength={200} />
        <div style={{ marginTop: 8 }}><Text type="secondary" style={{ fontSize: 12 }}>仅修改显示名称，不会移动或重新上传文件。</Text></div>
      </Modal>
    </div>
  );
};

export default SourcePanel;
