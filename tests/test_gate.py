"""Behavior tests for the funds gate.

The centerpiece is ``test_race_screen_resolves_after_transfer_denies`` and the
polarity guard ``test_gate_removed_lets_race_through``. Together they make the
claim falsifiable: with the ordering enforcement present the race is DENIED;
strip it (naive_mode) and the same race is ALLOWED. The gate's value is the
ordering check, and the test is the proof.
"""

from agent_funds_gate import FundsGate, OFAC_CITE, ScreenResult, ScreenStatus

VERSION = "2026-06-17"


def _clear(seq, subject="ACME CORP", version=VERSION):
    return ScreenResult(ScreenStatus.CLEAR, version, seq, subject)


def test_clean_screen_before_transfer_allows():
    """Happy path: a CLEAR screen that completed before the transfer -> ALLOW."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=_clear(seq=5))
    assert d.decision == "ALLOW"
    assert d.failing_assertion is None
    assert d.rule_cite is None


def test_sdn_hit_denies():
    """A confirmed SDN hit blocks the transfer."""
    gate = FundsGate(VERSION)
    screen = ScreenResult(ScreenStatus.HIT, VERSION, 5, "BLOCKED PERSON ALPHA")
    d = gate.authorize(subject="BLOCKED PERSON ALPHA", transfer_seq=10, screen=screen)
    assert d.decision == "DENY"
    assert d.failing_assertion == "sdn_hit"
    assert d.rule_cite == OFAC_CITE


def test_race_screen_resolves_after_transfer_denies():
    """CENTERPIECE. The screen completed AFTER the transfer fired (completed_seq
    15 > transfer_seq 10). A naive 'was a screen run?' check passes this; the
    gate denies it. Goes RED if the ordering enforcement is removed."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=_clear(seq=15))
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_completion_precedes_execution"


def test_pending_screen_denies():
    """A screen still pending at execution time never completed -> DENY."""
    gate = FundsGate(VERSION)
    screen = ScreenResult(ScreenStatus.PENDING, VERSION, None, "ACME CORP")
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=screen)
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_completion_precedes_execution"


def test_no_screen_denies():
    """No screen at all fails closed."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=None)
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_present"


def test_stale_sdn_version_denies():
    """A clear screen against an unpinned/older SDN list version -> DENY."""
    gate = FundsGate(VERSION)
    d = gate.authorize(
        subject="ACME CORP", transfer_seq=10, screen=_clear(seq=5, version="2026-01-01")
    )
    assert d.decision == "DENY"
    assert d.failing_assertion == "sdn_version_pinned"


def test_screen_error_fails_closed():
    """A screen that errored/timed out fails closed -> DENY, never ALLOW."""
    gate = FundsGate(VERSION)
    screen = ScreenResult(ScreenStatus.ERROR, VERSION, 5, "ACME CORP")
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=screen)
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_error"


def test_deny_carries_cite_and_assertion_allow_carries_neither():
    """The decision contract: every DENY names a rule and a failed assertion;
    every ALLOW carries neither."""
    gate = FundsGate(VERSION)
    allow = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=_clear(seq=5))
    assert allow.rule_cite is None and allow.failing_assertion is None
    deny = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=None)
    assert deny.rule_cite is not None and deny.failing_assertion is not None


def test_gate_removed_lets_race_through():
    """POLARITY GUARD / the defeat. With enforcement stripped (naive_mode), the
    exact race the gate caught above is ALLOWED. This documents the hole the
    gate closes; it PASSES in naive mode on purpose."""
    gate = FundsGate(VERSION, naive_mode=True)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=_clear(seq=15))
    assert d.decision == "ALLOW"


# --- Hardening tests added after the independent code-reviewer pass (2026-06-18).
# Each guards a confirmed false-pass / crash path on this fail-closed control.

def test_screen_for_different_subject_denies():
    """The binding the demo is built on: a CLEAR screen of party A must NOT
    authorize a transfer to party B. The gate takes `subject` separately from
    `screen.subject`; if it never compares them, a clean screen of ACME would
    clear a wire to a sanctioned party. That is an OFAC violation -> DENY."""
    gate = FundsGate(VERSION)
    screen = ScreenResult(ScreenStatus.CLEAR, VERSION, 5, "ACME CORP")
    d = gate.authorize(subject="BLOCKED PERSON ALPHA", transfer_seq=10, screen=screen)
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_subject_mismatch"
    assert d.rule_cite == OFAC_CITE


def test_tie_completed_equals_transfer_denies():
    """Boundary lock: a screen that completed at the SAME seq as the transfer
    did not complete strictly before it -> DENY. Locks the `>=` so a later
    'cleanup' to `>` can't silently reopen the race."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=_clear(seq=10))
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_completion_precedes_execution"


def test_none_transfer_seq_fails_closed():
    """Malformed input fails closed: a None transfer_seq must DENY, never raise.
    An exception in a 'should I block?' check can resolve to 'proceed'."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=None, screen=_clear(seq=5))
    assert d.decision == "DENY"
    assert d.failing_assertion == "transfer_seq_invalid"


def test_bool_transfer_seq_fails_closed():
    """A bool is an int subtype in Python (True == 1); a control must reject it
    rather than treat True as seq 1 -> DENY."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=True, screen=_clear(seq=0))
    assert d.decision == "DENY"
    assert d.failing_assertion == "transfer_seq_invalid"


def test_malformed_screen_fails_closed():
    """A non-ScreenResult object handed in as the screen must DENY, not crash."""
    class Bogus:
        pass
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=Bogus())
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_malformed"


def test_pending_with_completed_seq_denies():
    """Internally inconsistent result (status PENDING but a terminal seq stamped)
    must DENY by positively requiring CLEAR, not ALLOW by falling through the
    HIT/ERROR special-cases. Also future-proofs against new ScreenStatus members."""
    gate = FundsGate(VERSION)
    screen = ScreenResult(ScreenStatus.PENDING, VERSION, 5, "ACME CORP")
    d = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=screen)
    assert d.decision == "DENY"
    assert d.failing_assertion == "screen_not_clear"


def test_nonpositive_seqs_deny():
    """Negative/zero sequence values are nonsense for a monotonic execution
    counter (uninitialized/spoofed) and must DENY even when the ordering relation
    holds numerically."""
    gate = FundsGate(VERSION)
    d = gate.authorize(subject="ACME CORP", transfer_seq=-1, screen=_clear(seq=-5))
    assert d.decision == "DENY"
    assert d.failing_assertion == "seq_out_of_range"


def test_cite_carries_precise_ofac_subsection():
    """The cite an FSI examiner asks for is a SUBSECTION, not 'OFAC' in general.
    Lock the precise anchors so a later generic-ization regresses RED:
    31 CFR 501.603 (block SDN property) / 501.604 (reject prohibited transfer),
    with strict liability under IEEPA, 50 U.S.C. 1705. Sourced from the canonical
    reg SSOT (active_regs.yaml: ofac_sdn_screening). Every DENY carries it."""
    assert "501.603" in OFAC_CITE
    assert "501.604" in OFAC_CITE
    assert "1705" in OFAC_CITE
    gate = FundsGate(VERSION)
    deny = gate.authorize(subject="ACME CORP", transfer_seq=10, screen=None)
    assert deny.rule_cite == OFAC_CITE
    assert "501.604" in deny.rule_cite
