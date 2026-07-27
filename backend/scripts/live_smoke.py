"""Ζωντανός έλεγχος end-to-end με πραγματικό κλειδί AI.

Εκτελεί ΟΛΟΚΛΗΡΟ το pipeline (ταξινόμηση → ειδικός κλάδου → πρότυπο
γραφείου → βαθμολόγηση) σε πραγματικό δικόγραφο, με πραγματική κλήση στο
Claude API. Χρησιμοποιήστε το εκεί όπου υπάρχει κλειδί (τοπικά ή στον
διακομιστή Hetzner).

    export ANTHROPIC_API_KEY=sk-ant-...
    cd backend && python scripts/live_smoke.py            # ενσωματωμένο δείγμα
    cd backend && python scripts/live_smoke.py δικογραφο.txt   # δικό σας αρχείο

Τυπώνει: ταξινόμηση, ειδικό που ανέλαβε, βαθμό επί τοις 100, ετυμηγορία,
πρότυπο γραφείου (ίχνη AI), κόστος tokens — και επιστρέφει κωδικό εξόδου 0
μόνο αν η ροή ολοκληρωθεί.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction import extract_text  # noqa: E402
from app.pipeline.engine import PipelineError, run_pipeline_with_usage  # noqa: E402

SAMPLE = """\
ΕΝΩΠΙΟΝ ΤΟΥ ΜΟΝΟΜΕΛΟΥΣ ΠΡΩΤΟΔΙΚΕΙΟΥ ΑΘΗΝΩΝ
(Διαδικασία Περιουσιακών Διαφορών)

ΑΓΩΓΗ

Του Ιωάννη Παπαδοπούλου του Γεωργίου, κατοίκου Αθηνών, οδός Ερμού αρ. 10,
με ΑΦΜ 000000000.

ΚΑΤΑ

Της ανώνυμης εταιρείας με την επωνυμία «ΔΟΜΙΚΗ Α.Ε.», που εδρεύει στον
Πειραιά και εκπροσωπείται νόμιμα.

_______________

Δυνάμει του από 15.1.2024 ιδιωτικού συμφωνητικού συμβάσεως έργου, ανέλαβα
έναντι της εναγομένης την εκτέλεση οικοδομικών εργασιών ανακαινίσεως επί
ακινήτου της, αντί συμφωνηθείσης συνολικής αμοιβής δώδεκα χιλιάδων (12.000)
ευρώ. Παρέδωσα το έργο προσηκόντως και εμπροθέσμως την 30.4.2024, όπως
προκύπτει από το υπ' αριθ. 5 πρωτόκολλο παραλαβής. Η εναγομένη κατέβαλε
μόνον το ποσό των έξι χιλιάδων (6.000) ευρώ, αρνούμενη αναιτιολογήτως την
εξόφληση του υπολοίπου, παρά τις οχλήσεις μου.

Επειδή η αξίωσή μου είναι νόμιμη, βάσιμη και αληθής, στηριζόμενη στα άρθρα
681 επ. ΑΚ περί συμβάσεως έργου και 340 ΑΚ περί υπερημερίας οφειλέτου.

Επειδή αρμοδίως και εμπροθέσμως ασκείται η παρούσα.

ΓΙΑ ΤΟΥΣ ΛΟΓΟΥΣ ΑΥΤΟΥΣ
και με τη ρητή επιφύλαξη παντός νομίμου δικαιώματός μου

ΖΗΤΩ

Να γίνει δεκτή η αγωγή μου. Να υποχρεωθεί η εναγομένη να μου καταβάλει το
ποσό των έξι χιλιάδων (6.000) ευρώ, νομιμοτόκως από της επιδόσεως της
παρούσης. Να καταδικαστεί η εναγομένη στη δικαστική μου δαπάνη.
"""


async def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("✗ Δεν έχει οριστεί ANTHROPIC_API_KEY στο περιβάλλον.")
        return 2

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        text = extract_text(path.name, path.read_bytes())
        print(f"Έγγραφο: {path}  ({len(text)} χαρακτήρες)")
    else:
        text = SAMPLE
        print(f"Έγγραφο: ενσωματωμένο δείγμα (αγωγή)  ({len(text)} χαρακτήρες)")

    print("Εκτέλεση pipeline με πραγματική κλήση Claude…\n")
    try:
        report, usage = await run_pipeline_with_usage(text)
    except PipelineError as exc:
        print(f"✗ PipelineError: {exc}")
        return 1

    c, s, a, fs = report.classification, report.score, report.auditor, report.firm_standard
    print(f"Ταξινόμηση      : {c.label}  ({c.branch})")
    print(f"Ανατέθηκε σε     : {a.title}")
    print(f"Βαθμός          : {s.overall:.0f}/100  — {s.verdict}")
    if s.capped:
        print(f"  (οροφή)       : {s.cap_reason}")
    print(f"Πρότυπο γραφείου : {fs.authenticity_verdict}  (register {fs.register_score}/100)")
    print(f"Ίχνη AI          : {len(fs.ai_tell_findings)}")
    print(f"Προτάσεις        : {len(report.suggestions)} · Κριτήρια: {len(report.criteria)}")
    if usage:
        print(
            f"Κόστος tokens    : in={usage['input_tokens']} out={usage['output_tokens']} "
            f"σε {usage['calls']} κλήσεις ({usage['model']})"
        )
    print("\n✓ Η ροή ολοκληρώθηκε.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
