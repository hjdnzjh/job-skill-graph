/**
 * API service layer — connects frontend to FastAPI backend.
 * All calls proxy through Vite dev server or served from same origin.
 */

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Overview ──
export interface OverviewData {
  job_trends: { month: string; timestamp: string; count: number; total_nodes: number; total_edges: number }[];
  skill_trends: { name: string; old_demand: number; new_demand: number; growth: number; direction: string }[];
  status_distribution: { name: string; value: number }[];
  insights: { category: string; title: string; description: string }[];
}
export const getOverview = () => request<OverviewData>('/reports/overview');

// ── Skills ──
export interface SkillRank { skill: string; category: string; demand: number }
export const getSkillRanking = (limit = 30) => request<{ skills: SkillRank[] }>(`/skills/ranking?limit=${limit}`);

export interface SkillNode { name: string; category: string; demand: number }
export interface SkillEdge { source: string; target: string; weight: number }
export const getSkillNetwork = (limit = 50) => request<{ nodes: SkillNode[]; edges: SkillEdge[] }>(`/skills/network?limit=${limit}`);

// ── Graph / Node Admin ──
export interface GraphNode { label: string; name: string; category: string; node_id: number }
export interface GraphEdge { source_label: string; source_name: string; rel_type: string; target_label: string; target_name: string }
export const getGraphExport = (limit = 5000) => request<{ nodes: GraphNode[]; edges: GraphEdge[]; node_count: number; edge_count: number; has_more: boolean }>(`/graph/export?limit=${limit}`);

// ── Job Titles ──
export const getJobTitles = () => request<{ titles: string[] }>('/job-titles');

// ── Jobs / Review ──
export interface PendingJob { title: string; category: string; source: string; status: string; date: string; type: string; description?: string; confidence?: number }
export const getPendingJobs = (params?: { status?: string; search?: string; limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.status) q.set('status', params.status);
  if (params?.search) q.set('search', params.search);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return request<{ jobs: PendingJob[]; total: number }>(`/jobs/pending?${q}`);
};

export interface JobDetail { title: string; type: string; status: string; description: string; job_count: number; required_skills: { name: string; category?: string; demand?: number }[] }
export const getJobDetail = (title: string) => request<JobDetail>(`/jobs/${encodeURIComponent(title)}`);

// ── Matching ──
export interface MatchRequest { skills: string[]; target: string }
export const postMatch = (body: MatchRequest) => request<any>('/match', { method: 'POST', body: JSON.stringify(body) });

export interface RecommendRequest { skills: string[]; top_n?: number }
export const postRecommend = (body: RecommendRequest) => request<any>('/recommend', { method: 'POST', body: JSON.stringify(body) });

// ── Resume ──
export const uploadResume = async (file: File) => {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/resume/upload`, { method: 'POST', body: form });
  if (!res.ok) throw new Error((await res.json()).error || 'Upload failed');
  return res.json();
};

export const evaluateResume = (fileId: string, targetTitle: string) =>
  request<any>('/resume/evaluate', {
    method: 'POST',
    body: JSON.stringify({ file_id: fileId, target_title: targetTitle }),
  });

// ── Evolution ──
export const getEvolutionTimeline = () => request<{ timeline: any[] }>('/evolution/timeline');

// ── RAG ──
export const queryRag = (question: string, topK = 5) =>
  request<any>('/rag/query', {
    method: 'POST',
    body: JSON.stringify({ question, top_k: topK }),
  });
