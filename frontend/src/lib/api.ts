import type { DocumentTypeInfo, PipelineStage } from '../types';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail.detail === 'string') return detail.detail;
  } catch {
    // αγνόησε — θα επιστραφεί γενικό μήνυμα
  }
  return `Σφάλμα διακομιστή (${res.status})`;
}

export async function fetchDocumentTypes(): Promise<DocumentTypeInfo[]> {
  const res = await fetch(`${API_URL}/api/document-types`);
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}

export async function extractFile(file: File): Promise<{ text: string; characters: number }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_URL}/api/extract`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await readErrorDetail(res));
  return res.json();
}

export async function* analyzeStream(
  text: string,
  context: string | null,
  docTypeHint: string | null,
): AsyncGenerator<PipelineStage> {
  const res = await fetch(`${API_URL}/api/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, context, doc_type_hint: docTypeHint }),
  });
  if (!res.ok || !res.body) throw new Error(await readErrorDetail(res));

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
