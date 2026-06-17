"""Defeat-first demo. Run: python demo/demo.py  (about 40-90 seconds to read)

Shows the race winning against a naive check, then the gate catching it.
"""

import sys
from pathlib import Path

# Run straight from a fresh clone, no install needed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_funds_gate import FundsGate, ScreenResult, ScreenStatus  # noqa: E402

VERSION = "2026-06-17"
SUBJECT = "BLOCKED PERSON ALPHA"
AMOUNT = "$250,000"

# A race: the screen resolves CLEAR, but only AFTER the transfer fired.
# The transfer executes at seq 10; the screen completes at seq 15.
TRANSFER_SEQ = 10
race_screen = ScreenResult(ScreenStatus.CLEAR, VERSION, completed_seq=15, subject=SUBJECT)


def _rule():
    print("-" * 72)


print()
print("agent-funds-gate -- we attacked our own gate and showed it holds.")
print()
print(f"An agent fires a {AMOUNT} transfer at seq {TRANSFER_SEQ}. The OFAC screen for")
print(f"the same party does not COMPLETE until seq {race_screen.completed_seq} -- after the money moved.")
_rule()

print()
print("[A] THE DEFEAT -- naive gate (only asks 'did a clear screen exist?')")
naive = FundsGate(VERSION, naive_mode=True)
a = naive.authorize(subject=SUBJECT, transfer_seq=TRANSFER_SEQ, screen=race_screen)
print(f"    decision: {a.decision}")
print(f"    -> {AMOUNT} sent to '{SUBJECT}'. The screen had not completed.")
print("    The naive check passed because a screen existed. OFAC violation shipped.")

print()
print("[B] THE GATE -- ordering enforced (screen must COMPLETE before execution)")
gate = FundsGate(VERSION)
b = gate.authorize(subject=SUBJECT, transfer_seq=TRANSFER_SEQ, screen=race_screen)
print(f"    decision: {b.decision}")
print(f"    rule_cite: {b.rule_cite}")
print(f"    failing_assertion: {b.failing_assertion}")
print(f"    -> transfer blocked: screen completed at seq {race_screen.completed_seq}, "
      f"transfer was seq {TRANSFER_SEQ}.")
_rule()

print()
print("Verify the polarity yourself -- the test IS the control:")
print("    pytest tests/test_gate.py::test_race_screen_resolves_after_transfer_denies")
print("    Delete the ordering check in gate.py and that test turns RED.")
print()
