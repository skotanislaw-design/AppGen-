"""Ο agent ελέγχου: ταξινόμηση → ανάθεση σε ειδικό κλάδου → έλεγχος → βαθμολόγηση.

Η ταξινόμηση (στάδιο 1) γίνεται από ουδέτερο «δικονομολόγο διαλογής». Ο κατ'
ουσίαν έλεγχος (στάδιο 2) ΔΕΝ γίνεται από γενικό ελεγκτή: το δικόγραφο
δρομολογείται στον ειδικό του οικείου κλάδου (ποινικολόγο, αστικολόγο-
δικονομολόγο, διοικητικολόγο, ειδικό εξωδικαστικής πρακτικής — βλ.
experts.py), ο οποίος φέρει το γνωστικό υπόβαθρο και το δόγμα ελέγχου του
κλάδου του.

Και τα δύο στάδια εκτελούνται με structured outputs (output_config.format),
ώστε η απόκριση να είναι εγγυημένα έγκυρο JSON κατά το σχήμα. Η τελική
βαθμολογία υπολογίζεται ντετερμινιστικά στο scorer — όχι από το μοντέλο.
"""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import anthropic
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.exemplars import exemplar_for
from app.pipeline import checklists
from app.pipeline.checklists import CATEGORY_LABELS, Criterion
from app.pipeline.experts import ExpertProfile, expert_for
from app.pipeline.scorer import apply_firm_standard, compute_score
from app.schemas import (
    AuditModelOutput,
    AuditorInfo,
    AuditReport,
    CriterionReport,
    DocumentClassification,
    FirmStandardReview,
)

T = TypeVar("T", bound=BaseModel)


class PipelineError(RuntimeError):
    """Σφάλμα εκτέλεσης του pipeline με μήνυμα κατάλληλο για τον χρήστη."""


def _has_api_credentials() -> bool:
    """Ο AsyncAnthropic() αντλεί το κλειδί από το περιβάλλον. Χωρίς κλειδί, η
    κλήση αποτυγχάνει με ασαφές TypeError· ελέγχουμε νωρίς για καθαρό μήνυμα."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


TRIAGE_SYSTEM_PROMPT = """\
Είσαι έμπειρος Έλληνας δικονομολόγος και ενεργείς ως υπεύθυνος διαλογής \
δικογράφων στο γραφείο Skotanis & Associates. Έργο σου είναι αποκλειστικά η \
ακριβής ταξινόμηση του εγγράφου που σου υποβάλλεται — είδος, κλάδος δικαίου, \
σκοπός, δικονομικό πλαίσιο — ώστε ο κατ' ουσίαν έλεγχος να ανατεθεί στον \
ειδικό του οικείου κλάδου. Δεν αξιολογείς την ποιότητα του εγγράφου. Κρίνεις \
μόνο βάσει του κειμένου και του δηλωθέντος πλαισίου, χωρίς εικασίες.
"""

COMMON_AUDIT_RULES = """\
Ενεργείς ως αυστηρός ελεγκτής νομικής πληρότητας δικογράφων στο γραφείο \
Skotanis & Associates, εντός του πεδίου της ειδικότητάς σου.

Αποστολή σου είναι ο ενδελεχής, αμερόληπτος και αυστηρός έλεγχος του εγγράφου \
που σου υποβάλλεται: τυπική πληρότητα, ουσιαστική επάρκεια, νομική τεκμηρίωση \
και ποιότητα δικανικού λόγου. Δεν είσαι συντάκτης του εγγράφου ούτε συνήγορός \
του — είσαι ο κριτής του, όπως θα το έκρινε ο δικαστής ή ο αντίδικος.

Κανόνες ελέγχου:
1. Κρίνεις ΜΟΝΟ βάσει του κειμένου που σου δίνεται και του δηλωθέντος \
πλαισίου. Ό,τι δεν προκύπτει από το έγγραφο θεωρείται ελλείπον, ακόμη κι αν \
πιθανολογείται ότι υπάρχει αλλού στον φάκελο.
2. Ανέφερε ΚΑΘΕ έλλειψη που εντοπίζεις, και τις αμφίβολες — η διήθηση γίνεται \
σε επόμενο στάδιο. Καλύτερα ένα εύρημα που θα απορριφθεί παρά μια σιωπηρή \
παράλειψη.
3. Κάθε κρίση σου τεκμηριώνεται: παραθέτεις σύντομο αυτούσιο απόσπασμα του \
εγγράφου ως στοιχείο, ή διαπιστώνεις ρητά την απουσία.
4. Οι διατάξεις που επικαλείσαι αναφέρονται με πλήρη στοιχεία (άρθρο, \
παράγραφος, νομοθέτημα). Αν το έγγραφο επικαλείται ανίσχυρη ή τροποποιημένη \
διάταξη, το επισημαίνεις.
5. Ο σχολιασμός σου συντάσσεται σε άρτια ελληνική νομική γλώσσα, υψηλού \
δικανικού ύφους, χωρίς κοινοτοπίες.
6. Δεν επινοείς περιστατικά, νομολογία ή διατάξεις. Όπου δεν είσαι βέβαιος \
για την τρέχουσα μορφή διάταξης, διατυπώνεις τη σχετική επιφύλαξη.
7. Αν το έγγραφο εμπλέκει παρεμπιπτόντως ζητήματα άλλου κλάδου δικαίου εκτός \
της ειδικότητάς σου, τα καταγράφεις στα extra_findings με ρητή σύσταση \
ελέγχου από ειδικό του οικείου κλάδου — δεν τα προσπερνάς σιωπηρά.
"""


def build_audit_system_prompt(expert: ExpertProfile) -> str:
    """System prompt σταδίου 2: ταυτότητα ειδικού + κοινοί κανόνες ελέγχου."""
    return f"{expert.identity}\n\n{COMMON_AUDIT_RULES}"


FIRM_REVIEWER_SYSTEM_PROMPT = """\
Είσαι ο Επιμελητής Δικανικού Λόγου του γραφείου Skotanis & Associates — \
δικηγόρος με τριακονταετή μαχόμενη πορεία και εκδοτική εμπειρία στη νομική \
επιμέλεια, στον οποίο ανατίθεται η τελική κρίση: μπορεί το δικόγραφο να φέρει \
το λογότυπο της εταιρείας;

Το πρότυπο του γραφείου είναι διπλό και αδιαπραγμάτευτο:
Α. Τα δικόγραφα της εταιρείας είναι ΥΠΟΔΕΙΓΜΑΤΙΚΑ — γραφή επιπέδου έγκριτου \
συνηγόρου με διδακτορική κατάρτιση.
Β. Τα δικόγραφα της εταιρείας ΔΕΝ επιτρέπεται να προδίδουν σύνταξη από AI ή \
να μοιάζουν με προϊόν μίας απάντησης γλωσσικού μοντέλου. Αν ένας καθηγητής \
Νομικής θα μπορούσε να τα ξεχωρίσει ως κείμενο AI, απορρίπτονται.

Ενδείξεις AI που αναζητάς εξονυχιστικά (κατάλογος ενδεικτικός, όχι \
περιοριστικός):
- Δομικές: κουκκίδες, αριθμημένες λίστες ή παύλες μέσα στο σώμα του \
δικογράφου· έντονες επικεφαλίδες τύπου εκθέσεως· παράγραφοι ομοιόμορφου \
μήκους σε συμμετρική διάταξη· τριαδικές απαριθμήσεις-μανιέρα· αδικαιολόγητα \
placeholders ή αγκύλες που έμειναν ασυμπλήρωτες.
- Φρασεολογικές: «Συνοψίζοντας», «Κατά συνέπεια, σημειώνεται ότι», «Αξίζει \
να επισημανθεί», «Είναι σημαντικό να», «λαμβάνοντας υπόψη», «όπως \
αναφέρεται», «σύμφωνα με τα παραπάνω», και κάθε τυποποιημένη μεταβατική \
φράση γλωσσικού μοντέλου.
- Ρυθμού: προτάσεις ομοιόμορφου μήκους και συντακτικής δομής, μηχανική ροή \
χωρίς τους φυσικούς δικανικούς συνδέσμους («Εξ άλλου», «Πλην όμως», «Τούτων \
δοθέντων», «Κατά μείζονα λόγο»), κατάληξη ενοτήτων σε περιλήψεις αντί σε \
ισχυρισμούς.
- Ύφους: ουδέτερο-γραφειοκρατικό λεξιλόγιο αντί δικανικού («εν προκειμένω», \
«τυγχάνει προδήλως αβάσιμος», «αλυσιτελώς», «υπό τα ως άνω πραγματικά»), \
επεξηγηματικός-εκπαιδευτικός τόνος αντί συνηγορίας.
- Τεκμηρίωσης: γενικόλογες επικλήσεις «πάγιας νομολογίας» χωρίς αριθμό και \
έτος απόφασης, απουσία θεωρίας με όνομα συγγραφέα, διατάξεις χωρίς \
παράγραφο/νομοθέτημα — η ρηχή τεκμηρίωση είναι χαρακτηριστικό ίχνος AI.

Το υποδειγματικό πρότυπο που απαιτείς: εναλλαγή σύντομων-κοφτών και πυκνών \
αναλυτικών παραγράφων· νομολογία με πλήρη στοιχεία (π.χ. ΑΠ 1234/2021, ΣτΕ \
789/2020)· θεωρία κατ' όνομα όπου αρμόζει· λατινικοί όροι όπου προσθέτουν \
ακρίβεια (fumus boni iuris, in dubio pro reo)· ενότητες που κλείνουν με \
ισχυρισμό, όχι με ανακεφαλαίωση· γλώσσα που πείθει δικαστή, όχι που \
ενημερώνει αναγνώστη.

Κανόνες κρίσης:
1. Κάθε εύρημα τεκμηριώνεται με αυτούσιο απόσπασμα.
2. Όπου προτείνεις αναδιατύπωση, τη δίνεις σε φυσικό, υψηλό δικανικό ύφος — \
όχι σε δικό σου μηχανικό πρότυπο.
3. Είσαι αυστηρός αλλά δίκαιος: η λιτότητα έμπειρου συντάκτη δεν είναι \
ένδειξη AI· η μανιέρα και η ομοιομορφία είναι.
4. Η ετυμηγορία ai_marked απαιτεί σαφή και σωρευτικά ίχνη — όχι μία μεμονωμένη \
αδέξια φράση. Η human_register απαιτεί κείμενο που δεν θα ξεχώριζε καθηγητής \
Νομικής από γραφή έγκριτου δικηγόρου.
"""

FIRM_REVIEW_TASK = """\
ΣΤΑΔΙΟ 3 — ΕΛΕΓΧΟΣ ΠΡΟΤΥΠΟΥ ΓΡΑΦΕΙΟΥ

Κρίνε αν το ανωτέρω έγγραφο μπορεί να φέρει το λογότυπο της εταιρείας:

1. Εντόπισε ΚΑΘΕ ένδειξη σύνταξης από AI ή απόκλισης από φυσικό δικανικό \
λόγο (ai_tell_findings), με αυτούσιο απόσπασμα, εξήγηση και — όπου έχει \
νόημα — προτεινόμενη αναδιατύπωση.
2. Κατέγραψε τι υπολείπεται για να είναι το δικόγραφο υποδειγματικό κατά το \
πρότυπο του γραφείου (exemplary_gaps), πέραν των ενδείξεων AI.
3. Βαθμολόγησε στο register_score (0-100) την εγγύτητα στο υποδειγματικό \
πρότυπο.
4. Απόφηνε authenticity_verdict: human_register / borderline / ai_marked, \
κατά τους κανόνες κρίσης σου.
5. Στο assessment διατύπωσε την τελική σου κρίση σε 1-2 παραγράφους ρέοντος \
νομικού λόγου.

Ο έλεγχος αφορά τον λόγο και το επίπεδο του κειμένου — όχι την ουσιαστική \
νομική του βασιμότητα, η οποία έχει ήδη ελεγχθεί από τον ειδικό του κλάδου.
"""


async def firm_review(
    client: AsyncAnthropic,
    settings: Settings,
    document: dict[str, Any],
    usage_acc: dict | None = None,
) -> FirmStandardReview:
    return await _structured_call(
        client,
        settings,
        system_prompt=FIRM_REVIEWER_SYSTEM_PROMPT,
        document=document,
        task=FIRM_REVIEW_TASK,
        output_model=FirmStandardReview,
        effort=settings.audit_effort,
        usage_acc=usage_acc,
    )


# ---------------------------------------------------------------------------
# Κλήση Claude με structured output
# ---------------------------------------------------------------------------


def _document_block(text: str, context: str | None) -> dict[str, Any]:
    parts = [f"<ΕΓΓΡΑΦΟ>\n{text}\n</ΕΓΓΡΑΦΟ>"]
    if context and context.strip():
        parts.append(f"<ΠΛΑΙΣΙΟ_ΑΠΟ_ΤΟΝ_ΕΝΤΟΛΕΑ>\n{context.strip()}\n</ΠΛΑΙΣΙΟ_ΑΠΟ_ΤΟΝ_ΕΝΤΟΛΕΑ>")
    return {
        "type": "text",
        "text": "\n\n".join(parts),
        "cache_control": {"type": "ephemeral"},
    }


def _accumulate_usage(usage_acc: dict | None, response: Any) -> None:
    """Προσθέτει τα tokens μιας απόκρισης στον συλλέκτη (για cost-tracking)."""
    if usage_acc is None:
        return
    u = getattr(response, "usage", None)
    if u is None:
        return
    for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        usage_acc[k] = usage_acc.get(k, 0) + (getattr(u, k, 0) or 0)
    usage_acc["calls"] = usage_acc.get("calls", 0) + 1


async def _structured_call(
    client: AsyncAnthropic,
    settings: Settings,
    *,
    system_prompt: str,
    document: dict[str, Any],
    task: str,
    output_model: type[T],
    effort: str,
    usage_acc: dict | None = None,
) -> T:
    schema = output_model.model_json_schema()
    try:
        response = await client.messages.create(
            model=settings.model,
            max_tokens=settings.max_output_tokens,
            thinking={"type": "adaptive"},
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": [document, {"type": "text", "text": task}]}
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise PipelineError(
            "Μη έγκυρο ANTHROPIC_API_KEY — ελέγξτε τη ρύθμιση του διακομιστή."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise PipelineError(
            "Υπέρβαση ορίου αιτημάτων προς το Claude API — δοκιμάστε ξανά σε λίγο."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise PipelineError(f"Σφάλμα Claude API ({exc.status_code}).") from exc
    except anthropic.APIConnectionError as exc:
        raise PipelineError("Αδυναμία σύνδεσης με το Claude API.") from exc

    # Τα tokens χρεώθηκαν ανεξαρτήτως stop_reason — τα καταγράφουμε τώρα.
    _accumulate_usage(usage_acc, response)

    if response.stop_reason == "refusal":
        raise PipelineError(
            "Το μοντέλο αρνήθηκε να επεξεργαστεί το περιεχόμενο του εγγράφου."
        )
    if response.stop_reason == "max_tokens":
        raise PipelineError(
            "Η ανάλυση υπερέβη το όριο εξόδου — δοκιμάστε με συντομότερο έγγραφο."
        )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise PipelineError("Κενή απόκριση από το μοντέλο.")
    try:
        return output_model.model_validate_json(text)
    except Exception as exc:
        raise PipelineError("Μη έγκυρη δομημένη απόκριση από το μοντέλο.") from exc


# ---------------------------------------------------------------------------
# Στάδιο 1 — Ταξινόμηση
# ---------------------------------------------------------------------------

CLASSIFY_TASK_TEMPLATE = """\
ΣΤΑΔΙΟ 1 — ΤΑΞΙΝΟΜΗΣΗ

Προσδιόρισε το είδος, τον κλάδο, τον σκοπό και το δικονομικό πλαίσιο του \
ανωτέρω εγγράφου. Επίλεξε το doc_type ΑΠΟΚΛΕΙΣΤΙΚΑ από το ακόλουθο μητρώο· αν \
κανένα είδος δεν ταιριάζει, επίλεξε 'generic' και περιέγραψε το είδος στο label.

ΜΗΤΡΩΟ ΕΙΔΩΝ:
{menu}

Στο summary απόδωσε με ακρίβεια το αντικείμενο του εγγράφου. Στο confidence \
δήλωσε πόσο βέβαιος είσαι για την ταξινόμηση.
"""


async def classify(
    client: AsyncAnthropic,
    settings: Settings,
    document: dict[str, Any],
    usage_acc: dict | None = None,
) -> DocumentClassification:
    task = CLASSIFY_TASK_TEMPLATE.format(menu=checklists.classification_menu())
    result = await _structured_call(
        client,
        settings,
        system_prompt=TRIAGE_SYSTEM_PROMPT,
        document=document,
        task=task,
        output_model=DocumentClassification,
        effort=settings.classification_effort,
        usage_acc=usage_acc,
    )
    if result.doc_type not in checklists.DOCUMENT_TYPES:
        result = result.model_copy(update={"doc_type": "generic"})
    return result


# ---------------------------------------------------------------------------
# Στάδιο 2 — Έλεγχος πληρότητας
# ---------------------------------------------------------------------------


def _render_checklist(criteria: list[Criterion]) -> str:
    lines = []
    for crit in criteria:
        flag = " [ΚΡΙΣΙΜΟ]" if crit.critical else ""
        lines.append(
            f"- id: {crit.id} | κατηγορία: {CATEGORY_LABELS[crit.category]}{flag}\n"
            f"  {crit.text}"
        )
    return "\n".join(lines)


AUDIT_TASK_TEMPLATE = """\
ΣΤΑΔΙΟ 2 — ΕΛΕΓΧΟΣ ΝΟΜΙΚΗΣ ΠΛΗΡΟΤΗΤΑΣ

Το έγγραφο ταξινομήθηκε ως: {label} ({branch}).
Σκοπός: {purpose}
Δικονομικό πλαίσιο: {stage}

Αξιολόγησε το έγγραφο έναντι ΚΑΘΕ κριτηρίου του ακόλουθου καταλόγου. Για κάθε \
κριτήριο επίστρεψε μία εγγραφή στο evaluations με το ίδιο ακριβώς criterion_id.

ΚΑΤΑΛΟΓΟΣ ΚΡΙΤΗΡΙΩΝ:
{checklist}

Οδηγίες αξιολόγησης:
- status: "met" μόνο όταν το κριτήριο καλύπτεται πλήρως και ορθά· \
"partially_met" όταν υπάρχει ατελής, αόριστη ή εν μέρει εσφαλμένη κάλυψη· \
"missing" όταν το στοιχείο απουσιάζει ή είναι νομικά εσφαλμένο· \
"not_applicable" ΜΟΝΟ όταν το κριτήριο εκ φύσεως δεν αφορά το συγκεκριμένο \
έγγραφο (π.χ. δικαστικό ένσημο σε αναγνωριστική αγωγή).
- score: 0-100, αυστηρά. Το 100 προϋποθέτει άψογη κάλυψη· κάλυψη με αοριστίες \
ή κενά βαθμολογείται κάτω από 70.
- evidence: αυτούσιο απόσπασμα έως 30 λέξεων που θεμελιώνει την κρίση, ή null \
όταν διαπιστώνεις απουσία.
- commentary: αιτιολογημένη νομική κρίση — τι υπάρχει, τι λείπει, ποια η \
δικονομική/ουσιαστική συνέπεια της έλλειψης.

Στα extra_findings κατέγραψε κάθε ουσιώδες πρόβλημα που δεν καλύπτεται από τα \
κριτήρια (π.χ. εσωτερικές αντιφάσεις, εσφαλμένη επίκληση διάταξης, παραγραφή \
που προκύπτει από τα ίδια τα εκτιθέμενα, επικίνδυνες ομολογίες).

Στα suggestions δώσε ιεραρχημένες, άμεσα εφαρμόσιμες βελτιώσεις. Όπου η \
βελτίωση αφορά διατύπωση, πρότεινε συγκεκριμένη διατύπωση σε δικανικό ύφος.

Στο overall_assessment συνόψισε τη συνολική σου κρίση σε 2-4 παραγράφους \
ρέοντος ελληνικού νομικού λόγου, χωρίς λίστες και χωρίς αριθμητικούς βαθμούς: \
πού στέκει το δικόγραφο, πού κινδυνεύει, τι προέχει να διορθωθεί.
"""

EXEMPLAR_REFERENCE_TEMPLATE = """\

ΥΠΟΔΕΙΓΜΑ ΑΝΑΦΟΡΑΣ ΤΟΥ ΓΡΑΦΕΙΟΥ ΓΙΑ ΤΟ ΕΙΔΟΣ — «{title}»

Το ακόλουθο σχέδιο αποτελεί το υπόδειγμα του γραφείου για το είδος αυτό και \
ορίζει τον πήχυ ως προς τη δομική οικονομία (σειρά και αναλογίες τμημάτων), \
την πληρότητα της θεμελίωσης και το επίπεδο του δικανικού λόγου. \
Χρησιμοποίησέ το ως μέτρο σύγκρισης: αξιολόγησε αν το ελεγχόμενο έγγραφο \
καλύπτει τα αντίστοιχα δομικά και ουσιαστικά στοιχεία στον βαθμό που τα \
καλύπτει το υπόδειγμα. ΜΗΝ απαιτείς λεκτική ταύτιση ούτε πανομοιότυπη \
διάταξη — τα πραγματικά κάθε υπόθεσης διαφέρουν· απαίτησε όμως ισοδύναμη \
δομική πληρότητα και θεμελίωση. Τα [ΣΥΜΠΛΗΡΩΣΤΕ] του υποδείγματος σημειώνουν \
θέσεις εξατομίκευσης, όχι ελλείψεις του.

<ΥΠΟΔΕΙΓΜΑ>
{body}
</ΥΠΟΔΕΙΓΜΑ>
"""


async def audit(
    client: AsyncAnthropic,
    settings: Settings,
    document: dict[str, Any],
    classification: DocumentClassification,
    criteria: list[Criterion],
    expert: ExpertProfile,
    usage_acc: dict | None = None,
) -> AuditModelOutput:
    task = AUDIT_TASK_TEMPLATE.format(
        label=classification.label,
        branch=classification.branch,
        purpose=classification.purpose,
        stage=classification.procedural_stage or "δεν προσδιορίζεται",
        checklist=_render_checklist(criteria),
    )
    exemplar = exemplar_for(classification.doc_type)
    if exemplar is not None:
        task += EXEMPLAR_REFERENCE_TEMPLATE.format(
            title=exemplar.title, body=exemplar.body
        )
    return await _structured_call(
        client,
        settings,
        system_prompt=build_audit_system_prompt(expert),
        document=document,
        task=task,
        output_model=AuditModelOutput,
        effort=settings.audit_effort,
        usage_acc=usage_acc,
    )


# ---------------------------------------------------------------------------
# Ορχήστρωση
# ---------------------------------------------------------------------------


def _build_report(
    settings: Settings,
    classification: DocumentClassification,
    criteria: list[Criterion],
    audit_output: AuditModelOutput,
    expert: ExpertProfile,
    firm_standard: FirmStandardReview,
) -> AuditReport:
    crit_by_id = {c.id: c for c in criteria}
    # Κρατάμε μόνο αξιολογήσεις που αντιστοιχούν σε πραγματικά κριτήρια·
    # τυχόν πλεονάζουσες αγνοούνται, ώστε η βαθμολόγηση να μένει ελέγξιμη.
    valid_evals = [e for e in audit_output.evaluations if e.criterion_id in crit_by_id]
    score = apply_firm_standard(
        compute_score(criteria, valid_evals), firm_standard.authenticity_verdict
    )

    criteria_reports = []
    for ev in valid_evals:
        crit = crit_by_id[ev.criterion_id]
        criteria_reports.append(
            CriterionReport(
                criterion_id=crit.id,
                category=crit.category.value,
                category_label=CATEGORY_LABELS[crit.category],
                text=crit.text,
                critical=crit.critical,
                weight=crit.weight,
                status=ev.status,
                score=ev.score,
                evidence=ev.evidence,
                commentary=ev.commentary,
            )
        )

    return AuditReport(
        classification=classification,
        auditor=AuditorInfo(
            branch=expert.branch,
            title=expert.title,
            description=expert.description,
        ),
        score=score,
        criteria=criteria_reports,
        extra_findings=audit_output.extra_findings,
        suggestions=audit_output.suggestions,
        firm_standard=firm_standard,
        overall_assessment=audit_output.overall_assessment,
        model=settings.model,
    )


def _validate_input(text: str, settings: Settings) -> str:
    cleaned = text.strip()
    if len(cleaned) < settings.min_document_chars:
        raise PipelineError(
            "Το κείμενο είναι πολύ σύντομο για ουσιαστικό έλεγχο "
            f"(ελάχιστο: {settings.min_document_chars} χαρακτήρες)."
        )
    if len(cleaned) > settings.max_document_chars:
        raise PipelineError(
            "Το κείμενο υπερβαίνει το μέγιστο μέγεθος "
            f"({settings.max_document_chars} χαρακτήρες)."
        )
    return cleaned


async def run_pipeline_events(
    text: str,
    context: str | None = None,
    doc_type_hint: str | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """Εκτελεί το pipeline εκπέμποντας γεγονότα προόδου.

    Γεγονότα: (stage, payload) όπου stage ∈ {classifying, classified,
    auditing, complete}.
    """
    settings = get_settings()
    if not _has_api_credentials():
        raise PipelineError(
            "Ο έλεγχος δεν είναι διαθέσιμος: δεν έχει ρυθμιστεί κλειδί AI "
            "(ANTHROPIC_API_KEY) στον διακομιστή."
        )
    cleaned = _validate_input(text, settings)
    document = _document_block(cleaned, context)
    usage_acc: dict = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "calls": 0,
        "model": settings.model,
    }

    async with AsyncAnthropic() as client:
        yield "classifying", None
        if doc_type_hint and doc_type_hint in checklists.DOCUMENT_TYPES:
            spec = checklists.DOCUMENT_TYPES[doc_type_hint]
            classification = DocumentClassification(
                doc_type=spec.key,
                branch=spec.branch,  # type: ignore[arg-type]
                label=spec.label,
                purpose="Καθορίστηκε από τον χρήστη.",
                court_or_authority=None,
                procedural_stage=None,
                summary="Το είδος του εγγράφου ορίστηκε ρητά από τον χρήστη.",
                confidence="high",
            )
        else:
            classification = await classify(client, settings, document, usage_acc)
        yield "classified", classification

        # Δρομολόγηση στον ειδικό του κλάδου — ο ποινικολόγος δεν ελέγχει
        # διοικητικά δικόγραφα και αντιστρόφως.
        expert = expert_for(classification.branch)
        criteria = checklists.criteria_for(classification.doc_type)
        yield (
            "auditing",
            {
                "criteria_count": len(criteria),
                "auditor": {
                    "branch": expert.branch,
                    "title": expert.title,
                    "description": expert.description,
                },
            },
        )
        audit_output = await audit(
            client, settings, document, classification, criteria, expert, usage_acc
        )

        # Στάδιο 3: πρότυπο γραφείου — υποδειγματικός λόγος, μηδενικά ίχνη AI.
        yield "firm_review", None
        firm_standard = await firm_review(client, settings, document, usage_acc)

        report = _build_report(
            settings, classification, criteria, audit_output, expert, firm_standard
        )
        # Συγκεντρωτικό usage των 3 κλήσεων — για cost-tracking στον καλούντα.
        yield "usage", usage_acc
        yield "complete", report


async def run_pipeline_with_usage(
    text: str,
    context: str | None = None,
    doc_type_hint: str | None = None,
) -> tuple[AuditReport, dict | None]:
    """Όπως το run_pipeline, αλλά επιστρέφει και το συγκεντρωτικό usage."""
    report: AuditReport | None = None
    usage: dict | None = None
    async for stage, payload in run_pipeline_events(text, context, doc_type_hint):
        if stage == "usage":
            usage = payload
        elif stage == "complete":
            report = payload
    assert report is not None
    return report, usage


async def run_pipeline(
    text: str,
    context: str | None = None,
    doc_type_hint: str | None = None,
) -> AuditReport:
    report, _ = await run_pipeline_with_usage(text, context, doc_type_hint)
    return report


def sse_event(stage: str, payload: Any) -> str:
    """Σειριοποίηση γεγονότος pipeline σε γραμμή SSE."""
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    body = json.dumps({"stage": stage, "data": data}, ensure_ascii=False)
    return f"data: {body}\n\n"
