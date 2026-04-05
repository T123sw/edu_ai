import { create } from 'zustand';
import type { RAGSource } from '../../services/rag';
import type { StatusCardV2 } from '../../services/teacher/chatV2';

// Define types for our state
interface Document {
  id: string;
  name: string;
  type: 'file' | 'web';
}

interface ChatMessage {
  user: 'You' | 'AI';
  text: string;
  sources?: RAGSource[];
  status?: 'thinking' | 'tool' | 'streaming' | 'done' | 'error';
  statusText?: string;
}

export interface GeneratedFile {
  id: string;
  name: string;
  type: 'report' | 'quiz' | 'blog' | 'lesson_plan' | 'audio' | 'graph' | 'video' | 'flashcard';
  content?: any; // Content can be string, object, or any other type
}

export interface HighlightRequest {
  filePath: string;
  source: RAGSource;
  requestId: string;
}

// Define the state structure and actions
interface AppState {
  documents: Document[];
  selectedDocs: string[];
  allowRag: boolean;
  allowWeb: boolean;
  messages: ChatMessage[];
  currentConversationId: string | null;
  generatedFiles: GeneratedFile[];
  viewingFile: GeneratedFile | null;
  highlightRequest: HighlightRequest | null;
  queuedMessage: string | null;
  statusCard: StatusCardV2 | null;
  addDocument: (doc: Document) => void;
  removeDocument: (id: string) => void;
  setSelectedDocs: (ids: string[]) => void;
  setAllowRag: (allow: boolean) => void;
  setAllowWeb: (allow: boolean) => void;
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  updateLastMessage: (message: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  setCurrentConversationId: (conversationId: string | null) => void;
  addGeneratedFile: (file: GeneratedFile) => void;
  removeGeneratedFile: (id: string) => void;
  setViewingFile: (file: GeneratedFile | null) => void;
  setHighlightRequest: (req: Omit<HighlightRequest, 'requestId'> | null) => void;
  setQueuedMessage: (message: string | null) => void;
  setStatusCard: (card: StatusCardV2 | null) => void;
}

// Initial mock data
const initialDocuments: Document[] = [];
const initialMessages: ChatMessage[] = [];
const initialGeneratedFiles: GeneratedFile[] = [];

// Create the store
export const useStore = create<AppState>((set) => ({
  documents: initialDocuments,
  selectedDocs: [],
  allowRag: false,
  allowWeb: false,
  messages: initialMessages,
  currentConversationId: null,
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
  clearMessages: () => set({ messages: [] }),
  setCurrentConversationId: (conversationId) => set({ currentConversationId: conversationId }),
  addGeneratedFile: (file) => set((state) => ({ generatedFiles: [...state.generatedFiles, file] })),
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
}));
