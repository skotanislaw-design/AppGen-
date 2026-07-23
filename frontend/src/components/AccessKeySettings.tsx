import { useState } from 'react';
import { getApiKey, setApiKey } from '../lib/api';

export const AccessKeySettings: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(getApiKey());
  const [saved, setSaved] = useState(false);
  const hasKey = getApiKey().length > 0;

  const save = () => {
    setApiKey(value);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-md border border-gold/25 bg-white/5 px-3 py-1.5 text-xs text-silver transition hover:text-white"
        title="Κλειδί πρόσβασης"
      >
        <span
          className={`inline-block h-2 w-2 rounded-full ${hasKey ? 'bg-emerald-400' : 'bg-silver/50'}`}
        />
        Κλειδί πρόσβασης
      </button>

      {open && (
        <div className="absolute right-0 z-10 mt-2 w-80 rounded-lg border border-gold/25 bg-navy-mid p-4 text-left shadow-2xl">
          <p className="mb-2 text-xs leading-relaxed text-silver-light">
            Αν ο διακομιστής προστατεύεται με κλειδί (NOMOS_AUDIT_API_KEY), εισάγετέ το
            εδώ. Αποθηκεύεται τοπικά στον περιηγητή σας και αποστέλλεται ως bearer token.
          </p>
          <input
            type="password"
            className="input-dark text-sm"
            placeholder="sk-… ή το κλειδί του γραφείου"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
          />
          <div className="mt-3 flex items-center justify-between">
            <button
              type="button"
              className="text-xs text-silver hover:text-white"
              onClick={() => {
                setValue('');
                setApiKey('');
              }}
            >
              Καθαρισμός
            </button>
            <button type="button" className="btn-gold !px-4 !py-2" onClick={save}>
              {saved ? 'Αποθηκεύτηκε ✓' : 'Αποθήκευση'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
