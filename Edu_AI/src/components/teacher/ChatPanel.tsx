import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Input, Button, List, Space, Typography, Tag, Tooltip, message, Empty, Spin, Modal, Popover } from 'antd';
import { SendOutlined, SnippetsOutlined, HistoryOutlined, DeleteOutlined, AudioOutlined, PictureOutlined, VideoCameraOutlined, PlusOutlined } from '@ant-design/icons';
import { useStore } from '../../store/teacher/useStore';
import { useCourseMaterialsStore } from '../../store/teacher/useCourseMaterialsStore';
import { listChatConversations, getChatConversationDetail, deleteChatConversation, type ConversationListItem } from '../../services/teacher/api';
import {
  buildChatReplyPayload,
  sendChatReplyV2Stream,
  transcribeSpeechV2,
  uploadChatImagesV2,
  uploadChatVideosV2,
  type ChatResponseV2,
  type ChatInputImageV2,
  type ChatInputVideoV2,
  type ChatSourceV2,
} from '../../services/teacher/chatV2';
import { decodeDisplayText } from '../../services/teacher/displayText.helpers';
import { resolveSpeechInputError } from '../../services/teacher/speechInput';
import { extractGeneratedFilesFromV2Response, restoreGeneratedFilesFromConversationDetail } from '../../services/teacher/chatV2.helpers';
import ReactMarkdown from 'react-markdown';
import { loadPreviewMediaUrl, revokePreviewMediaUrl, type RAGSource } from '../../services/rag';
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
}

interface ChatPanelProps {
  courseId?: string;
}

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

const ChatPanel: React.FC<ChatPanelProps> = ({ courseId }) => {
  const {
    messages,
    addMessage,
    setMessages,
    updateLastMessage,
    selectedDocs,
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

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [historyList, setHistoryList] = useState<ConversationListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loadingConversationId, setLoadingConversationId] = useState<string | null>(null);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPopoverOpen, setHistoryPopoverOpen] = useState(false);
  const [workflowType, setWorkflowType] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
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

  useEffect(() => {
    const init = async () => {
      setHistoryLoading(true);
      try {
        const result = await listChatConversations();
        const list = result.conversations || [];
        setHistoryList(list);

        const storedConversationId = String(currentConversationId || '').trim();
        const storedConversationExists = storedConversationId
          ? list.some((item) => item.conversation_id === storedConversationId)
          : false;

        if (storedConversationExists) {
          await loadConversation(storedConversationId, false);
        } else if (list.length > 0) {
          setCurrentConversationId(list[0].conversation_id);
          await loadConversation(list[0].conversation_id, false);
        }
      } catch (error) {
        console.error('加载历史对话失败:', error);
      } finally {
        setHistoryLoading(false);
      }
    };

    void init();
  }, []);

  const refreshHistoryList = async () => {
    try {
      const result = await listChatConversations();
      setHistoryList(result.conversations || []);
    } catch (error) {
      console.error('刷新历史对话失败:', error);
    }
  };

  const loadConversation = async (conversationId: string, showSuccess = true, silent = false) => {
    if (!silent) {
      setLoadingConversationId(conversationId);
    }
    try {
      const detail = await getChatConversationDetail(conversationId);
      const mapped: Message[] = (detail.history || []).map((msg: any) => ({
        user: msg.role === 'assistant' ? 'AI' : 'You',
        text: msg.content || '',
        sources: (msg.sources || []) as any[],
        inputImages: (msg.input_images || []) as ChatInputImageV2[],
        inputVideos: (msg.input_videos || []) as ChatInputVideoV2[],
      }));
      const detailWorkflowState = detail?.state?.workflow_state;
      const nextWorkflowType = String((detailWorkflowState as any)?.workflow_type || '').trim();
      const nextWorkflowStatus = String((detailWorkflowState as any)?.status || '').trim();

      setMessages(mapped);
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
      const payload = buildChatReplyPayload({
        question: userMessage.text,
        conversationId: currentConversationId,
        courseId,
        allowRag,
        allowWeb,
        selectedDocIds: selectedDocs,
        inputImages,
        inputVideos,
        artifactReference,
        conversationReference,
      });
      let streamedText = '';
      let response: ChatResponseV2 | null = null;
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
        onError: (error) => {
          throw error;
        },
      });
      if (!response) {
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

      const hasFinalReport = generatedFiles.some((file) => file.meta?.kind === 'final_report');
      const replyText = hasFinalReport ? '已生成，请在右侧查看。' : String(response.message?.content || '');

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
    if (!currentConversationId || workflowType !== 'ppt' || workflowStatus !== 'running') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadConversation(currentConversationId, false, true);
    }, 3000);

    return () => window.clearInterval(timer);
  }, [currentConversationId, workflowStatus, workflowType]);

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

  const visibleHistoryList = useMemo(() => {
    return historyExpanded ? historyList : historyList.slice(0, 7);
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

          {!historyExpanded && historyList.length > 7 && (
            <div className="chat-panel__history-more">
              <Button
                type="text"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setHistoryExpanded(true);
                }}
              >
                ...
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
          <div className="chat-panel__subtitle">当前知识库：总课程知识库</div>
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
            renderItem={(item, index) => (
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
                      {item.user === 'AI' ? (
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => (
                              <p className="chat-panel__markdown-paragraph">
                                {children}
                              </p>
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

                    {item.user === 'AI' && item.sources && item.sources.length > 0 && (
                    <div className="chat-panel__sources">
                      <Space wrap size={[0, 8]}>
                        {item.sources.map((source, i) => {
                          const isImage = String((source as any)?.modality || (source as any)?.metadata?.modality || '').toLowerCase() === 'image';
                          const isVideo = String((source as any)?.modality || (source as any)?.metadata?.modality || '').toLowerCase() === 'video';
                          const imageUrl = ((source as any)?.image_url || (source as any)?.metadata?.image_url) as string | undefined;
                          const videoUrl = ((source as any)?.video_url || (source as any)?.metadata?.video_url) as string | undefined;
                          const resolvedImageUrl = imageUrl ? sourceImageUrls[imageUrl] : '';
                          const resolvedVideoUrl = videoUrl ? sourceVideoUrls[videoUrl] : '';
                          const sourceName = getDisplayLabel(source?.source, `来源 ${i + 1}`);
                          const imageTitle = getDisplayLabel((source as any)?.image_name, sourceName);
                          const videoTitle = getDisplayLabel((source as any)?.metadata?.title, sourceName);
                          return (
                            <Tooltip
                              key={i}
                              title={source?.content ? (`引用片段：${String(source.content).substring(0, 100)}...`) : '暂无引用片段'}
                            >
                              <Tag
                                icon={<SnippetsOutlined />}
                                color={isVideo ? 'green' : isImage ? 'purple' : 'blue'}
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  handleSourceClick(source);
                                }}
                                onMouseDown={(e) => {
                                  e.preventDefault();
                                }}
                                style={{ cursor: 'pointer', userSelect: 'none' }}
                              >
                                {isVideo ? `视频 · ${sourceName}` : isImage ? `图片 · ${sourceName}` : sourceName}
                              </Tag>
                              {isImage && imageUrl && (
                                <div style={{ marginTop: 8, marginBottom: 4 }}>
                                  {resolvedImageUrl ? (
                                    <img
                                      src={resolvedImageUrl}
                                      alt={String((source as any)?.image_alt || imageTitle || 'image preview')}
                                      style={{ maxWidth: 220, maxHeight: 140, borderRadius: 8, border: '1px solid #eee' }}
                                    />
                                  ) : (
                                    <div
                                      style={{
                                        width: 220,
                                        height: 140,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        background: 'rgba(0, 0, 0, 0.04)',
                                        color: '#666',
                                        fontSize: 12,
                                        borderRadius: 8,
                                        border: '1px solid #eee',
                                      }}
                                    >
                                      图片加载中...
                                    </div>
                                  )}
                                </div>
                              )}
                              {isVideo && videoUrl && (
                                <div
                                  style={{
                                    marginTop: 8,
                                    width: 240,
                                    borderRadius: 10,
                                    overflow: 'hidden',
                                    border: '1px solid #eee',
                                    background: '#fff',
                                  }}
                                >
                                  {resolvedVideoUrl ? (
                                    <video controls preload="metadata" src={resolvedVideoUrl} style={{ width: '100%', display: 'block' }} />
                                  ) : (
                                    <div
                                      style={{
                                        height: 140,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        background: 'rgba(0, 0, 0, 0.04)',
                                        color: '#666',
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
                                      color: '#666',
                                      whiteSpace: 'nowrap',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                    }}
                                    title={videoTitle}
                                  >
                                    {videoTitle}
                                  </div>
                                </div>
                              )}
                            </Tooltip>
                          );
                        })}
                      </Space>
                    </div>
                  )}
                  </div>
                </div>
              </List.Item>
            )}
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
              <div>
                <Text type="secondary">
                  可直接围绕这个文件提问，也可以说“修改第 3 页”或“重写结论”。
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
                <Button
                  size="large"
                  className={`chat-panel__composer-mode-button ${allowRag ? 'chat-panel__composer-mode-button--active' : ''}`}
                  onClick={() => setAllowRag(!allowRag)}
                  disabled={isLoading}
                >
                  RAG检索
                </Button>
                <Button
                  size="large"
                  className={`chat-panel__composer-mode-button ${allowWeb ? 'chat-panel__composer-mode-button--active' : ''}`}
                  onClick={() => setAllowWeb(!allowWeb)}
                  disabled={isLoading}
                >
                  Web搜索
                </Button>
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




