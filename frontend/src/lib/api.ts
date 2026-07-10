import axios from "axios";

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120000, // 2 minutes for ML operations
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for auth token
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("auth_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("auth_token");
      }
    }
    return Promise.reject(error);
  }
);

// ─── OCR ────────────────────────────────────────────────────────────────────

export interface OCRResponse {
  document_id: string;   // MongoDB ObjectId string
  document_type: string;
  summary: string;
  metadata: Record<string, string | string[]>;
  blockchain: {
    document_hash: string;
    transaction_hash: string;
    registered: boolean;
  };
  original_image_url?: string;
  preprocessed_image_url?: string;
  // Legacy fields (kept for backward compatibility with store)
  id?: string;
  raw_text?: string;
  clean_text?: string;
  fields?: Record<string, string | string[]>;
  boxes?: Array<{ left: number; top: number; width: number; height: number; conf: number; text: string }>;
  lang?: string;
  lang_detected?: string;
}

export async function scanDocument(file: File, lang = "eng"): Promise<OCRResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("lang", lang);

  const response = await api.post<OCRResponse>("/api/ocr/scan", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

// ─── AI / NLP ────────────────────────────────────────────────────────────────

export interface AIResponse<T> {
  ok: boolean;
  data: T;
  cached: boolean;
  error?: string;
}

export interface ClassificationData {
  doc_type: string;
  confidence: number;
  all_scores: Record<string, number>;
  processed_at?: string;
  model?: string;
  lang?: string;
}

export interface EntityData {
  persons: string[];
  organisations: string[];
  dates: string[];
  money: string[];
  locations: string[];
  case_numbers: string[];
  raw_entities: Array<{ text: string; label: string; score: number; start: number; end: number }>;
  clauses?: {
    clauses_found: string[];
    clause_spans: Array<{ clause: string; text_snippet: string; start_char: number }>;
  };
}

export interface SummarizationData {
  summary: string;
  word_count: number;
  compression_ratio: number;
  processed_at?: string;
}

export interface RiskFlag {
  category: string;
  description: string;
  severity: "low" | "medium" | "high";
}

export interface RiskData {
  risk_level: "low" | "medium" | "high";
  flags: RiskFlag[];
  score: number;
  processed_at?: string;
}

export interface ChunkResult {
  chunk_text: string;
  doc_id: string;
  chunk_index: number;
  score: number;
}

export interface RAGResult {
  answer: string;
  source_chunks: ChunkResult[];
  model_used: string;
}

export async function classifyDocument(docId: string, force = false): Promise<AIResponse<ClassificationData>> {
  const res = await api.post<AIResponse<ClassificationData>>("/api/ai/classify", { doc_id: docId, force });
  return res.data;
}

export async function extractEntities(docId: string, force = false): Promise<AIResponse<EntityData>> {
  const res = await api.post<AIResponse<EntityData>>("/api/ai/extract", { doc_id: docId, force });
  return res.data;
}

export async function summarizeDocument(docId: string, force = false): Promise<AIResponse<SummarizationData>> {
  const res = await api.post<AIResponse<SummarizationData>>("/api/ai/summarize", { doc_id: docId, force });
  return res.data;
}

export async function checkRisk(docId: string, force = false): Promise<AIResponse<RiskData>> {
  const res = await api.post<AIResponse<RiskData>>("/api/ai/risk-check", { doc_id: docId, force });
  return res.data;
}

export async function semanticSearch(docId: string, query: string, topK = 4): Promise<AIResponse<ChunkResult[]>> {
  const res = await api.post<AIResponse<ChunkResult[]>>("/api/ai/search", { doc_id: docId, query, top_k: topK });
  return res.data;
}

export async function crossSearch(query: string, docIds?: string[]): Promise<AIResponse<ChunkResult[]>> {
  const res = await api.post<AIResponse<ChunkResult[]>>("/api/ai/cross-search", { query, doc_ids: docIds });
  return res.data;
}

export async function chatWithDocument(docId: string, question: string): Promise<AIResponse<RAGResult>> {
  const res = await api.post<AIResponse<RAGResult>>("/api/ai/chat", { doc_id: docId, question });
  return res.data;
}

// ─── OCR Documents (list / get / delete) ─────────────────────────────────────

export interface OcrDocumentSummary {
  id: string;
  filename: string;
  clean_text?: string;
  fields: Record<string, string | string[]>;
  lang: string;
  lang_detected: string;
  created_at: string;
  original_image_url?: string;
  preprocessed_image_url?: string;
  nlp?: {
    classification?: ClassificationData;
    entities?: EntityData;
    summary?: SummarizationData;
    risk?: RiskData;
  };
}

export interface OcrDocumentsListResponse {
  ok: boolean;
  data: OcrDocumentSummary[];
  total: number;
  skip: number;
  limit: number;
}

export async function listOcrDocuments(params?: {
  limit?: number;
  skip?: number;
  lang?: string;
}): Promise<OcrDocumentsListResponse> {
  const res = await api.get<OcrDocumentsListResponse>("/api/ocr/documents", { params });
  return res.data;
}

export async function getOcrDocument(docId: string): Promise<AIResponse<OcrDocumentSummary>> {
  const res = await api.get<AIResponse<OcrDocumentSummary>>(`/api/ocr/documents/${docId}`);
  return res.data;
}

export async function deleteOcrDocument(docId: string): Promise<{ ok: boolean; deleted: string }> {
  const res = await api.delete<{ ok: boolean; deleted: string }>(`/api/ocr/documents/${docId}`);
  return res.data;
}

// ─── Generated Documents ─────────────────────────────────────────────────────

export interface GenerateDocRequest {
  doc_type: string;
  fields: Record<string, string>;
}

export interface GenerateDocResponse {
  id: string;
  content: string;
  file_url: string;
}

export interface GeneratedDoc {
  id: string;
  doc_type: string;
  fields: Record<string, string>;
  content?: string;
  file_url: string;
  created_at: string;
}

export interface DocType {
  key: string;
  label: string;
  required_fields: string[];
}

export async function generateDocument(payload: GenerateDocRequest): Promise<GenerateDocResponse> {
  const res = await api.post<GenerateDocResponse>("/api/documents/create", payload);
  return res.data;
}

export async function listGeneratedDocuments(params?: {
  limit?: number;
  skip?: number;
  doc_type?: string;
}): Promise<{ ok: boolean; data: GeneratedDoc[]; total: number }> {
  const res = await api.get<{ ok: boolean; data: GeneratedDoc[]; total: number }>("/api/documents", { params });
  return res.data;
}

export async function getGeneratedDocument(docId: string): Promise<AIResponse<GeneratedDoc>> {
  const res = await api.get<AIResponse<GeneratedDoc>>(`/api/documents/${docId}`);
  return res.data;
}

export async function deleteGeneratedDocument(docId: string): Promise<{ ok: boolean; deleted: string }> {
  const res = await api.delete<{ ok: boolean; deleted: string }>(`/api/documents/${docId}`);
  return res.data;
}

export async function listDocTypes(): Promise<{ ok: boolean; data: DocType[] }> {
  const res = await api.get<{ ok: boolean; data: DocType[] }>("/api/documents/types");
  return res.data;
}

// ─── Biometric Auth ───────────────────────────────────────────────────────────

export interface AuthUser {
  name: string;
  role: string;
  token: string;
  fingerprint_id?: number;
}

export interface DemoUser {
  name: string;
  role: string;
  fingerprint_id: number;
}

/** Authenticate by fingerprint ID — returns JWT */
export async function authenticateFingerprint(fingerprint_id: number): Promise<AuthUser> {
  const res = await api.post<AuthUser>("/api/biometric/authenticate", { fingerprint_id });
  return res.data;
}

/** Register a new user with a fingerprint ID */
export async function registerFingerprint(payload: {
  name: string;
  fingerprint_id: number;
  role: string;
}): Promise<{ user_id: string }> {
  const res = await api.post<{ user_id: string }>("/api/biometric/register", payload);
  return res.data;
}

/** Get demo users list */
export async function getDemoUsers(): Promise<DemoUser[]> {
  const res = await api.get<DemoUser[]>("/api/biometric/demo-users");
  return res.data;
}

/** Get current user profile from JWT */
export async function getUserProfile(): Promise<{ user_id: string; name: string; role: string }> {
  const res = await api.get<{ user_id: string; name: string; role: string }>("/api/biometric/profile");
  return res.data;
}

// ─── Blockchain ───────────────────────────────────────────────────────────────

export interface BlockchainRecord {
  document_id: string;
  document_hash: string;
  transaction_hash: string;
  registered: boolean;
  block_number?: number;
}

export interface VerifyResult {
  document_id: string;
  document_hash: string;
  status: "authentic" | "tampered";
}

export async function registerDocumentOnChain(
  document_id: string,
  document_hash: string
): Promise<BlockchainRecord> {
  const res = await api.post<BlockchainRecord>("/api/blockchain/register", {
    document_id,
    document_hash,
  });
  return res.data;
}

export async function verifyDocumentOnChain(
  document_id: string,
  document_hash?: string
): Promise<VerifyResult> {
  const res = await api.post<VerifyResult>("/api/blockchain/verify", {
    document_id,
    ...(document_hash && { document_hash }),
  });
  return res.data;
}

export async function getBlockchainRecord(doc_id: string): Promise<BlockchainRecord> {
  const res = await api.get<BlockchainRecord>(`/api/blockchain/document/${doc_id}`);
  return res.data;
}

// ─── Auth helpers ─────────────────────────────────────────────────────────────

export function saveAuth(user: AuthUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem("auth_token", user.token);
  localStorage.setItem("auth_user", JSON.stringify({ name: user.name, role: user.role }));
}

export function getAuthUser(): { name: string; role: string } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("auth_user");
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("auth_token");
}

// ─── Face Recognition ─────────────────────────────────────────────────────────

export interface FaceAuthResponse {
  token: string;
  name: string;
  role: string;
  user_id: string;
}

export interface FaceStatusResponse {
  enrolled: boolean;
}

/** POST /api/face/authenticate — no auth token required */
export async function authenticateFace(imageBlob: Blob): Promise<FaceAuthResponse> {
  const formData = new FormData();
  formData.append("file", imageBlob, "face.jpg");
  const res = await api.post<FaceAuthResponse>("/api/face/authenticate", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

/** POST /api/face/enroll — requires Bearer token; JWT attached automatically by interceptor */
export async function enrollFace(imageBlob: Blob): Promise<{ enrolled: boolean; user_id: string }> {
  const formData = new FormData();
  formData.append("file", imageBlob, "face.jpg");
  const res = await api.post<{ enrolled: boolean; user_id: string }>(
    "/api/face/enroll",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data;
}

/** GET /api/face/status — requires Bearer token; JWT attached automatically by interceptor */
export async function getFaceStatus(): Promise<FaceStatusResponse> {
  const res = await api.get<FaceStatusResponse>("/api/face/status");
  return res.data;
}
