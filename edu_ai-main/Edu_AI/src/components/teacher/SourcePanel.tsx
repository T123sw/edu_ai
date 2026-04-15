import React, { useRef, useState, useEffect } from 'react';
import { Button, Input, Space, Typography, Modal, Divider, Checkbox, Dropdown, MenuProps, Spin, message, Card } from 'antd';
import ReactMarkdown from 'react-markdown';
import {
  FilePdfOutlined,
  FileWordOutlined,
  FileTextOutlined,
  FileMarkdownOutlined,
  GlobalOutlined,
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
} from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { useAuth } from '../../context/AuthContext';
import { listDocuments, importDocument, deleteDocument, renameDocument, getDocumentContent, getDocumentSummary, type DocumentContent, type RAGSource } from '../../services/rag';
import { addRAGDocumentToCourseKB } from '../../services/knowledgeBase';
import { deepSearchAndCrawl, getCrawlResults, type CrawlResult } from '../../services/deepsearch';
import { uploadVideo, getVideoJobStatus } from '../../services/video';

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

const SourcePanel: React.FC<Props> = ({ collapsed, onToggleCollapsed, courseId, onPreviewStateChange }) => {
  const { selectedDocs, setSelectedDocs, highlightRequest, setHighlightRequest } = useStore();
  const [videoUploading, setVideoUploading] = useState(false);
  const { token } = useAuth();
  const [fileList, setFileList] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>(selectedDocs);
  const [searchValue, setSearchValue] = useState('');
  const [searchDraftValue, setSearchDraftValue] = useState('');
  const [researchModalVisible, setResearchModalVisible] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchResults, setResearchResults] = useState<CrawlResult[]>([]);
  const [selectAllChecked, setSelectAllChecked] = useState(false);

  // 预览（覆盖列表）
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [previewContent, setPreviewContent] = useState<DocumentContent | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [highlightedContent, setHighlightedContent] = useState<React.ReactNode>(null);
  const highlightRef = useRef<HTMLElement | null>(null);
  // 文档摘要
  const [previewSummary, setPreviewSummary] = useState<string>('');
  const [summaryLoading, setSummaryLoading] = useState(false);

  // 重命名
  const [renameModalVisible, setRenameModalVisible] = useState(false);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameSubmitting, setRenameSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const researchAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const loadDocuments = async () => {
      try {
        setLoading(true);
        const documents = await listDocuments();
        const formattedFiles: FileItem[] = documents.map(doc => {
          // 如果是网页来源，优先使用 source_title 或 source_domain 作为显示标题
          let displayTitle = doc.file_name;
          if (doc.source_url) {
            if (doc.source_title) {
              displayTitle = doc.source_title;
            } else if (doc.source_domain) {
              displayTitle = `${doc.source_domain} - 网页内容`;
            } else {
              // 从 URL 提取域名
              try {
                const url = new URL(doc.source_url);
                displayTitle = `${url.hostname} - 网页内容`;
              } catch {
                displayTitle = doc.file_name;
              }
            }
          }
          return {
            key: doc.file_path,
            title: displayTitle,
            type: 'file' as const,
            filePath: doc.file_path,
          };
        });
        setFileList(formattedFiles);
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
      
      // 1. 直接匹配（完全一致）
      if (filePath === requestPath) {
        console.log('SourcePanel: 直接匹配成功:', filePath);
        return true;
      }
      
      // 2. 文件名匹配（requestPath 是文件名，filePath 是 source_key）
      if (fileName && requestPath.includes(fileName)) {
        console.log('SourcePanel: 文件名匹配成功:', fileName);
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
      return;
    }

    // 获取完整的文本块内容（这是要高亮的完整内容）
    const highlightText = String((source as any)?.content || '').trim();
    const fullText = fullContent.content;

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

    // 策略1：尝试精确匹配整个文本块
    let index = fullText.indexOf(highlightText);
    let matchLength = highlightText.length;

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

    // 策略3：如果还是找不到，尝试通过关键词定位，然后高亮整个文本块
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

  const onCheck = (key: React.Key, checked: boolean) => {
    const newChecked = checked ? [...checkedKeys, key] : checkedKeys.filter(k => k !== key);
    setCheckedKeys(newChecked);
    setSelectedDocs(newChecked as string[]);
    setSelectAllChecked(fileList.length > 0 && fileList.every(file => newChecked.includes(file.key)));
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allFileKeys = fileList.map(file => file.key);
      setCheckedKeys(allFileKeys);
      setSelectedDocs(allFileKeys as string[]);
    } else {
      setCheckedKeys([]);
      setSelectedDocs([]);
    }
    setSelectAllChecked(checked);
  };

  const reloadDocuments = async () => {
    setLoading(true);
    try {
      const documents = await listDocuments();
      const formattedFiles: FileItem[] = documents.map(doc => {
        // 如果是网页来源，优先使用 source_title 或 source_domain 作为显示标题
        let displayTitle = doc.file_name;
        if (doc.source_url) {
          if (doc.source_title) {
            displayTitle = doc.source_title;
          } else if (doc.source_domain) {
            displayTitle = `${doc.source_domain} - 网页内容`;
          } else {
            // 从 URL 提取域名
            try {
              const url = new URL(doc.source_url);
              displayTitle = `${url.hostname} - 网页内容`;
            } catch {
              displayTitle = doc.file_name;
            }
          }
        }
        return {
          key: doc.file_path,
          title: displayTitle,
          type: 'file' as const,
          filePath: doc.file_path,
        };
      });
      setFileList(formattedFiles);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSourceClick = () => {
    fileInputRef.current?.click();
  };

  const pollVideoJobUntilDone = async (jobId: string) => {
    const maxAttempts = 300;
    for (let i = 0; i < maxAttempts; i++) {
      const status = await getVideoJobStatus(jobId);
      if (status.status === 'completed') {
        return status;
      }
      if (status.status === 'failed') {
        throw new Error(status.message || '视频入库失败');
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error('视频入库超时，请稍后在任务页查看状态');
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

        if (videoExts.includes(ext)) {
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
          message.loading({
            content: `${file.name} 已上传，正在后台切片与向量化...`,
            key: `upload-${i}`,
            duration: 0,
          });
          await pollVideoJobUntilDone(uploadRes.job_id);
          message.success({ content: `${file.name} 视频入库完成`, key: `upload-${i}` });
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

  const handleResearch = () => {
    setSearchDraftValue(searchValue);
    setResearchModalVisible(true);
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
        max_urls: 5,
        crawl_timeout: 30,
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
      await addRAGDocumentToCourseKB(courseId, file.filePath, token);
      message.success('已添加到课程知识库');
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
      setHighlightedContent(null);
      setPreviewSummary(''); // 重置摘要
      onPreviewStateChange?.(true);

      setPreviewLoading(true);
      // 并行加载文档内容和摘要
      const [content, summaryData] = await Promise.all([
        getDocumentContent(file.filePath),
        getDocumentSummary(file.filePath, false).catch(err => {
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
        setHighlightedContent(content.content);
      }
    } catch (error) {
      console.error('获取文档内容失败:', error);
      message.error(error instanceof Error ? error.message : '获取文档内容失败');
      setPreviewOpen(false);
      setPreviewFile(null);
      setPreviewContent(null);
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
    setHighlightedContent(null);
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
      setFileList(prev => prev.map(item => (item.key === renameTarget.key ? { ...item, title: updated.file_name } : item)));
      message.success('重命名成功');
      setRenameModalVisible(false);
      setRenameTarget(null);
      setRenameValue('');

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
    if (!file || !file.filePath) {
      message.error('文件信息不完整');
      return;
    }

    try {
      await deleteDocument(file.filePath);
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
        {getFileIcon(node.type, node.title, 20)}
      </div>
    ));
  };

  if (collapsed) {
    const fileIcons = getAllFileIcons();
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          background: '#ffffff',
          borderRadius: 12,
          padding: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
          <Button type="text" icon={<RightOutlined />} onClick={onToggleCollapsed} aria-label="展开知识库" style={{ padding: '4px 8px' }} />
        </div>
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {fileIcons.length > 0 ? fileIcons : (
            <Text type="secondary" style={{ fontSize: 12, textAlign: 'center' }}>暂无文档</Text>
          )}
        </div>
      </div>
    );
  }

  if (previewOpen) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 24, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', minHeight: 0, overflow: 'hidden' }}>
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
                {/* 文档摘要：显示在顶部 */}
                {previewSummary && (
                  <Card
                    title="文档概述"
                    size="small"
                    style={{ marginBottom: 16 }}
                    loading={summaryLoading}
                  >
                    <div style={{ fontSize: 14, lineHeight: 1.8 }}>
                      <ReactMarkdown>{previewSummary}</ReactMarkdown>
                    </div>
                  </Card>
                )}
                
                <div style={{ marginBottom: 12, padding: '10px', background: '#f5f5f5', borderRadius: 8 }}>
                  <Space wrap>
                    <Text strong>总段落数:</Text>
                    <Text>{previewContent.total_chunks}</Text>
                  </Space>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.8', fontSize: '14px', color: '#333', fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, "source-code-pro", monospace' }}>
                  {highlightedContent}
                </div>
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff', borderRadius: 12, padding: 24, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', minHeight: 0, overflow: 'hidden', position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexShrink: 0, position: 'relative' }}>
        <Title level={5} style={{ margin: 0, fontWeight: 600 }}>知识库</Title>
        <Button type="text" icon={<LeftOutlined />} onClick={onToggleCollapsed} aria-label="折叠知识库" style={{ position: 'absolute', right: 0, top: 0, padding: '4px 8px' }} />
      </div>

      <Button
        type="default"
        icon={<SearchOutlined />}
        size="large"
        onClick={handleResearch}
        style={{ width: '100%', marginBottom: 16, flexShrink: 0 }}
      >
        深度研究搜索
      </Button>

      <div style={{ marginBottom: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 0 }}>
        <span style={{ fontSize: 14 }}>选择所有来源</span>
        <Checkbox checked={selectAllChecked} onChange={(e) => handleSelectAll(e.target.checked)} />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        <Spin spinning={loading}>
          {fileList.length === 0 && !loading ? (
            <div style={{ textAlign: 'center', padding: 48 }}><Text type="secondary">暂无文档</Text></div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {fileList.map((file) => {
              const menuItems: MenuProps['items'] = [
                  { key: 'preview', label: '预览文档', icon: <EyeOutlined />, onClick: () => openPreview(file.key) },
                  { key: 'rename', label: '重命名', icon: <EditOutlined />, onClick: () => openRenameModal(file.key) },
                  { key: 'add-to-course', label: '增加到课程知识库', icon: <PlusOutlined />, onClick: () => handleAddToCourseKB(file.key) },
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
                        <Button type="text" icon={<MoreOutlined />} size="small" style={{ padding: '4px 8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={(e) => e.stopPropagation()} />
                    </Dropdown>
                      <Checkbox checked={checkedKeys.includes(file.key)} onChange={(e) => { e.stopPropagation(); onCheck(file.key, e.target.checked); }} style={{ marginRight: 0, flexShrink: 0 }} />
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
        <input 
          type="file" 
          multiple 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept=".pdf,.doc,.docx,.txt,.md,.markdown,.mp4,.mov,.mkv,.avi,.webm"
          style={{ display: 'none' }} 
        />
        <Button icon={<UploadOutlined />} type="default" onClick={handleAddSourceClick} size="large" block loading={videoUploading}>上传文档/视频</Button>
      </Space>

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

      <Modal title="重命名文档" open={renameModalVisible} confirmLoading={renameSubmitting} onOk={handleRenameConfirm} okText="确定" cancelText="取消" onCancel={() => { setRenameModalVisible(false); setRenameTarget(null); setRenameValue(''); }}>
        <Input value={renameValue} placeholder="请输入新的文档名称" onChange={(e) => setRenameValue(e.target.value)} onPressEnter={handleRenameConfirm} maxLength={200} />
        <div style={{ marginTop: 8 }}><Text type="secondary" style={{ fontSize: 12 }}>仅修改显示名称，不会移动或重新上传文件。</Text></div>
      </Modal>
    </div>
  );
};

export default SourcePanel;
