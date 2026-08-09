import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Input, Button, List, Space, Typography, Tooltip, message, Empty, Spin, Modal, Popover } from 'antd';
import { SendOutlined, HistoryOutlined, DeleteOutlined, AudioOutlined, PictureOutlined, VideoCameraOutlined, PlusOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';
import { listChatConversations, getChatConversationDetail, deleteChatConversation, type ConversationListItem } from '../../services/teacher/api';
import {
  buildChatReplyPayload,
  resolveChatRetrievalDocIds,
  sendChatReplyV2Stream,
  pollChatTask,
  transcribeSpeechV2,
  uploadChatImagesV2,
  uploadChatVideosV2,
  type ChatResponseV2,
  type ChatTaskStatusV2,
  type ChatInputImageV2,
  type ChatInputVideoV2,
  type ChatSourceV2,
} from '../../services/teacher/chatV2';
import {
  AgentActivityPanel,
  emptyAgentActivity,
  type AgentActivityState,
  type MergedTimeline,
  type MergedTimelineStep,
} from './AgentActivityPanel';
import { decodeDisplayText } from '../../services/teacher/displayText.helpers';
import { resolveSpeechInputError } from '../../services/teacher/speechInput';
import { extractGeneratedFilesFromV2Response, restoreGeneratedFilesFromConversationDetail } from '../../services/teacher/chatV2.helpers';
import {
  getWorkspaceKnowledgeBaseLabel,
  getWorkspaceScopeApiParams,
  normalizeWorkspaceScope,
  type WorkspaceScope,
} from '../../services/teacher/workspaceScope';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { loadPreviewMediaUrl, revokePreviewMediaUrl, type RAGSource } from '../../services/rag';
import { requestJobRefresh, useJobStore } from '../../jobs/jobStore';
import { isTerminalJob } from '../../jobs/types';
import { buildGenerationSavedMessage, resolveGenerationReply } from './generationSavedMessage';
import './ChatPanel.css';

const { TextArea } = Input;
const { Title, Text } = Typography;

function buildSpeechFileName(mimeType: string): string {
  if (mimeType.includes('mp4')) return 'voice.mp4';
  if (mimeType.includes('mpeg')) return 'voice.mp3';
  if (mimeType.includes('ogg')) return 'voice.ogg';
  if (mimeType.includes('wav')) return 'voice.wav';
  return 'voice.webm';
}

function appendTranscript(previous: string, transcript: string): string {
  const normalizedTranscript = String(transcript || '').trim();
  if (!normalizedTranscript) {
    return previous;
  }
  if (!previous.trim()) {
    return normalizedTranscript;
  }
  return `${previous.trimEnd()} ${normalizedTranscript}`;
}

function getDisplayLabel(value: unknown, fallback: string): string {
  return decodeDisplayText(value) || fallback;
}

interface Message {
  user: 'You' | 'AI';
  text: string;
  sources?: ChatSourceV2[];
  inputImages?: ChatInputImageV2[];
  inputVideos?: ChatInputVideoV2[];
  statusText?: string;
  /** ReAct agent activity captured during streaming. Optional — present only on AI msgs that went through agent path. */
  agentActivity?: AgentActivityState;
}

interface ChatPanelProps {
  courseId?: string;
  workspaceScope?: WorkspaceScope;
  onWorkspaceScopeChange?: (scope: WorkspaceScope) => void;
}

/**
 * Merge agent plans across consecutive AI messages with the same subject into
 * a single timeline, so the user sees task continuity instead of fragmented
 * single-step plans on turn N+1.
 *
 * Walks back from `currentIndex` while subject matches; all earlier-turn steps
 * are forced to status='done' (we know they finished since this turn started).
 */
const buildMergedTimeline = (messages: Message[], currentIndex: number): MergedTimeline | undefined => {
  const current = messages[currentIndex];
  if (current?.user !== 'AI') return undefined;
  const activity = current.agentActivity as AgentActivityState | undefined;
  const subject = activity?.plan?.subject;
  if (!subject) return undefined;

  const related: AgentActivityState[] = [];
  for (let i = currentIndex; i >= 0; i--) {
    const msg = messages[i];
    if (msg.user !== 'AI') continue;
    const a = msg.agentActivity as AgentActivityState | undefined;
    if (!a?.plan) continue;
    if (a.plan.subject !== subject) break; // different task — stop
    related.unshift(a);
  }
  if (related.length <= 1) return undefined; // single plan — no need to merge

  const seen = new Set<string>();
  const steps: MergedTimelineStep[] = [];
  for (let i = 0; i < related.length; i++) {
    const a = related[i];
    const isLatest = i === related.length - 1;
    for (const step of a.plan!.steps) {
      const key = `${step.user_title}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const status: MergedTimelineStep['status'] = isLatest
        ? ((a.stepStatus[step.index] || step.status || 'pending') as MergedTimelineStep['status'])
        : 'done';
      steps.push({
        index: step.index,
        user_title: step.user_title,
        status,
        fromPriorTurn: !isLatest,
      });
    }
  }
  return {
    subject,
    resource_type: current.agentActivity?.plan?.resource_type || '',
    steps,
  };
};

interface PendingChatImage extends ChatInputImageV2 {
  previewUrl: string;
}

interface PendingChatVideo extends ChatInputVideoV2 {
  previewUrl: string;
}

const normalizeArtifactReferenceType = (
  value: unknown,
): 'report' | 'report_outline' | 'ppt_outline' | 'ppt_content_markdown' | 'ppt_deck' => {
  const artifactType = String(value || '').trim();
  if (
    artifactType === 'report_outline'
    || artifactType === 'ppt_outline'
    || artifactType === 'ppt_content_markdown'
    || artifactType === 'ppt_deck'
  ) {
    return artifactType;
  }
  return 'report';
};

type InlineSourceBlock = {
  markdown: string;
  normalizedText: string;
  sources: InlineSourceEntry[];
};

type InlineSourcePlan = {
  blocks: InlineSourceBlock[];
  unmatchedSources: InlineSourceEntry[];
};

type InlineSourceEntry = {
  source: ChatSourceV2;
  order: number;
};

const FENCE_PATTERN = /^(```|~~~)/;
const HISTORY_PAGE_SIZE = 20;

function normalizeSourceComparableText(value: unknown): string {
  return String(value || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]*`/g, ' ')
    .replace(/!\[[^\]]*]\(([^)]+)\)/g, ' ')
    .replace(/\[[^\]]*]\(([^)]+)\)/g, ' ')
    .replace(/[*_>#-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}

function buildCharacterBigrams(value: string): string[] {
  const compact = value.replace(/\s+/g, '');
  if (compact.length <= 2) {
    return compact ? [compact] : [];
  }

  const result: string[] = [];
  for (let index = 0; index < compact.length - 1; index += 1) {
    result.push(compact.slice(index, index + 2));
  }
  return result;
}

function scoreSourceBlockMatch(blockText: string, sourceText: string): number {
  const normalizedBlock = normalizeSourceComparableText(blockText);
  const normalizedSource = normalizeSourceComparableText(sourceText);

  if (!normalizedBlock || !normalizedSource) {
    return 0;
  }

  const sourceProbe = normalizedSource.slice(0, Math.min(normalizedSource.length, 36));
  if (sourceProbe && normalizedBlock.includes(sourceProbe)) {
    return 1;
  }

  const sourceBigrams = Array.from(new Set(buildCharacterBigrams(normalizedSource.slice(0, 240))));
  if (sourceBigrams.length === 0) {
    return 0;
  }

  const blockBigramSet = new Set(buildCharacterBigrams(normalizedBlock));
  let overlapCount = 0;
  for (const token of sourceBigrams) {
    if (blockBigramSet.has(token)) {
      overlapCount += 1;
    }
  }

  return overlapCount / sourceBigrams.length;
}

function splitMarkdownIntoSourceBlocks(markdown: string): InlineSourceBlock[] {
  const normalized = String(markdown || '').replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const blocks: InlineSourceBlock[] = [];
  let inFence = false;
  let currentLines: string[] = [];

  const flushCurrentLines = () => {
    const markdownBlock = currentLines.join('\n').trim();
    currentLines = [];
    if (!markdownBlock) {
      return;
    }
    blocks.push({
      markdown: markdownBlock,
      normalizedText: normalizeSourceComparableText(markdownBlock),
      sources: [],
    });
  };

  for (const line of lines) {
    const trimmedLine = line.trim();
    if (FENCE_PATTERN.test(trimmedLine)) {
      if (inFence) {
        currentLines.push(line);
        flushCurrentLines();
        inFence = false;
      } else {
        flushCurrentLines();
        inFence = true;
        currentLines.push(line);
      }
      continue;
    }

    if (inFence) {
      currentLines.push(line);
      continue;
    }

    if (!trimmedLine) {
      flushCurrentLines();
      continue;
    }

    currentLines.push(line);
  }

  flushCurrentLines();
  return blocks;
}

function buildInlineSourcePlan(markdown: string, sources: ChatSourceV2[]): InlineSourcePlan {
  const blocks = splitMarkdownIntoSourceBlocks(markdown);
  if (blocks.length === 0 || sources.length === 0) {
    return {
      blocks,
      unmatchedSources: sources.map((source, index) => ({ source, order: index + 1 })),
    };
  }

  const unmatchedSources: InlineSourceEntry[] = [];

  sources.forEach((source, sourceIndex) => {
    const sourceContent = String(source?.content || '').trim();
    const entry: InlineSourceEntry = {
      source,
      order: sourceIndex + 1,
    };
    if (!sourceContent) {
      unmatchedSources.push(entry);
      return;
    }

    let bestBlockIndex = -1;
    let bestScore = 0;

    blocks.forEach((block, index) => {
      if (!block.normalizedText || FENCE_PATTERN.test(block.markdown.trim())) {
        return;
      }
      const score = scoreSourceBlockMatch(block.markdown, sourceContent);
      if (score > bestScore) {
        bestScore = score;
        bestBlockIndex = index;
      }
    });

    if (bestBlockIndex >= 0 && bestScore >= 0.16) {
      blocks[bestBlockIndex].sources.push(entry);
    } else {
      unmatchedSources.push(entry);
    }
  });

  return {
    blocks,
    unmatchedSources,
  };
}

const ChatPanel: React.FC<ChatPanelProps> = ({ courseId, workspaceScope, onWorkspaceScopeChange }) => {
  const {
    messages,
    addMessage,
    setMessages,
    updateLastMessage,
    updateMessageById,
    selectedDocs,
    scopedSourceDocIds,
    allowRag,
    allowWeb,
    setAllowRag,
    setAllowWeb,
    setHighlightRequest,
    currentConversationId,
    setCurrentConversationId,
    queuedMessage,
    setQueuedMessage,
    artifactReference,
    conversationReference,
    setArtifactReference,
    clearArtifactReference,
    setConversationReference,
    clearConversationReference,
    addGeneratedFile,
    replaceConversationGeneratedFiles,
    clearConversationGeneratedFiles,
    removeGeneratedFilesByConversationId,
    setViewingFile,
    setStatusCard,
  } = useStore();
  const { addMaterial } = useCourseMaterialsStore();
  const jobsById = useJobStore((state) => state.jobs);

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [historyList, setHistoryList] = useState<ConversationListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<string | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPopoverOpen, setHistoryPopoverOpen] = useState(false);
  const [workflowType, setWorkflowType] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [backgroundTaskId, setBackgroundTaskId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [pendingImages, setPendingImages] = useState<PendingChatImage[]>([]);
  const [pendingVideos, setPendingVideos] = useState<PendingChatVideo[]>([]);
  const [messageImageUrls, setMessageImageUrls] = useState<Record<string, string>>({});
  const [messageVideoUrls, setMessageVideoUrls] = useState<Record<string, string>>({});
  const [sourceImageUrls, setSourceImageUrls] = useState<Record<string, string>>({});
  const [sourceVideoUrls, setSourceVideoUrls] = useState<Record<string, string>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const videoInputRef = useRef<HTMLInputElement | null>(null);
  const normalizedWorkspaceScope = useMemo(() => normalizeWorkspaceScope(workspaceScope), [workspaceScope]);
  const workspaceScopeApiParams = useMemo(
    () => getWorkspaceScopeApiParams(normalizedWorkspaceScope),
    [normalizedWorkspaceScope],
  );

  useEffect(() => {
    if (workspaceScopeApiParams.scopeType === 'knowledge_point') {
      setAllowRag(true);
    }
  }, [setAllowRag, workspaceScopeApiParams.scopeType]);
  const workspaceKnowledgeBaseLabel = useMemo(
    () => getWorkspaceKnowledgeBaseLabel(normalizedWorkspaceScope),
    [normalizedWorkspaceScope],
  );
  const conversationMatchesCurrentWorkspace = useMemo(
    () => (
      conversation?: Pick<ConversationListItem, 'scope_type' | 'scope_id'> | null,
    ) => {
      const conversationScope = normalizeWorkspaceScope({
        scopeType: conversation?.scope_type,
        scopeId: conversation?.scope_id,
      });

      if (conversationScope.scopeType !== normalizedWorkspaceScope.scopeType) {
        return false;
      }

      if (conversationScope.scopeType === 'knowledge_point') {
        return conversationScope.scopeId === normalizedWorkspaceScope.scopeId;
      }

      return true;
    },
    [normalizedWorkspaceScope.scopeId, normalizedWorkspaceScope.scopeType],
  );

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
      mediaStreamRef.current = null;
      audioChunksRef.current = [];
      pendingImages.forEach((image) => URL.revokeObjectURL(image.previewUrl));
      pendingVideos.forEach((video) => URL.revokeObjectURL(video.previewUrl));
    };
  }, [pendingImages, pendingVideos]);

  useEffect(() => {
    return () => {
      Object.values(messageImageUrls).forEach((url) => revokePreviewMediaUrl(url));
    };
  }, [messageImageUrls]);

  useEffect(() => {
    return () => {
      Object.values(messageVideoUrls).forEach((url) => revokePreviewMediaUrl(url));
    };
  }, [messageVideoUrls]);

  useEffect(() => {
    return () => {
      Object.values(sourceImageUrls).forEach((url) => revokePreviewMediaUrl(url));
    };
  }, [sourceImageUrls]);

  useEffect(() => {
    return () => {
      Object.values(sourceVideoUrls).forEach((url) => revokePreviewMediaUrl(url));
    };
  }, [sourceVideoUrls]);

  const persistedMessageImageUrls = useMemo(() => {
    const urls = new Set<string>();
    messages.forEach((item) => {
      (item.inputImages || []).forEach((image) => {
        const imageUrl = String(image.image_url || '').trim();
        if (imageUrl) {
          urls.add(imageUrl);
        }
      });
    });
    return Array.from(urls);
  }, [messages]);

  const persistedMessageVideoUrls = useMemo(() => {
    const urls = new Set<string>();
    messages.forEach((item) => {
      (item.inputVideos || []).forEach((video) => {
        const videoUrl = String(video.video_url || '').trim();
        if (videoUrl) {
          urls.add(videoUrl);
        }
      });
    });
    return Array.from(urls);
  }, [messages]);

  const persistedSourceVideoUrls = useMemo(() => {
    const urls = new Set<string>();
    messages.forEach((item) => {
      (item.sources || []).forEach((source) => {
        const modality = String(source?.modality || source?.metadata?.modality || '').toLowerCase();
        const videoUrl = String(source?.video_url || source?.metadata?.video_url || '').trim();
        if (modality === 'video' && videoUrl) {
          urls.add(videoUrl);
        }
      });
    });
    return Array.from(urls);
  }, [messages]);

  const persistedSourceImageUrls = useMemo(() => {
    const urls = new Set<string>();
    messages.forEach((item) => {
      (item.sources || []).forEach((source) => {
        const modality = String(source?.modality || source?.metadata?.modality || '').toLowerCase();
        const imageUrl = String(source?.image_url || source?.metadata?.image_url || '').trim();
        if (modality === 'image' && imageUrl) {
          urls.add(imageUrl);
        }
      });
    });
    return Array.from(urls);
  }, [messages]);

  useEffect(() => {
    if (persistedMessageImageUrls.length === 0) {
      setMessageImageUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllMessageImages = async () => {
      const resolvedEntries = await Promise.all(
        persistedMessageImageUrls.map(async (imageUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(imageUrl);
            return [imageUrl, objectUrl] as const;
          } catch (error) {
            console.error('load chat message image error:', imageUrl, error);
            return [imageUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setMessageImageUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextUrls;
      });
    };

    void loadAllMessageImages();

    return () => {
      cancelled = true;
    };
  }, [persistedMessageImageUrls]);

  useEffect(() => {
    if (persistedMessageVideoUrls.length === 0) {
      setMessageVideoUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllMessageVideos = async () => {
      const resolvedEntries = await Promise.all(
        persistedMessageVideoUrls.map(async (videoUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(videoUrl);
            return [videoUrl, objectUrl] as const;
          } catch (error) {
            console.error('load chat message video error:', videoUrl, error);
            return [videoUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setMessageVideoUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextUrls;
      });
    };

    void loadAllMessageVideos();

    return () => {
      cancelled = true;
    };
  }, [persistedMessageVideoUrls]);

  useEffect(() => {
    if (persistedSourceImageUrls.length === 0) {
      setSourceImageUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllSourceImages = async () => {
      const resolvedEntries = await Promise.all(
        persistedSourceImageUrls.map(async (imageUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(imageUrl);
            return [imageUrl, objectUrl] as const;
          } catch (error) {
            console.error('load chat source image error:', imageUrl, error);
            return [imageUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setSourceImageUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextUrls;
      });
    };

    void loadAllSourceImages();

    return () => {
      cancelled = true;
    };
  }, [persistedSourceImageUrls]);

  useEffect(() => {
    if (persistedSourceVideoUrls.length === 0) {
      setSourceVideoUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return {};
      });
      return;
    }

    let cancelled = false;

    const loadAllSourceVideos = async () => {
      const resolvedEntries = await Promise.all(
        persistedSourceVideoUrls.map(async (videoUrl) => {
          try {
            const objectUrl = await loadPreviewMediaUrl(videoUrl);
            return [videoUrl, objectUrl] as const;
          } catch (error) {
            console.error('load chat source video error:', videoUrl, error);
            return [videoUrl, ''] as const;
          }
        }),
      );

      if (cancelled) {
        resolvedEntries.forEach(([, objectUrl]) => revokePreviewMediaUrl(objectUrl));
        return;
      }

      const nextUrls = Object.fromEntries(
        resolvedEntries.filter(([, objectUrl]) => Boolean(objectUrl)),
      );

      setSourceVideoUrls((current) => {
        Object.values(current).forEach((url) => revokePreviewMediaUrl(url));
        return nextUrls;
      });
    };

    void loadAllSourceVideos();

    return () => {
      cancelled = true;
    };
  }, [persistedSourceVideoUrls]);

  const loadHistoryPage = async ({
    offset = 0,
    append = false,
  }: {
    offset?: number;
    append?: boolean;
  }) => {
    const result = await listChatConversations({
      courseId,
      scopeType: workspaceScopeApiParams.scopeType,
      scopeId: workspaceScopeApiParams.scopeId,
      aggregate: workspaceScopeApiParams.aggregate,
      limit: HISTORY_PAGE_SIZE,
      offset,
    });
    const nextItems = result.conversations || [];
    setHistoryTotal(typeof result.total === 'number' ? result.total : nextItems.length);
    setHistoryList((current) => {
      if (!append) {
        return nextItems;
      }
      const seen = new Set(current.map((item) => item.conversation_id));
      return [...current, ...nextItems.filter((item) => !seen.has(item.conversation_id))];
    });
    return nextItems;
  };

  useEffect(() => {
    const init = async () => {
      setHistoryLoading(true);
      try {
        const list = await loadHistoryPage({ offset: 0, append: false });

        const storedConversationId = String(currentConversationId || '').trim();
        const storedConversation = storedConversationId
          ? list.find((item) => item.conversation_id === storedConversationId)
          : undefined;
        const storedConversationExists = Boolean(
          storedConversation && conversationMatchesCurrentWorkspace(storedConversation),
        );
        const initialConversation = list.find((item) => conversationMatchesCurrentWorkspace(item));

        if (storedConversationExists) {
          await loadConversation(storedConversationId, false);
        } else if (initialConversation) {
          setCurrentConversationId(initialConversation.conversation_id);
          await loadConversation(initialConversation.conversation_id, false);
        } else {
          setMessages([]);
          setCurrentConversationId(null);
          setStatusCard(null);
          setWorkflowType(null);
          setWorkflowStatus(null);
          clearArtifactReference();
          clearConversationReference();
          clearConversationGeneratedFiles();
          setViewingFile(null);
        }
      } catch (error) {
        console.error('加载历史对话失败:', error);
      } finally {
        setHistoryLoading(false);
      }
    };

    void init();
  }, [
    courseId,
    conversationMatchesCurrentWorkspace,
    workspaceScopeApiParams.aggregate,
    workspaceScopeApiParams.scopeId,
    workspaceScopeApiParams.scopeType,
  ]);

  const refreshHistoryList = async () => {
    try {
      await loadHistoryPage({ offset: 0, append: false });
    } catch (error) {
      console.error('刷新历史对话失败:', error);
    }
  };

  const handleLoadMoreHistory = async () => {
    if (historyLoadingMore || historyList.length >= historyTotal) {
      return;
    }
    setHistoryLoadingMore(true);
    try {
      await loadHistoryPage({
        offset: historyList.length,
        append: true,
      });
    } catch (error) {
      console.error('鍔犺浇鏇村鍘嗗彶瀵硅瘽澶辫触:', error);
      message.error('鍔犺浇鏇村鍘嗗彶瀵硅瘽澶辫触');
    } finally {
      setHistoryLoadingMore(false);
    }
  };

  const loadConversation = async (conversationId: string, showSuccess = true, silent = false) => {
    if (!silent) {
      setLoadingConversationId(conversationId);
    }
    try {
      const detail = await getChatConversationDetail(conversationId);
      const detailScope = normalizeWorkspaceScope({
        scopeType: detail.scope_type,
        scopeId: detail.scope_id,
      });
      if (
        onWorkspaceScopeChange
        && (
          detailScope.scopeType !== normalizedWorkspaceScope.scopeType
          || detailScope.scopeId !== normalizedWorkspaceScope.scopeId
        )
      ) {
        onWorkspaceScopeChange(detailScope);
      }
      const mapped: Message[] = (detail.history || [])
        .filter((msg: any) => {
          // Internal tool exchange (role='tool' or message_kind='tool_exchange') is
          // for LLM context only — never user-facing. Without this filter, internal
          // prompts injected via _format_tool_result_for_context render as user
          // bubbles after page refresh.
          if (msg.message_kind === 'tool_exchange') return false;
          if (msg.role === 'tool') return false;
          // Skip assistant-with-only-tool_calls turns (no visible text)
          if (msg.role === 'assistant' && !String(msg.content || '').trim() && msg.tool_calls) return false;
          return true;
        })
        .map((msg: any) => ({
          user: msg.role === 'assistant' ? 'AI' : 'You',
          text: msg.content || '',
          sources: (msg.sources || []) as any[],
          inputImages: (msg.input_images || []) as ChatInputImageV2[],
          inputVideos: (msg.input_videos || []) as ChatInputVideoV2[],
        }));
      const detailWorkflowState = detail?.state?.workflow_state;
      const nextWorkflowType = String((detailWorkflowState as any)?.workflow_type || '').trim();
      const nextWorkflowStatus = String((detailWorkflowState as any)?.status || '').trim();

      if (!(silent && isLoading)) {
        setMessages(mapped);
      }
      setCurrentConversationId(detail.conversation_id);
      setStatusCard(detail.status_card || null);
      setWorkflowType(nextWorkflowType || null);
      setWorkflowStatus(nextWorkflowStatus || null);
      const restoredFiles = restoreGeneratedFilesFromConversationDetail(detail);
      replaceConversationGeneratedFiles(restoredFiles);
      const stateArtifactReference = detail?.state?.artifact_reference;
      if (stateArtifactReference && typeof stateArtifactReference === 'object') {
        setArtifactReference({
          artifact_id: String((stateArtifactReference as any).artifact_id || '').trim(),
          artifact_type: normalizeArtifactReferenceType((stateArtifactReference as any).artifact_type),
          version_id: String((stateArtifactReference as any).version_id || '').trim() || undefined,
          title: String((stateArtifactReference as any).title || '').trim() || undefined,
          source_conversation_id: String((stateArtifactReference as any).source_conversation_id || detail.conversation_id || '').trim() || undefined,
          source_course_id: String((stateArtifactReference as any).source_course_id || courseId || '').trim() || undefined,
        });
      } else {
        clearArtifactReference();
      }
      const stateConversationReference = detail?.state?.conversation_reference;
      if (stateConversationReference && typeof stateConversationReference === 'object') {
        setConversationReference({
          conversation_id: String((stateConversationReference as any).conversation_id || '').trim(),
          title: String((stateConversationReference as any).title || '').trim() || undefined,
          message_count:
            typeof (stateConversationReference as any).message_count === 'number'
              ? (stateConversationReference as any).message_count
              : undefined,
        });
      } else {
        clearConversationReference();
      }
      if (silent && nextWorkflowType === 'ppt' && nextWorkflowStatus === 'completed' && restoredFiles.length > 0) {
        setViewingFile(restoredFiles[restoredFiles.length - 1]);
      } else if (!silent) {
        setViewingFile(null);
      }

      if (showSuccess && !silent) {
        message.success('已切换到历史对话');
      }
    } catch (error: any) {
      console.error('加载对话详情失败:', error);
      if (!silent) {
        message.error(error?.message || '加载历史对话失败');
      }
    } finally {
      if (!silent) {
        setLoadingConversationId(null);
      }
    }
  };

  const handleNewConversation = () => {
    setMessages([]);
    setCurrentConversationId(null);
    setInputValue('');
    setStatusCard(null);
    setWorkflowType(null);
    setWorkflowStatus(null);
    clearArtifactReference();
    clearConversationReference();
    clearConversationGeneratedFiles();
    setViewingFile(null);
    message.success('已新建对话');
  };

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      await deleteChatConversation(conversationId);

      const nextHistory = historyList.filter((item) => item.conversation_id !== conversationId);
      setHistoryList(nextHistory);
      removeGeneratedFilesByConversationId(conversationId);

      if (currentConversationId === conversationId) {
        if (nextHistory.length > 0) {
          await loadConversation(nextHistory[0].conversation_id, false);
        } else {
          setMessages([]);
          setCurrentConversationId(null);
          setStatusCard(null);
          setWorkflowType(null);
          setWorkflowStatus(null);
          clearArtifactReference();
          clearConversationReference();
          setViewingFile(null);
        }
      }

      message.success('历史对话已删除');
    } catch (error: any) {
      console.error('删除对话失败:', error);
      message.error(error?.message || '删除历史对话失败');
    }
  };

  const transcribeAudioFile = async (file: Blob, filename: string) => {
    try {
      setIsTranscribing(true);
      const result = await transcribeSpeechV2(file, filename);
      setInputValue((previous) => appendTranscript(previous, result.text));
      message.success('语音已转换为文本');
    } catch (error: any) {
      console.error('speech transcription error:', error);
      message.error(error?.message || '语音识别失败');
    } finally {
      setIsTranscribing(false);
    }
  };

  const handleVoiceInput = async () => {
    if (isTranscribing) {
      return;
    }

    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    if (typeof window === 'undefined' || !window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      message.error('当前浏览器不支持语音输入');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });

        mediaRecorderRef.current = null;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        audioChunksRef.current = [];

        if (audioBlob.size === 0) {
          message.warning('未录到有效语音内容');
          return;
        }

        void transcribeAudioFile(audioBlob, buildSpeechFileName(mimeType));
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error: any) {
      console.error('start recording error:', error);
      const resolution = resolveSpeechInputError(error);
      message.error(resolution.message);
    }
  };

  const clearPendingImages = () => {
    setPendingImages((current) => {
      current.forEach((image) => URL.revokeObjectURL(image.previewUrl));
      return [];
    });
  };

  const clearPendingVideos = () => {
    setPendingVideos((current) => {
      current.forEach((video) => URL.revokeObjectURL(video.previewUrl));
      return [];
    });
  };

  const handleRemovePendingImage = (imageId: string) => {
    setPendingImages((current) => current.filter((image) => image.image_id !== imageId));
  };

  const handleRemovePendingVideo = (videoId: string) => {
    setPendingVideos((current) => current.filter((video) => video.video_id !== videoId));
  };

  const handleAddImages = async (files: File[], source: 'upload' | 'paste') => {
    const imageFiles = files.filter((file) => String(file.type || '').startsWith('image/'));
    if (imageFiles.length === 0) {
      return;
    }

    const previewUrls = imageFiles.map((file) => URL.createObjectURL(file));
    try {
      const uploaded = await uploadChatImagesV2(imageFiles, {
        conversationId: currentConversationId,
        source,
      });
      const nextImages = (uploaded.images || []).map((image, index) => ({
        ...image,
        previewUrl: previewUrls[index] || '',
      }));
      setPendingImages((current) => [...current, ...nextImages]);
      message.success(`已添加 ${nextImages.length} 张图片`);
    } catch (error: any) {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
      console.error('upload chat images error:', error);
      message.error(error?.message || '图片上传失败');
    }
  };

  const handleAddVideos = async (files: File[]) => {
    const videoFiles = files.filter((file) => String(file.type || '').startsWith('video/'));
    if (videoFiles.length === 0) {
      return;
    }

    const previewUrls = videoFiles.map((file) => URL.createObjectURL(file));
    try {
      const uploaded = await uploadChatVideosV2(videoFiles, {
        conversationId: currentConversationId,
        source: 'upload',
      });
      const nextVideos = (uploaded.videos || []).map((video, index) => ({
        ...video,
        previewUrl: previewUrls[index] || '',
      }));
      setPendingVideos((current) => [...current, ...nextVideos]);
      message.success('已添加 ' + nextVideos.length + ' 个视频');
    } catch (error: any) {
      previewUrls.forEach((url) => URL.revokeObjectURL(url));
      console.error('upload chat videos error:', error);
      message.error(error?.message || '视频上传失败');
    }
  };

  const handleImagePaste = async (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const imageFiles = Array.from(event.clipboardData?.items || [])
      .filter((item) => item.kind === 'file' && String(item.type || '').startsWith('image/'))
      .map((item) => item.getAsFile())
      .filter((file): file is File => Boolean(file));

    if (imageFiles.length === 0) {
      return;
    }

    event.preventDefault();
    await handleAddImages(imageFiles, 'paste');
  };

  const handleImagePickerChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    await handleAddImages(files, 'upload');
  };

  const handleVideoPickerChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    await handleAddVideos(files);
  };

  const handleSendMessage = async (overrideText?: string, forceSend = false) => {
    const draft = (overrideText ?? inputValue).trim();
    if ((draft === '' && pendingImages.length === 0 && pendingVideos.length === 0) || (isLoading && !forceSend)) return;

    const inputImages = pendingImages.map(({ previewUrl: _previewUrl, ...image }) => image);
    const inputVideos = pendingVideos.map(({ previewUrl: _previewUrl, ...video }) => video);

    const userMessage: Message = { user: 'You', text: draft || '已发送附件' };
    userMessage.inputImages = inputImages;
    userMessage.inputVideos = inputVideos;
    addMessage(userMessage);
    setInputValue('');
    setIsLoading(true);
    setQueuedMessage(null);

    const aiResponse: Message = { user: 'AI', text: '', statusText: 'Thinking...' };
    addMessage(aiResponse);

    try {
      // Checked documents are always a mandatory, scoped RAG source.
      // Enabling the RAG knowledge-base button expands that scope to every
      // document currently mounted in the workspace, regardless of which
      // individual rows are checked.
      const effectiveSelectedDocIds = resolveChatRetrievalDocIds({
        mountFullKnowledgeBase: allowRag,
        selectedDocIds: selectedDocs,
        scopedDocIds: scopedSourceDocIds,
      });
      const payload = buildChatReplyPayload({
        question: userMessage.text,
        conversationId: currentConversationId,
        courseId,
        scopeType: workspaceScopeApiParams.scopeType,
        scopeId: workspaceScopeApiParams.scopeId,
        allowRag,
        allowWeb,
        selectedDocIds: effectiveSelectedDocIds,
        inputImages,
        inputVideos,
        artifactReference,
        conversationReference,
      });
      let streamedText = '';
      let response: ChatResponseV2 | null = null;
      let pendingTaskId: string | null = null;
      const agentActivity: AgentActivityState = emptyAgentActivity();
      const flushAgentActivity = () => {
        // Shallow copy so React detects a change
        updateLastMessage({
          agentActivity: {
            plan: agentActivity.plan,
            stepStatus: { ...agentActivity.stepStatus },
            toolCalls: [...agentActivity.toolCalls],
            toolResults: [...agentActivity.toolResults],
            reflects: [...agentActivity.reflects],
          },
        });
      };

      await sendChatReplyV2Stream(payload, {
        onMetadata: (payload) => {
          const nextConversationId = String(payload.conversation_id || '').trim();
          if (nextConversationId && nextConversationId !== currentConversationId) {
            setCurrentConversationId(nextConversationId);
          }
          if (Array.isArray(payload.sources)) {
            updateLastMessage({
              sources: payload.sources as ChatSourceV2[],
              statusText: '正在生成回复...',
            });
          }
          if (payload.status_card && typeof payload.status_card === 'object') {
            setStatusCard(payload.status_card as any);
          }
        },
        onStatus: (payload) => {
          updateLastMessage({
            statusText: String(payload.label || payload.stage || '正在处理...'),
          });
          const workflow = payload.workflow as any;
          if (workflow) {
            setWorkflowType(String(workflow.type || '').trim() || null);
            setWorkflowStatus(String(workflow.status || '').trim() || null);
          }
        },
        onDelta: (content) => {
          streamedText += content;
          updateLastMessage({
            text: streamedText,
            statusText: '正在生成回复...',
          });
        },
        onResult: (finalResponse) => {
          response = finalResponse;
        },
        onTaskSubmitted: (taskId) => {
          pendingTaskId = taskId;
          requestJobRefresh(taskId);
          // Tag the AI message with the task ID so the background poller can find and update it
          updateLastMessage({ id: taskId });
        },
        onPlan: (plan) => {
          agentActivity.plan = plan;
          flushAgentActivity();
        },
        onPlanStepUpdate: (update) => {
          agentActivity.stepStatus[update.step_index] = update.status;
          flushAgentActivity();
        },
        onToolCall: (call) => {
          agentActivity.toolCalls.push(call);
          flushAgentActivity();
        },
        onToolResult: (result) => {
          agentActivity.toolResults.push(result);
          flushAgentActivity();
        },
        onReflect: (reflect) => {
          agentActivity.reflects.push(reflect);
          flushAgentActivity();
        },
        onError: (error) => {
          throw error;
        },
      });

      // Background task path: hand off to useEffect poller and release the UI immediately
      if (pendingTaskId) {
        updateLastMessage({ statusText: '正在后台生成，请稍候...' });
        setBackgroundTaskId(pendingTaskId);
        return; // isLoading → false via finally; user can continue chatting
      } else if (!response) {
        throw new Error('流式回复未返回最终结果');
      }

      const nextConversationId = String(response.conversation?.conversation_id || '').trim();
      if (nextConversationId && nextConversationId !== currentConversationId) {
        setCurrentConversationId(nextConversationId);
      }
      setStatusCard(response.status_card || null);
      setWorkflowType(String(response.workflow?.type || '').trim() || null);
      setWorkflowStatus(String(response.workflow?.status || '').trim() || null);

      const sources = Array.isArray(response.sources) ? (response.sources as ChatSourceV2[]) : [];
      const generatedFiles = extractGeneratedFilesFromV2Response(response).map((file) => ({
        ...file,
        meta: {
          ...(file.meta || {}),
          origin: 'conversation',
          conversationId: nextConversationId || currentConversationId,
        },
      }));

      generatedFiles.forEach((file) => addGeneratedFile(file));
      const nextPptArtifact = generatedFiles.find((file) => file.meta?.kind === 'ppt_deck');
      if (artifactReference?.artifact_type === 'ppt_deck' && nextPptArtifact) {
        setArtifactReference({
          artifact_id: String(nextPptArtifact.meta?.originalArtifactId || nextPptArtifact.id).trim(),
          artifact_type: 'ppt_deck',
          title: nextPptArtifact.name,
          source_conversation_id: String(
            nextPptArtifact.meta?.conversationId || nextConversationId || currentConversationId || '',
          ).trim() || undefined,
          source_course_id: String(courseId || '').trim() || undefined,
        });
      }
      if (courseId) {
        generatedFiles.forEach((file) =>
          addMaterial({
            id: file.id,
            name: file.name,
            type: file.type,
            content: file.content,
            addedAt: String(file.meta?.addedAt || new Date().toISOString()),
            courseId,
            isPinned: Boolean(file.meta?.isPinned),
            pinnedAt: typeof file.meta?.pinnedAt === 'string' ? file.meta.pinnedAt : undefined,
          } as any),
        );
      }
      if (generatedFiles.length > 0) {
        setViewingFile(generatedFiles[generatedFiles.length - 1]);
      }

      const replyText = resolveGenerationReply({
        generatedResourceCount: generatedFiles.length,
        fallbackMessage: String(response.message?.content || ''),
      });

      updateLastMessage({
        text: replyText,
        sources,
        statusText: '',
      });

      await refreshHistoryList();
      clearPendingImages();
      clearPendingVideos();
    } catch (error: any) {
      console.error('v2 reply error:', error);
      updateLastMessage({
        text: error?.message || 'Request failed. Please try again.',
        statusText: 'Failed',
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!queuedMessage || isLoading) return;
    void handleSendMessage(queuedMessage, true);
  }, [queuedMessage, isLoading, pendingImages, pendingVideos]);

  useEffect(() => {
    if (isLoading || !currentConversationId || workflowType !== 'ppt' || workflowStatus !== 'running') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadConversation(currentConversationId, false, true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [currentConversationId, isLoading, workflowStatus, workflowType]);

  // Consume the result once the global task manager observes a terminal state.
  useEffect(() => {
    if (!backgroundTaskId) return undefined;

    const taskId = backgroundTaskId;
    const globalJob = jobsById[taskId];
    if (!globalJob || !isTerminalJob(globalJob)) return undefined;
    setBackgroundTaskId(null);
    if (globalJob.status !== 'succeeded') {
      updateMessageById(taskId, {
        text:
          globalJob.error_message ||
          globalJob.error ||
          (globalJob.status === 'canceled'
            ? '生成任务已取消。'
            : '生成失败，请重试。'),
        statusText: '',
        status: 'error',
      });
      return undefined;
    }

    void (async () => {
        try {
          const status = await pollChatTask(taskId);

          if (status.status === 'completed') {
            if (!status.result) {
              updateMessageById(taskId, { text: '生成完成，但未返回内容。', statusText: '', status: 'done' });
              return;
            }
            const result = status.result;
            const nextConversationId = String(result.conversation?.conversation_id || '').trim();
            if (nextConversationId && nextConversationId !== currentConversationId) {
              setCurrentConversationId(nextConversationId);
            }
            setStatusCard(result.status_card || null);
            setWorkflowType(String(result.workflow?.type || '').trim() || null);
            setWorkflowStatus(String(result.workflow?.status || '').trim() || null);

            const sources = Array.isArray(result.sources) ? (result.sources as ChatSourceV2[]) : [];
            const genFiles = extractGeneratedFilesFromV2Response(result).map((file) => ({
              ...file,
              meta: {
                ...(file.meta || {}),
                origin: 'conversation',
                conversationId: nextConversationId || currentConversationId,
              },
            }));
            genFiles.forEach((file) => addGeneratedFile(file));
            const nextPptArtifact = genFiles.find((f) => f.meta?.kind === 'ppt_deck');
            if (artifactReference?.artifact_type === 'ppt_deck' && nextPptArtifact) {
              setArtifactReference({
                artifact_id: String(nextPptArtifact.meta?.originalArtifactId || nextPptArtifact.id).trim(),
                artifact_type: 'ppt_deck',
                title: nextPptArtifact.name,
                source_conversation_id: String(nextPptArtifact.meta?.conversationId || nextConversationId || currentConversationId || '').trim() || undefined,
                source_course_id: String(courseId || '').trim() || undefined,
              });
            }
            if (courseId) {
              genFiles.forEach((file) =>
                addMaterial({
                  id: file.id,
                  name: file.name,
                  type: file.type,
                  content: file.content,
                  addedAt: String(file.meta?.addedAt || new Date().toISOString()),
                  courseId,
                  isPinned: Boolean(file.meta?.isPinned),
                  pinnedAt: typeof file.meta?.pinnedAt === 'string' ? file.meta.pinnedAt : undefined,
                } as any),
              );
            }
            if (genFiles.length > 0) setViewingFile(genFiles[genFiles.length - 1]);

            const replyText = resolveGenerationReply({
              generatedResourceCount: genFiles.length,
              fallbackMessage: String(result.message?.content || ''),
            });
            updateMessageById(taskId, { text: replyText, sources, statusText: '', status: 'done' });
            void refreshHistoryList();
          } else if (status.status === 'failed') {
            updateMessageById(taskId, { text: status.error || '生成失败，请重试。', statusText: '', status: 'error' });
          }
        } catch {
          updateMessageById(taskId, {
            text: buildGenerationSavedMessage({ visibility: 'private' }),
            statusText: '',
            status: 'done',
          });
          void refreshHistoryList();
        }
    })();
    return undefined;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backgroundTaskId, jobsById]);

  const handleSourceClick = (source: any) => {
    const path =
      source?.source_path ||
      source?.sourcePath ||
      source?.source ||
      source?.source_path_encoded ||
      source?.source_path_raw;

    if (!path) return;

    setHighlightRequest({
      filePath: path,
      source: source as RAGSource,
    });
  };

  const renderSourceTag = (entry: InlineSourceEntry, index: number, keyPrefix: string, compact = false) => {
    const { source, order } = entry;
    const isImage = String((source as any)?.modality || (source as any)?.metadata?.modality || '').toLowerCase() === 'image';
    const isVideo = String((source as any)?.modality || (source as any)?.metadata?.modality || '').toLowerCase() === 'video';
    const sourceName = getDisplayLabel(source?.source, `来源 ${order}`);
    const dotLabel = String(order);
    const kindLabel = isVideo ? '视频来源' : isImage ? '图片来源' : '文本来源';

    return (
      <Tooltip
        key={`${keyPrefix}-${index}`}
        title={source?.content ? (`${kindLabel} ${dotLabel} · ${sourceName}\n完整命中片段预览：${String(source.content).substring(0, 100)}...`) : `${kindLabel} ${dotLabel} · ${sourceName}`}
      >
        <button
          type="button"
          className={`chat-panel__source-dot chat-panel__source-dot--${compact ? 'inline' : 'floating'}`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            handleSourceClick(source);
          }}
          onMouseDown={(event) => {
            event.preventDefault();
          }}
          aria-label={`${kindLabel} ${dotLabel}：${sourceName}`}
        >
          {dotLabel}
        </button>
      </Tooltip>
    );
  };

  const renderInlineSourceTags = (sources: InlineSourceEntry[], keyPrefix: string) => {
    if (!sources.length) {
      return null;
    }

    return (
      <span className="chat-panel__inline-sources">
        {sources.map((source, index) => renderSourceTag(source, index, keyPrefix, true))}
      </span>
    );
  };

  const visibleHistoryList = useMemo(() => {
    return historyList;
  }, [historyExpanded, historyList]);

  const historyContent = (
    <div className="chat-panel__history-popover">
      {historyLoading ? (
        <div className="chat-panel__history-loading">
          <Spin size="small" /> <Text style={{ marginLeft: 8 }}>加载中...</Text>
        </div>
      ) : historyList.length === 0 ? (
        <div className="chat-panel__history-empty">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史对话" />
        </div>
      ) : (
        <>
          {visibleHistoryList.map((item) => (
            <div
              key={item.conversation_id}
              className={`chat-panel__history-item ${item.conversation_id === currentConversationId ? 'chat-panel__history-item--current' : ''}`}
            >
              <button
                type="button"
                className="chat-panel__history-entry"
                onClick={() => {
                  void loadConversation(item.conversation_id);
                  setHistoryPopoverOpen(false);
                  setHistoryExpanded(false);
                }}
              >
                <div className="chat-panel__history-meta">
                  <div className="chat-panel__history-title">
                    {getDisplayLabel(item.title, '未命名对话')}
                  </div>
                  <div className="chat-panel__history-subtitle">{item.message_count || 0} 条消息</div>
                </div>
              </button>

              <div className="chat-panel__history-actions">
                {loadingConversationId === item.conversation_id ? <Spin size="small" /> : null}

                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  className="chat-panel__history-delete"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    Modal.confirm({
                      title: '确认删除该历史对话？',
                      content: '删除后不可恢复。',
                      okText: '删除',
                      cancelText: '取消',
                      okButtonProps: { danger: true },
                      onOk: async () => {
                        await handleDeleteConversation(item.conversation_id);
                      },
                    });
                  }}
                />
              </div>
            </div>
          ))}

          {historyList.length < historyTotal && (
            <div className="chat-panel__history-more">
              <Button
                type="text"
                loading={historyLoadingMore}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  void handleLoadMoreHistory();
                }}
              >
                加载更多
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );

  const composerAdditions = (
    <div className="chat-panel__composer-popover">
      <button
        type="button"
        className="chat-panel__composer-popover-item"
        onClick={() => imageInputRef.current?.click()}
      >
        <PictureOutlined />
        <span>添加图片</span>
      </button>
      <button
        type="button"
        className="chat-panel__composer-popover-item"
        onClick={() => videoInputRef.current?.click()}
      >
        <VideoCameraOutlined />
        <span>添加视频</span>
      </button>
    </div>
  );

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <div className="chat-panel__heading">
          <Title level={5} className="chat-panel__title">
            对话
          </Title>
          <div className="chat-panel__subtitle">当前知识库：{workspaceKnowledgeBaseLabel}</div>
        </div>

        <div className="chat-panel__controls">
          <Space className="chat-panel__controls-main">
            <Button
              type="text"
              className="chat-panel__toolbar-button chat-panel__toolbar-button--new"
              onClick={handleNewConversation}
            >
              新建对话
            </Button>
            <Popover
              trigger="click"
              placement="bottomRight"
              content={historyContent}
              overlayClassName="chat-panel__history-popover-shell"
              open={historyPopoverOpen}
              onOpenChange={(open) => {
                setHistoryPopoverOpen(open);
                if (!open) {
                  setHistoryExpanded(false);
                }
              }}
            >
              <Button
                type="text"
                icon={<HistoryOutlined />}
                className="chat-panel__toolbar-button chat-panel__toolbar-button--history"
              >
                历史对话
              </Button>
            </Popover>
          </Space>
        </div>
      </div>

      <div className="chat-panel__messages">
        <div className="chat-panel__messages-scroll">
          <List
            className="chat-panel__message-list"
            dataSource={messages}
            locale={{
              emptyText: (
                <div className="chat-panel__conversation-empty">
                  <strong>开始一段课程对话</strong>
                  <span>从下方输入问题，或先从知识库选择资料作为回答依据。</span>
                </div>
              ),
            }}
            renderItem={(item, index) => {
              const inlineSourcePlan = item.user === 'AI'
                ? buildInlineSourcePlan(item.text, item.sources || [])
                : null;

              return (
                <List.Item
                  key={index}
                  className={`chat-panel__message-row chat-panel__message-row--${item.user === 'You' ? 'user' : 'ai'}`}
                >
                  <div className={`chat-panel__message-shell chat-panel__message-shell--${item.user === 'You' ? 'user' : 'ai'}`}>
                    <div className={`chat-panel__avatar chat-panel__avatar--${item.user === 'You' ? 'user' : 'ai'}`}>
                      {item.user === 'You' ? '你' : 'AI'}
                    </div>
                    <div className="chat-panel__message-content">
                    {item.user === 'AI' && item.statusText && (
                      <div className="chat-panel__status-text">
                        {item.statusText}
                      </div>
                    )}
                    {item.user === 'AI' && Boolean(item.agentActivity) && (
                      <AgentActivityPanel
                        activity={item.agentActivity as AgentActivityState}
                        defaultExpanded={Boolean(item.statusText)}
                        mergedTimeline={buildMergedTimeline(messages as unknown as Message[], index)}
                      />
                    )}
                    {item.inputImages && item.inputImages.length > 0 && (
                    <div className="chat-panel__media-strip" style={{ marginBottom: item.text ? 10 : 0 }}>
                      <Space wrap size={[8, 8]}>
                        {item.inputImages.map((image) => {
                          const previewUrl = messageImageUrls[image.image_url];
                          const imageFileName = getDisplayLabel(image.file_name, '图片');
                          return (
                            <div
                              key={image.image_id}
                              style={{
                                width: 144,
                                borderRadius: 12,
                                overflow: 'hidden',
                                border: '1px solid rgba(0, 0, 0, 0.12)',
                                background: item.user === 'You' ? 'rgba(255,255,255,0.14)' : '#fff',
                              }}
                            >
                              {previewUrl ? (
                                <img
                                  src={previewUrl}
                                  alt={imageFileName}
                                  style={{ width: '100%', height: 108, objectFit: 'cover', display: 'block' }}
                                />
                              ) : (
                                <div
                                  style={{
                                    width: '100%',
                                    height: 108,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    background: 'rgba(0, 0, 0, 0.04)',
                                    color: item.user === 'You' ? 'rgba(255,255,255,0.92)' : '#666',
                                    fontSize: 12,
                                  }}
                                >
                                  图片加载中...
                                </div>
                              )}
                              <div
                                style={{
                                  padding: '6px 8px',
                                  fontSize: 12,
                                  color: item.user === 'You' ? 'rgba(255,255,255,0.92)' : '#666',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                                title={imageFileName}
                              >
                                {imageFileName}
                              </div>
                            </div>
                          );
                        })}
                      </Space>
                    </div>
                  )}
                    {item.inputVideos && item.inputVideos.length > 0 && (
                    <div className="chat-panel__media-strip" style={{ marginBottom: item.text ? 10 : 0 }}>
                      <Space wrap size={[8, 8]}>
                        {item.inputVideos.map((video) => {
                          const previewUrl = messageVideoUrls[video.video_url];
                          const videoFileName = getDisplayLabel(video.file_name, '视频');
                          return (
                            <div
                              key={video.video_id}
                              style={{
                                width: 180,
                                borderRadius: 12,
                                overflow: 'hidden',
                                border: '1px solid rgba(0, 0, 0, 0.12)',
                                background: item.user === 'You' ? 'rgba(255,255,255,0.14)' : '#fff',
                              }}
                            >
                              {previewUrl ? (
                                <video
                                  src={previewUrl}
                                  controls
                                  preload="metadata"
                                  style={{ width: '100%', height: 120, display: 'block', background: '#000' }}
                                />
                              ) : (
                                <div
                                  style={{
                                    width: '100%',
                                    height: 120,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    background: 'rgba(0, 0, 0, 0.04)',
                                    color: item.user === 'You' ? 'rgba(255,255,255,0.92)' : '#666',
                                    fontSize: 12,
                                  }}
                                >
                                  视频加载中...
                                </div>
                              )}
                              <div
                                style={{
                                  padding: '6px 8px',
                                  fontSize: 12,
                                  color: item.user === 'You' ? 'rgba(255,255,255,0.92)' : '#666',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                                title={videoFileName}
                              >
                                {videoFileName}
                              </div>
                            </div>
                          );
                        })}
                      </Space>
                    </div>
                  )}
                    {item.text ? (
                      <div className={`chat-panel__bubble chat-panel__bubble--${item.user === 'You' ? 'user' : 'ai'}`}>
                        {item.user === 'AI' && inlineSourcePlan ? (
                          <div className="chat-panel__inline-answer">
                            {inlineSourcePlan.blocks.map((block, blockIndex) => (
                              <div key={`message-${index}-block-${blockIndex}`} className="chat-panel__inline-answer-block">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm, remarkMath]}
                                  rehypePlugins={[rehypeKatex]}
                                  components={{
                                    p: ({ children }) => (
                                      <p className="chat-panel__markdown-paragraph">
                                        {children}
                                      </p>
                                    ),
                                  }}
                                >
                                  {block.markdown}
                                </ReactMarkdown>
                                {renderInlineSourceTags(block.sources, `message-${index}-block-${blockIndex}`)}
                              </div>
                            ))}
                          </div>
                        ) : item.user === 'AI' ? (
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                            components={{
                              p: ({ children }) => (
                                <p className="chat-panel__markdown-paragraph">
                                  {children}
                                </p>
                              ),
                              h1: ({ children }) => (
                                <h1 style={{
                                  fontSize: 18,
                                  fontWeight: 700,
                                  margin: '16px 0 8px',
                                  paddingBottom: 4,
                                  borderBottom: '1px solid #e8e8e8',
                                }}>{children}</h1>
                              ),
                              h2: ({ children }) => (
                                <h2 style={{
                                  fontSize: 16,
                                  fontWeight: 600,
                                  margin: '12px 0 6px',
                                  color: '#1677ff',
                                }}>{children}</h2>
                              ),
                              h3: ({ children }) => (
                                <h3 style={{
                                  fontSize: 14,
                                  fontWeight: 600,
                                  margin: '8px 0 4px',
                                  paddingLeft: 12,
                                  borderLeft: '2px solid #91caff',
                                }}>{children}</h3>
                              ),
                              h4: ({ children }) => (
                                <h4 style={{
                                  fontSize: 13,
                                  fontWeight: 500,
                                  margin: '6px 0 2px',
                                  paddingLeft: 24,
                                  color: '#555',
                                }}>{children}</h4>
                              ),
                              h5: ({ children }) => (
                                <h5 style={{
                                  fontSize: 13,
                                  fontWeight: 500,
                                  margin: '4px 0',
                                  paddingLeft: 36,
                                  color: '#777',
                                }}>{children}</h5>
                              ),
                              ul: ({ children }) => (
                                <ul style={{ paddingLeft: 24, margin: '4px 0' }}>{children}</ul>
                              ),
                              ol: ({ children }) => (
                                <ol style={{ paddingLeft: 24, margin: '4px 0' }}>{children}</ol>
                              ),
                              li: ({ children }) => (
                                <li style={{ margin: '2px 0', lineHeight: 1.7 }}>{children}</li>
                              ),
                            }}
                          >
                            {item.text}
                          </ReactMarkdown>
                        ) : (
                          <div className="chat-panel__user-text">{item.text}</div>
                        )}
                      </div>
                    ) : null}

                    {item.user === 'AI' && inlineSourcePlan && inlineSourcePlan.unmatchedSources.length > 0 && (
                      <div className="chat-panel__sources">
                        <Space wrap size={[0, 8]}>
                          {inlineSourcePlan.unmatchedSources.map((source, sourceIndex) =>
                            renderSourceTag(source, sourceIndex, `message-${index}-unmatched`),
                          )}
                        </Space>
                      </div>
                    )}
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
          <div ref={chatEndRef} />
        </div>
      </div>

      <div className="chat-panel__composer">
        {conversationReference ? (
          <div className="chat-panel__reference-card">
            <div className="chat-panel__reference-meta">
            <Text strong>{getDisplayLabel(conversationReference.title, '未命名对话')}</Text>
            <div>
              <Text type="secondary">
                历史对话
                {typeof conversationReference.message_count === 'number'
                  ? ` · ${conversationReference.message_count} 条消息`
                  : ''}
              </Text>
            </div>
            </div>

            <Button size="small" onClick={() => clearConversationReference()}>
              移除引用
            </Button>
          </div>

        ) : null}

        {artifactReference ? (
          <div className="chat-panel__reference-card">
            <div className="chat-panel__reference-meta">
            <Text strong>{getDisplayLabel(artifactReference.title, '未命名产物')}</Text>
            <div>
              <Text type="secondary">
                {artifactReference.artifact_type === 'report_outline'
                  ? '报告大纲'
                  : artifactReference.artifact_type === 'ppt_deck'
                    ? 'PPT 文件'
                    : artifactReference.artifact_type === 'ppt_outline'
                      ? 'PPT 大纲'
                      : artifactReference.artifact_type === 'ppt_content_markdown'
                        ? 'PPT 文稿'
                        : '报告正文'}
                {artifactReference.version_id ? ` · 版本 ${artifactReference.version_id}` : ''}
              </Text>
            </div>
            </div>
            <Button size="small" onClick={() => clearArtifactReference()}>
              移除引用
            </Button>
          </div>
        ) : null}

      <input
        ref={imageInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/bmp,image/gif"
        multiple
        style={{ display: 'none' }}
        onChange={(event) => {
          void handleImagePickerChange(event);
        }}
      />
      <input
        ref={videoInputRef}
        type="file"
        accept="video/mp4,video/webm,video/quicktime,video/x-m4v"
        multiple
        style={{ display: 'none' }}
        onChange={(event) => {
          void handleVideoPickerChange(event);
        }}
      />

        {pendingImages.length > 0 ? (
        <div className="chat-panel__pending-media">
          <Space wrap size={[8, 8]}>
            {pendingImages.map((image) => {
              const imageFileName = getDisplayLabel(image.file_name, '图片');
              return (
              <div
                key={image.image_id}
                className="chat-panel__pending-media-card chat-panel__pending-media-card--image"
              >
                <img
                  src={image.previewUrl}
                  alt={imageFileName}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemovePendingImage(image.image_id)}
                  style={{ position: 'absolute', top: 0, right: 0 }}
                />
              </div>
              );
            })}
          </Space>
        </div>
        ) : null}

        {pendingVideos.length > 0 ? (
        <div className="chat-panel__pending-media">
          <Space wrap size={[8, 8]}>
            {pendingVideos.map((video) => {
              const videoFileName = getDisplayLabel(video.file_name, '视频');
              return (
              <div
                key={video.video_id}
                className="chat-panel__pending-media-card chat-panel__pending-media-card--video"
              >
                <video
                  src={video.previewUrl}
                  preload="metadata"
                  controls
                  style={{ width: '100%', height: 88, display: 'block', background: '#000' }}
                />
                <div
                  style={{
                    padding: '6px 8px',
                    fontSize: 12,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={videoFileName}
                >
                  {videoFileName}
                </div>
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemovePendingVideo(video.video_id)}
                  style={{ position: 'absolute', top: 0, right: 0 }}
                />
              </div>
              );
            })}
          </Space>
        </div>
        ) : null}

        <div className="chat-panel__composer-inner">
          <div className="chat-panel__composer-editor">
            <TextArea
              autoSize={{ minRows: 2, maxRows: 6 }}
              placeholder={isTranscribing ? '正在识别语音...' : '开始输入问题…（Shift + Enter 换行）'}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPaste={(event) => { void handleImagePaste(event); }}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  void handleSendMessage();
                }
              }}
              disabled={isLoading}
              size="large"
              className="chat-panel__composer-input"
            />
          </div>

          <div className="chat-panel__composer-actions">
            <div className="chat-panel__composer-secondary-actions">
              <Popover
                trigger="click"
                placement="topLeft"
                content={composerAdditions}
                overlayClassName="chat-panel__composer-popover-shell"
              >
                <Button
                  icon={<PlusOutlined />}
                  disabled={isLoading || isTranscribing}
                  size="large"
                  className="chat-panel__composer-plus-button"
                />
              </Popover>

              <div className="chat-panel__composer-toggle-group">
                <Tooltip title="开启后，本轮强制检索当前工作区的整个知识库">
                  <Button
                    size="large"
                    className={`chat-panel__composer-mode-button ${allowRag ? 'chat-panel__composer-mode-button--active' : ''}`}
                    onClick={() => setAllowRag(!allowRag)}
                    disabled={isLoading}
                  >
                    RAG知识库
                  </Button>
                </Tooltip>
                <Tooltip title="开启后，本轮强制进行联网搜索">
                  <Button
                    size="large"
                    className={`chat-panel__composer-mode-button ${allowWeb ? 'chat-panel__composer-mode-button--active' : ''}`}
                    onClick={() => setAllowWeb(!allowWeb)}
                    disabled={isLoading}
                  >
                    Web搜索
                  </Button>
                </Tooltip>
              </div>
            </div>

            <div className="chat-panel__composer-primary-actions">
              <Tooltip title={isRecording ? '点击停止录音并转成文字' : isTranscribing ? '正在识别语音' : '语音输入'}>
                <Button
                  shape="circle"
                  icon={<AudioOutlined />}
                  onClick={() => void handleVoiceInput()}
                  disabled={isLoading || isTranscribing}
                  danger={isRecording}
                  size="large"
                  className="chat-panel__voice-button"
                />
              </Tooltip>
              <Tooltip title="发送">
                <Button
                  type="primary"
                  shape="circle"
                  icon={<SendOutlined />}
                  onClick={() => void handleSendMessage()}
                  loading={isLoading}
                  size="large"
                  className="chat-panel__send-button"
                />
              </Tooltip>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPanel;




