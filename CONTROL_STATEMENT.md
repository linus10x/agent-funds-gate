# Control statement: OFAC screen-before-transfer gate

One control, stated the way a model-risk team or an examiner reads it: the rule it
serves, the way it fails without the control, the assertion it enforces, and the one
specific false-pass it stops. The gate is `agent-funds-gate`; this is what it claims
and how to check the claim.

## Regulatory anchor (precise)

**31 CFR 501.603** (reports of blocked property) and **31 CFR 501.604** (reports of
rejected transactions), under the OFAC Reporting, Procedures and Penalties Regulations
(31 CFR Part 501). A prohibited transfer to a Specially Designated National must be
blocked or rejected before value moves, not after. Civil liability is **strict under
IEEPA, 50 U.S.C. 1705**: an institution is liable whether or not it intended the
violation, and whether or not a screen was "in flight." Subsection sourced 2026-06-18
against eCFR/OFAC primary sources and recorded in the canonical reg SSOT
(`active_regs.yaml`, id `ofac_sdn_screening`).

Why the strict-liability standard matters to the design: if liability turned on intent,
a screen that merely *exists* might be a defense. It does not, so the control has to
prove the screen **completed before** the transfer executed, not that one was started.

## Failure mode (what goes wrong without the control)

An agent that moves money calls a sanctions screen and a payment rail as two separate
steps. Under load, retry, or async scheduling, the payment can execute while the screen
is still pending, or the result can be read back against the wrong party. A naive check
("was a screen run?") passes both cases. The money has already moved to a possibly
sanctioned party, and the strict-liability clock has already started.

## The assertion the gate enforces

A transfer is ALLOWed only if a version-pinned OFAC SDN screen:
1. is **about the party being paid** (the screen subject equals the transfer subject),
2. returned **CLEAR** (affirmed positively, not reached by falling through HIT/ERROR),
3. ran against the **pinned SDN list version**, and
4. **completed strictly before** the transfer executed
   (`screen.completed_seq < transfer_seq`).

Any other state, including missing, pending, errored, malformed, or a non-positive
sequence number, **fails closed to DENY**. Every DENY carries the rule cite above and
the named assertion that failed; every ALLOW carries neither. The control denies on bad
input rather than raising, because an exception in a "should I block?" check can be
swallowed by the caller and resolve to "proceed."

## The one specific false-pass it prevents

**The screen-completes-after-transfer race.** A CLEAR screen exists, but it finished
*after* the money already moved (`completed_seq = 15`, `transfer_seq = 10`). A
"did a screen come back clean?" check authorizes this. The gate denies it on assertion
`screen_completion_precedes_execution`. This is the centerpiece, and it is falsifiable:
remove the ordering check and `test_race_screen_resolves_after_transfer_denies` goes
RED (the race is allowed again); restore it and the suite is green. The same hole is
shown from the other side by `naive_mode`, which allows the race on purpose.

A second confirmed false-pass, found in the independent review, is reinforced here: a
CLEAR screen of party A authorizing a transfer to sanctioned party B. The gate binds the
screen to the subject and denies on `screen_subject_mismatch`.

Framing: we attacked our own gate to find these. They are defeats we built and closed,
not a real incident.

## SR 26-2 context (SSOT-confirmed facts only)

SR 26-2 / OCC Bulletin 2026-13 (joint Fed/OCC/FDIC, issued April 17, 2026; non-enforceable
supervisory guidance, most relevant to banking organizations over $30B in total assets)
revised model-risk guidance and superseded SR 11-7 and SR 21-8. Per OCC Bulletin 2026-13,
generative and agentic AI models "are not within the scope of this guidance," and an
AI-focused Request for Information is forthcoming. An institution running agentic payments
therefore has no prescribed supervisory model for those systems today, so it must
demonstrate, with its own controls, that each value-moving action stays bounded. A
fail-closed, polarity-proven screen-before-transfer gate is one such demonstration.

## Verify the claim (one command, zero install)

```
python3 -m pytest -q     # 17 tests green; src is on the path via pyproject
python demo/demo.py      # the defeat, then the gate, from a fresh clone
```

Polarity proof (the claim is falsifiable):

```
# remove the ordering-check block in src/agent_funds_gate/gate.py, then:
python3 -m pytest tests/test_gate.py::test_race_screen_resolves_after_transfer_denies -q
# -> RED: the race is allowed again. Restore the block -> 17 passed.
```

## What this does NOT catch (scope limits)

This is the authoritative scope list for the gate. README.md points here so the two never
drift. This is one control on one ordering invariant, and it assumes the screen object and
the SDN list it is handed are trustworthy inputs. It does NOT catch:

- **SDN-list currency beyond a pinned-version check.** It confirms the screen ran against
  the pinned list version; it does not confirm that version is the current OFAC list.
- **Name matching / fuzzy-match tuning.** It does not decide whether a name is a match.
- **The 50%-rule on ownership** (an entity owned 50%+ by blocked persons).
- **License determinations** (whether an otherwise-prohibited transfer is authorized).
- **Non-payment actions.** It governs value-moving transfers, not other agent actions.
- **A forged or unsigned screen result.** v1 trusts the `ScreenResult` it is handed and
  does not cryptographically verify it. Here "completed" means a terminal result stamped
  with a monotonic sequence before execution. In production, "completed" must mean a
  *signed* result from the screening service, verified before execution; that signature
  check is the boundary of v1, named here rather than hand-waved.
- **A correct screen run against a poisoned SDN list** (garbage in).
- **A compromised or colluding second approver**, and **multi-turn collusion** spread
  across several actions.
- **Clock skew below the abstraction.** The gate orders on a monotonic sequence, not
  wall-clock time.

It proves one thing well: a clean screen of the right party, against the pinned list
version, completed before the money moved, or the transfer is denied.
