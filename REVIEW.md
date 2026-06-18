# Independent review record — agent-funds-gate

This gate was built solo. Before any public release it owed an independent
adversarial review (writer != reviewer) and a reproduced polarity proof. Both
are recorded here.

## Review 1 — adversarial pass (2026-06-18)
Verdict: **PASS-WITH-FIXES.** The core invariant (screen must COMPLETE strictly
before the transfer executes) was correctly enforced and provably falsifiable.
But the gate trusted that the `ScreenResult` it was handed was about the party
being paid, and did not validate input shape. Confirmed findings:

- **[CRITICAL] subject not bound to the action.** The gate took `subject`
  separately from `screen.subject` and never compared them, so a CLEAR screen of
  party A authorized a transfer to sanctioned party B — an OFAC violation, and
  the exact "a screen exists but doesn't bind" defeat the demo dramatizes.
- **[CRITICAL] malformed input crashed instead of failing closed**
  (`transfer_seq=None`, a non-`ScreenResult` screen). A fail-closed control must
  DENY on bad input, never raise.
- **[MAJOR] non-positive sequence values** (negative/zero) passed the ordering
  relation numerically and reached ALLOW.
- **[MAJOR] bool `transfer_seq`** accepted as int (`True == 1`).
- **[MAJOR] fall-through ALLOW.** A PENDING-with-`completed_seq` result, and any
  future `ScreenStatus` member, reached ALLOW by falling through the HIT/ERROR
  special-cases rather than by affirming `CLEAR`.
- **[MINOR] tie boundary** (`completed_seq == transfer_seq`) was already correct
  (`>=`); locked with a test so a later cleanup to `>` can't reopen the race.

## Fixes applied (TDD: each defect got a test that goes RED first)
- subject-match check -> DENY `screen_subject_mismatch`.
- input-shape validation before evidence is built -> DENY `transfer_seq_invalid`
  / `screen_malformed` (via `_deny_bare`); never raises.
- non-positive seq -> DENY `seq_out_of_range`.
- bool excluded from the int check.
- positive `status is CLEAR` assertion before ALLOW -> DENY `screen_not_clear`.
- tie-boundary lock test.

Test count 9 -> 16 (7 hardening tests added; all green).

## Review 2 — confirmation pass (2026-06-18)
Verdict: **CONFIRMED-FIXED.** All five fix areas enforced in fail-closed order,
each with a guarding test that genuinely asserts DENY. Full attack matrix
(subject mismatch, None/bool/float/str seq, bogus screen, negative/zero seqs,
pending-with-seq, tie) — every input returns a DENY `GateDecision`; none raises;
the only ALLOW is the legitimate happy path. Decision contract holds across the
new `_deny_bare` path (DENY -> rule_cite + failing_assertion; ALLOW -> both None).

## Polarity proof (reproduced both before and after the fixes)
The claim is falsifiable and asserts the PRESENCE of the safe condition, not the
absence of an unsafe one:

```
# remove the ordering-check block in src/agent_funds_gate/gate.py:
#   if screen.completed_seq is None or screen.completed_seq >= transfer_seq:
#       return self._deny(ORDERING_ASSERTION, screen, evidence)
python3 -m pytest tests/test_gate.py::test_race_screen_resolves_after_transfer_denies -q
# -> RED: AssertionError 'ALLOW' == 'DENY'   (the race is allowed again)
# restore the block:
python3 -m pytest -q
# -> 16 passed
```

`test_gate_removed_lets_race_through` shows the same hole from the other side:
in `naive_mode` the race is ALLOW on purpose.

## Status
Reviewer-passed and polarity-proven. Release to public GitHub stays news-pegged
and owner-tap. Framing law: "we attacked our own gate," never "caught a real
incident."
