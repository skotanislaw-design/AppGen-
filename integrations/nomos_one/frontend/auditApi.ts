// Nomos One — API layer του module ελέγχου δικογράφων.
//
// Χρησιμοποιεί το JWT του LPMS (localStorage 'access_token', ίδια σύμβαση με
// τον axios interceptor του Nomos One) και μιλά στα endpoints /api/audit/*
// που εκθέτει ο create_audit_router πίσω από το require_role(...).
//
// Τοποθέτηση: src/features/audit/auditApi.ts (ή όπου κρατάτε τα feature APIs).

import type {
  AuditReport,
  DocumentTypeInfo,
  ExemplarDetail,
  ExemplarSummary,
  PipelineStage,
} from './types';

const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api/audit`;

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('access_token');
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function readError(res: Response): Promise<string> {
  if (res.status === 401) return 'Η συνεδρία έληξε — συνδεθείτε ξανά.';
  if (res.status === 403) return 'Δεν έχετε δικαίωμα πρόσβασης στον έλεγχο δικογράφων.';
  try {
    const body = await res.json();
    const d = body?.detail;
    if (typeof d === 'string') return d;
    if (d && typeof d.detail === 'string') return d.detail;
  } catch {
    /* αγνόησε */
  }
  return `Σφάλμα διακομιστή (${res.status})`;
}

export async function fetchDocumentTypes(): Promise<DocumentTypeInfo[]> {
  const res = await fetch(`${BASE}/document-types`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchExemplars(): Promise<ExemplarSummary[]> {
  const res = await fetch(`${BASE}/exemplars`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchExemplar(docType: string): Promise<ExemplarDetail> {
  const res = await fetch(`${BASE}/exemplars/${encodeURIComponent(docType)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function downloadExemplarDocx(docType: string): Promise<void> {
  const res = await fetch(`${BASE}/exemplars/${encodeURIComponent(docType)}/docx`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await readError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `skotanis-ypodeigma-${docType}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function extractFile(
  file: File,
): Promise<{ text: string; characters: number }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/extract`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function* analyzeStream(
  text: string,
  context: string | null,
  docTypeHint: string | null,
  matterId?: string | null,
): AsyncGenerator<PipelineStage> {
  const res = await fetch(`${BASE}/analyze/stream`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      text,
      context,
      doc_type_hint: docTypeHint,
      matter_id: matterId ?? null,
    }),
  });
  if (!res.ok || !res.body) throw new Error(await readError(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!chunk.startsWith('data:')) continue;
      const payload = chunk.slice(5).trim();
      if (!payload) continue;
      yield JSON.parse(payload) as PipelineStage;
    }
  }
}
