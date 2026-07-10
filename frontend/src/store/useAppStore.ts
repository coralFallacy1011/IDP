import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { OCRResponse, ClassificationData, EntityData, SummarizationData, RiskData } from "@/lib/api";

export interface Document {
  id: string;
  filename: string;
  uploadDate: string;
  lang: string;
  lang_detected: string;
  status: "processed" | "analyzing" | "error";
  ocrData?: OCRResponse;
  classification?: ClassificationData;
  entities?: EntityData;
  summary?: SummarizationData;
  risk?: RiskData;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ chunk_text: string; doc_id: string; chunk_index: number; score: number }>;
  timestamp: Date;
}

interface AppState {
  // Documents
  documents: Document[];
  activeDocumentId: string | null;
  addDocument: (doc: Document) => void;
  updateDocument: (id: string, updates: Partial<Document>) => void;
  removeDocument: (id: string) => void;
  setActiveDocument: (id: string | null) => void;
  getActiveDocument: () => Document | undefined;

  // OCR
  ocrResult: OCRResponse | null;
  setOcrResult: (result: OCRResponse | null) => void;

  // Chat
  chatHistory: Record<string, ChatMessage[]>;
  addChatMessage: (docId: string, message: ChatMessage) => void;
  getChatHistory: (docId: string) => ChatMessage[];
  clearChatHistory: (docId: string) => void;

  // UI State
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  // Stats
  stats: {
    documentsProcessed: number;
    ocrAccuracy: number;
    analysesCompleted: number;
    generatedDocs: number;
  };
  incrementDocumentsProcessed: () => void;
  incrementAnalysesCompleted: () => void;
  incrementGeneratedDocs: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      documents: [],
      activeDocumentId: null,
      ocrResult: null,
      chatHistory: {},
      sidebarOpen: true,

      stats: {
        documentsProcessed: 1247,
        ocrAccuracy: 97.3,
        analysesCompleted: 891,
        generatedDocs: 342,
      },

      addDocument: (doc) =>
        set((state) => ({ documents: [doc, ...state.documents] })),

      updateDocument: (id, updates) =>
        set((state) => ({
          documents: state.documents.map((d) =>
            d.id === id ? { ...d, ...updates } : d
          ),
        })),

      removeDocument: (id) =>
        set((state) => ({
          documents: state.documents.filter((d) => d.id !== id),
          activeDocumentId: state.activeDocumentId === id ? null : state.activeDocumentId,
        })),

      setActiveDocument: (id) => set({ activeDocumentId: id }),

      getActiveDocument: () => {
        const { documents, activeDocumentId } = get();
        return documents.find((d) => d.id === activeDocumentId);
      },

      setOcrResult: (result) => set({ ocrResult: result }),

      addChatMessage: (docId, message) =>
        set((state) => ({
          chatHistory: {
            ...state.chatHistory,
            [docId]: [...(state.chatHistory[docId] || []), message],
          },
        })),

      getChatHistory: (docId) => get().chatHistory[docId] || [],

      clearChatHistory: (docId) =>
        set((state) => {
          const newHistory = { ...state.chatHistory };
          delete newHistory[docId];
          return { chatHistory: newHistory };
        }),

      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      incrementDocumentsProcessed: () =>
        set((state) => ({
          stats: { ...state.stats, documentsProcessed: state.stats.documentsProcessed + 1 },
        })),

      incrementAnalysesCompleted: () =>
        set((state) => ({
          stats: { ...state.stats, analysesCompleted: state.stats.analysesCompleted + 1 },
        })),

      incrementGeneratedDocs: () =>
        set((state) => ({
          stats: { ...state.stats, generatedDocs: state.stats.generatedDocs + 1 },
        })),
    }),
    {
      name: "legal-idp-storage",
      partialize: (state) => ({
        documents: state.documents,
        activeDocumentId: state.activeDocumentId,
        chatHistory: state.chatHistory,
        stats: state.stats,
      }),
    }
  )
);
