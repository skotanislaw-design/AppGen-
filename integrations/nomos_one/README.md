# Ενσωμάτωση στο Nomos One (πίσω από JWT/RBAC)

Αυτός ο φάκελος είναι **drop-in πακέτο** για να προσαρτηθεί ο έλεγχος
δικογράφων στο Nomos One LPMS, πίσω από το υπάρχον JWT + RBAC — όχι
αυτόνομη υπηρεσία με δικό της κλειδί. Ο πυρήνας (pipeline, ειδικοί κλάδου,
πρότυπο γραφείου, υποδείγματα, εξαγωγή DOCX) επαναχρησιμοποιείται αυτούσιος·
αλλάζει μόνο ο τρόπος έκθεσης και η ταυτοποίηση.

> Το Nomos One είναι ξεχωριστό repository και δεν περιλαμβάνεται εδώ. Τα
> παρακάτω βήματα δείχνουν πού μπαίνει κάθε κομμάτι στον δικό του κώδικα.

## Αρχιτεκτονική

- **Auth-agnostic router**: `backend/app/integration.py` →
  `create_audit_router(auth_dependency=..., on_result=...)`. Δέχεται το δικό
  σας `require_role([...])` και το εφαρμόζει σε ΟΛΕΣ τις διαδρομές (ακόμη και
  οι αναγνώσεις απαιτούν έγκυρη συνεδρία στελέχους). Οι διαδρομές γίνονται
  `/api/audit/*`.
- **RBAC**: προτεινόμενοι ρόλοι `super_admin, admin, attorney, paralegal`
  (`DEFAULT_AUDIT_ROLES`). Ο `client` αποκλείεται — ο έλεγχος είναι εσωτερική
  νομική εργασία, όχι λειτουργία του portal εντολέα.
- **Matter linkage**: το `MatterAnalyzeRequest` δέχεται προαιρετικό
  `matter_id`· το `on_result(user, matter_id, report)` hook αποθηκεύει το
  αποτέλεσμα (π.χ. MongoDB, συνδεδεμένο με την υπόθεση).

## Backend — βήματα

1. **Τοποθετήστε τον πυρήνα** ως πακέτο μέσα στο backend του Nomos One.
   Αντιγράψτε ολόκληρο το `backend/app/` αυτού του repo ως `nomos_audit/`
   (ή εγκαταστήστε το ως εσωτερικό package). Απαιτούμενα modules: `pipeline/`,
   `exemplars/`, `extraction.py`, `docx_export.py`, `schemas.py`, `config.py`,
   `integration.py`. Το standalone `main.py` ΔΕΝ χρειάζεται.

2. **Εξαρτήσεις** (προσθήκη στο requirements του Nomos One αν λείπουν):
   `anthropic>=0.116`, `pypdf>=5.0`, `python-docx>=1.1`, `python-multipart`.

3. **Μεταβλητές περιβάλλοντος** στο `.env` του Nomos One:
   `ANTHROPIC_API_KEY=sk-ant-...` και προαιρετικά `NOMOS_AUDIT_MODEL`
   (default `claude-opus-4-8`). Το `NOMOS_AUDIT_API_KEY` **δεν** χρειάζεται —
   η ταυτοποίηση γίνεται από το JWT του LPMS.

4. **Mount του router** στο `main.py` του Nomos One:

   ```python
   from app.core.auth import require_role
   from nomos_audit.integration import create_audit_router
   from app.db import get_database
   from nomos_audit_integration.audit_persistence import save_audit_result

   async def persist_audit(user, matter_id, report):
       await save_audit_result(get_database(), user, matter_id, report)

   app.include_router(
       create_audit_router(
           auth_dependency=require_role(
               ["super_admin", "admin", "attorney", "paralegal"]
           ),
           on_result=persist_audit,   # παραλείψτε το αν δεν θέλετε εμμονή
       ),
       prefix="/api",
   )
   ```

   Απαίτηση: το `require_role(...)` επιστρέφει το αντικείμενο χρήστη (με
   `.id` / `.role`) ώστε το hook να το χρησιμοποιήσει. Αν το δικό σας απλώς
   επικυρώνει χωρίς να επιστρέφει χρήστη, προσαρμόστε το `save_audit_result`.

5. **Εμμονή/ιστορικό** (προαιρετικό): δείτε
   `backend/audit_persistence.py` — αποθηκεύει σύνοψη + πλήρη αναφορά στο
   collection `document_audits`, με `list_matter_audits()` για προβολή στο
   ιστορικό της υπόθεσης.

## Frontend — βήματα

1. **Αντιγράψτε τα components** του ελέγχου από το standalone
   `frontend/src/components/` (`DocumentInput`, `ProgressPanel`, `ReportView`,
   `ScoreGauge`, `CategoryBreakdown`, `CriteriaList`, `Suggestions`,
   `FirmStandardSection`, `ExemplarLibrary`) και το `types.ts` σε έναν φάκελο
   feature, π.χ. `src/features/audit/`.

2. **API layer**: χρησιμοποιήστε το `frontend/auditApi.ts` αυτού του φακέλου
   αντί του standalone `lib/api.ts`. Διαφορά: μιλά στο `/api/audit/*` και
   στέλνει το JWT του LPMS (`localStorage 'access_token'`, ίδια σύμβαση με τον
   axios interceptor σας) — όχι το αυτόνομο κλειδί. Το `ExemplarLibrary` και
   τα υπόλοιπα components πρέπει να κάνουν import από αυτό το `auditApi`.

3. **Σελίδα**: `frontend/DocumentAuditPage.tsx` — έτοιμη σελίδα module,
   default export, με προαιρετικό `matterId`. Προσαρμόστε τα relative imports
   στη δομή σας.

4. **Route + RBAC στο frontend**: προσθέστε το route πίσω από τον υπάρχοντα
   guard σας, π.χ.

   ```tsx
   <Route
     path="/audit"
     element={
       <RequireRole roles={['super_admin', 'admin', 'attorney', 'paralegal']}>
         <DocumentAuditPage />
       </RequireRole>
     }
   />
   // Matter-linked:
   <Route path="/matters/:id/audit" element={<MatterAuditRoute />} />
   // όπου το MatterAuditRoute περνά το :id ως matterId στο DocumentAuditPage.
   ```

5. **Sidebar**: προσθέστε στοιχείο πλοήγησης «Έλεγχος Δικογράφου» (ορατό
   στους επιτρεπόμενους ρόλους), κατά το pattern του navigation sidebar σας
   (χρυσό accent στο active, `#9BA8B7` inactive).

## Επαλήθευση

```bash
# Με έγκυρο JWT στελέχους:
curl -H "Authorization: Bearer <access_token>" \
  https://nomos.skotanislaw.gr/api/audit/document-types      # 200

# Χωρίς / με ρόλο client:
curl https://nomos.skotanislaw.gr/api/audit/document-types   # 401/403
```

## Ασφάλεια

- Δεν εκτίθεται δεύτερο κλειδί — η πρόσβαση διέπεται αποκλειστικά από το JWT
  και τους ρόλους του LPMS. Ο RBAC έλεγχος γίνεται στο route level (backend
  dependency), όχι μόνο στο frontend.
- Το `ANTHROPIC_API_KEY` παραμένει server-side (pydantic-settings / `.env`),
  ουδέποτε εκτίθεται στον browser.
- Το εργαλείο καταναλώνει Claude tokens (3 κλήσεις Opus ανά πλήρη έλεγχο) —
  εξετάστε rate limiting ανά χρήστη κατά το pattern του SkotanisBot
  (20 μηνύματα/ώρα) αν χρειαστεί.
