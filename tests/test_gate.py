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
