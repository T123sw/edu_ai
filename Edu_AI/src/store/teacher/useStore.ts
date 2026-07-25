import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { RAGSource } from '../../services/rag';
import type {
  ChatArtifactReference,
  ChatConversationReference,
  ChatInputImageV2,
  ChatInputVideoV2,
  StatusCardV2,
} from '../../services/teacher/chatV2';
import {
  clearConversationGeneratedFiles,
  pinGeneratedFileInList,
  replaceCourseMaterialGeneratedFiles,
  replaceConversationGeneratedFiles,
  upsertGeneratedFileInList,
} from '../../services/teacher/materials.helpers';

interface Document {
  id: string;
  name: string;
  type: 'file' | 'web';
}

interface ChatMessage {
  id?: string;
  user: 'You' | 'AI';
  text: string;
  sources?: RAGSource[];
  inputImages?: ChatInputImageV2[];
  inputVideos?: ChatInputVideoV2[];
  status?: 'thinking' | 'tool' | 'streaming' | 'done' | 'error';
  statusText?: string;
  /** ReAct agent execution timeline. Set by ChatPanel during streaming. */
  agentActivity?: unknown;
}

export interface GeneratedFile {
  id: string;
  name: string;
  type: 'report' | 'ppt' | 'quiz' | 'blog' | 'lesson_plan' | 'audio' | 'graph' | 'video' | 'flashcard' | 'game';
  content?: any;
  meta?: Record<string, unknown>;
}

export interface HighlightRequest {
  filePath: string;
  source: RAGSource;
  requestId: string;
}

type ArtifactReference = ChatArtifactReference;
type ConversationReference = ChatConversationReference;

interface AppState {
  documents: Document[];
  selectedDocs: string[];
  scopedSourceDocIds: string[];
  allowRag: boolean;
  allowWeb: boolean;
  messages: ChatMessage[];
  currentConversationId: string | null;
  artifactReference: ArtifactReference | null;
  conversationReference: ConversationReference | null;
  generatedFiles: GeneratedFile[];
  viewingFile: GeneratedFile | null;
  highlightRequest: HighlightRequest | null;
  queuedMessage: string | null;
  statusCard: StatusCardV2 | null;
  addDocument: (doc: Document) => void;
  removeDocument: (id: string) => void;
  setSelectedDocs: (ids: string[]) => void;
  setScopedSourceDocIds: (ids: string[]) => void;
  setAllowRag: (allow: boolean) => void;
  setAllowWeb: (allow: boolean) => void;
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  updateLastMessage: (message: Partial<ChatMessage>) => void;
  updateMessageById: (id: string, message: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  setCurrentConversationId: (conversationId: string | null) => void;
  setArtifactReference: (reference: ArtifactReference | null) => void;
  clearArtifactReference: () => void;
  setConversationReference: (reference: ConversationReference | null) => void;
  clearConversationReference: () => void;
  addGeneratedFile: (file: GeneratedFile) => void;
  pinGeneratedFile: (id: string, isPinned: boolean, pinnedAt?: string) => void;
  replaceConversationGeneratedFiles: (files: GeneratedFile[]) => void;
  replaceCourseMaterialGeneratedFiles: (files: GeneratedFile[]) => void;
  clearConversationGeneratedFiles: () => void;
  removeGeneratedFilesByConversationId: (conversationId: string) => void;
  removeGeneratedFile: (id: string) => void;
  setViewingFile: (file: GeneratedFile | null) => void;
  setHighlightRequest: (req: Omit<HighlightRequest, 'requestId'> | null) => void;
  setQueuedMessage: (message: string | null) => void;
  setStatusCard: (card: StatusCardV2 | null) => void;
}

const initialDocuments: Document[] = [];
const initialMessages: ChatMessage[] = [];
const initialGeneratedFiles: GeneratedFile[] = [];

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      documents: initialDocuments,
      selectedDocs: [],
      scopedSourceDocIds: [],
      allowRag: false,
      allowWeb: false,
      messages: initialMessages,
      currentConversationId: null,
      artifactReference: null,
      conversationReference: null,
      generatedFiles: initialGeneratedFiles,
      viewingFile: null,
      highlightRequest: null,
      queuedMessage: null,
      statusCard: null,

      addDocument: (doc) => set((state) => ({ documents: [...state.documents, doc] })),
      removeDocument: (id) =>
        set((state) => ({
          documents: state.documents.filter((doc) => doc.id !== id),
          selectedDocs: state.selectedDocs.filter((docId) => docId !== id),
        })),
      setSelectedDocs: (ids) => set({ selectedDocs: ids }),
      setScopedSourceDocIds: (ids) => set({ scopedSourceDocIds: ids }),
      setAllowRag: (allow) => set({ allowRag: allow }),
      setAllowWeb: (allow) => set({ allowWeb: allow }),
      addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
      setMessages: (messages) => set({ messages }),
      updateLastMessage: (message) =>
        set((state) => {
          if (state.messages.length === 0) return state;
          const next = [...state.messages];
          const last = next[next.length - 1];
          const updated = { ...last, ...message };
          const keys = new Set([...Object.keys(last), ...Object.keys(updated)]);
          for (const key of keys) {
            if ((last as any)[key] !== (updated as any)[key]) {
              next[next.length - 1] = updated;
              return { messages: next };
            }
          }
          return state;
        }),
      updateMessageById: (id, message) =>
        set((state) => {
          const idx = [...state.messages].reduceRight((found, _, i) =>
            found === -1 && state.messages[i].id === id ? i : found, -1);
          if (idx === -1) return state;
          const next = [...state.messages];
          next[idx] = { ...next[idx], ...message };
          return { messages: next };
        }),
      clearMessages: () => set({ messages: [] }),
      setCurrentConversationId: (conversationId) => set({ currentConversationId: conversationId }),
      setArtifactReference: (reference) => set({ artifactReference: reference }),
      clearArtifactReference: () => set({ artifactReference: null }),
      setConversationReference: (reference) => set({ conversationReference: reference }),
      clearConversationReference: () => set({ conversationReference: null }),
      addGeneratedFile: (file) =>
        set((state) => {
          const nextFiles = upsertGeneratedFileInList(state.generatedFiles, file);
          return {
            generatedFiles: nextFiles,
            viewingFile: state.viewingFile?.id === file.id ? file : state.viewingFile,
          };
        }),
      pinGeneratedFile: (id, isPinned, pinnedAt) =>
        set((state) => {
          const nextFiles = pinGeneratedFileInList(state.generatedFiles, id, isPinned, pinnedAt);
          const nextViewingFile =
            state.viewingFile?.id === id
              ? nextFiles.find((file) => file.id === id) || null
              : state.viewingFile;
          return {
            generatedFiles: nextFiles,
            viewingFile: nextViewingFile,
          };
        }),
      replaceConversationGeneratedFiles: (files) =>
        set((state) => {
          const nextFiles = replaceConversationGeneratedFiles(state.generatedFiles, files);
          const currentViewingId = String(state.viewingFile?.id || '').trim();
          const nextViewingFile = currentViewingId
            ? nextFiles.find((file) => file.id === currentViewingId) || null
            : null;
          return {
            generatedFiles: nextFiles,
            viewingFile: nextViewingFile,
          };
        }),
      replaceCourseMaterialGeneratedFiles: (files) =>
        set((state) => {
          const nextFiles = replaceCourseMaterialGeneratedFiles(state.generatedFiles, files);
          const currentViewingId = String(state.viewingFile?.id || '').trim();
          const nextViewingFile = currentViewingId
            ? nextFiles.find((file) => file.id === currentViewingId) || null
            : null;
          return {
            generatedFiles: nextFiles,
            viewingFile: nextViewingFile,
          };
        }),
      clearConversationGeneratedFiles: () =>
        set((state) => {
          const nextFiles = clearConversationGeneratedFiles(state.generatedFiles);
          const nextViewingFile =
            state.viewingFile && String(state.viewingFile.meta?.origin || '').trim() !== 'course_material'
              ? null
              : state.viewingFile;
          return {
            generatedFiles: nextFiles,
            viewingFile: nextViewingFile,
          };
        }),
      removeGeneratedFilesByConversationId: (conversationId) =>
        set((state) => {
          const nextFiles = state.generatedFiles.filter(
            (file) =>
              String(file.meta?.conversationId || '') !== conversationId
              || String(file.meta?.origin || '').trim() === 'course_material',
          );
          return {
            generatedFiles: nextFiles,
            viewingFile:
              String(state.viewingFile?.meta?.conversationId || '') === conversationId
              && String(state.viewingFile?.meta?.origin || '').trim() !== 'course_material'
                ? null
                : state.viewingFile,
          };
        }),
      removeGeneratedFile: (id) =>
        set((state) => ({
          generatedFiles: state.generatedFiles.filter((file) => file.id !== id),
          viewingFile: state.viewingFile?.id === id ? null : state.viewingFile,
        })),
      setViewingFile: (file) => set({ viewingFile: file }),

      setHighlightRequest: (req) => {
        if (!req) {
          set({ highlightRequest: null });
          return;
        }
        set({
          highlightRequest: {
            ...req,
            requestId: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
          },
        });
      },

      setQueuedMessage: (message) => set({ queuedMessage: message }),
      setStatusCard: (card) => set({ statusCard: card }),
    }),
    {
      name: 'edu-ai-teacher-store',
      storage: createJSONStorage(() => window.localStorage),
      partialize: (state) => ({
        currentConversationId: state.currentConversationId,
      }),
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...(persistedState as Partial<AppState>),
        generatedFiles: currentState.generatedFiles,
        viewingFile: currentState.viewingFile,
      }),
    },
  ),
);
