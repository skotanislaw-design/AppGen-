import { useRef, useState } from 'react';
import { extractFile } from '../lib/api';
import type { DocumentTypeInfo } from '../types';

interface DocumentInputProps {
  documentTypes: DocumentTypeInfo[];
  disabled: boolean;
  onSubmit: (text: string, context: string | null, docTypeHint: string | null) => void;
}

export const DocumentInput: React.FC<DocumentInputProps> = ({
  documentTypes,
  disabled,
  onSubmit,
}) => {
  const [text, setText] = useState('');
  const [context, setContext] = useState('');
  const [docTypeHint, setDocTypeHint] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setFileError(null);
    setExtracting(true);
    try {
      const result = await extractFile(file);
      setText(result.text);
    } catch (err) {
      setFileError(err instanceof Error ? err.message : 'Αποτυχία ανάγνωσης αρχείου.');
    } finally {
      setExtracting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const canSubmit = text.trim().length >= 200 && !disabled && !extracting;

  return (
    <div className="glass-card flex flex-col gap-5 p-6 md:p-8">
      <div>
        <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gold">
          Κείμενο δικογράφου
        </label>
        <textarea
          className="input-dark min-h-[280px] resize-y font-body text-sm leading-relaxed"
          placeholder="Επικολλήστε εδώ το πλήρες κείμενο του δικογράφου ή ανεβάστε αρχείο (PDF, DOCX, TXT)…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
        />
        <div className="mt-2 flex items-center justify-between text-xs text-silver">
          <span>{text.length.toLocaleString('el-GR')} χαρακτήρες</span>
          <button
            type="button"
            className="btn-ghost !px-4 !py-2"
            onClick={() => fileRef.current?.click()}
            disabled={disabled || extracting}
          >
            {extracting ? 'Ανάγνωση…' : 'Μεταφόρτωση αρχείου'}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
            }}
          />
        </div>
        {fileError && <p className="mt-2 text-sm text-red-300">{fileError}</p>}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gold">
            Πλαίσιο / σκοπός (προαιρετικό)
          </label>
          <textarea
            className="input-dark min-h-[80px] resize-y text-sm"
            placeholder="π.χ. Επείγει η κατάθεση· ο αντίδικος έχει ήδη επισπεύσει εκτέλεση…"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            disabled={disabled}
          />
        </div>
        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gold">
            Είδος εγγράφου (προαιρετικό)
          </label>
          <select
            className="input-dark text-sm"
            value={docTypeHint}
            onChange={(e) => setDocTypeHint(e.target.value)}
            disabled={disabled}
          >
            <option value="">Αυτόματη αναγνώριση</option>
            {documentTypes
              .filter((t) => t.key !== 'generic')
              .map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
          </select>
          <p className="mt-2 text-xs leading-relaxed text-silver">
            Αν δεν επιλέξετε είδος, ο έλεγχος ξεκινά με αυτόματη ταξινόμηση του εγγράφου.
          </p>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          className="btn-gold"
          disabled={!canSubmit}
          onClick={() => onSubmit(text.trim(), context.trim() || null, docTypeHint || null)}
        >
          Έναρξη ελέγχου
        </button>
      </div>
    </div>
  );
};
