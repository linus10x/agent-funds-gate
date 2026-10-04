# agent-funds-gate

A small, runnable, fail-closed control: **a value-moving agent action is denied unless a version-pinned OFAC SDN screen *completed before* the transfer executed.** I tested the gate against the race it is meant to stop, and it denies it.

## What broke (the defeat, first)

An agent fires a $250,000 transfer at sequence 10. The OFAC screen for the same party does not resolve until sequence 15 — *after* the money already moved. A naive check asks only "was a screen run?" and there is a clear screen result sitting there, so it passes. The payment to a blocked party shipped.

```
[A] naive gate   -> ALLOW  ($250,000 sent; screen had not completed)
[B] this gate    -> DENY   {rule_cite: "31 CFR 501.603/501.604; strict liability under
                                        IEEPA, 50 U.S.C. 1705",
                            failing_assertion: "screen_completion_precedes_execution"}
```

The gate's whole value is the ordering check. The test proves it.

## Run it in 90 seconds

```bash
pytest                 # 19 tests green (src is on the path via pyproject)
python demo/demo.py    # the defeat, then the gate -- no install needed
```

(`pip install -e .` only if you want to import `agent_funds_gate` from elsewhere.)

## What this enforces

A transfer is `ALLOW` only if all hold, else `DENY` with the failed assertion named:
1. the inputs are well-formed — a real screen object and a valid positive sequence (`screen_malformed` / `transfer_seq_invalid` / `seq_out_of_range`); malformed input fails closed, it never raises,
2. a screen is present (`screen_present`),
3. it is not an SDN hit (`sdn_hit`) and did not error (`screen_error`),
4. it is **about the party being paid** — `screen.subject == subject` (`screen_subject_mismatch`); a clean screen of a different party does not authorize the transfer,
5. it **completed before** the transfer fired — `completed_seq < transfer_seq` (`screen_completion_precedes_execution`),
6. it ran against the pinned SDN-list version (`sdn_version_pinned`),
7. its status is positively `CLEAR` (`screen_not_clear`) — ALLOW is affirmed, never reached by falling through.

The decision is a structured object — `{decision, rule_cite, failing_assertion, sdn_list_version, evidence}` — so it reads like a control, not a print statement. No SDN list is bundled; a deployer wires its own version-pinned list. The repo ships a tiny synthetic fixture for the tests only.

## What this does NOT catch

The full, authoritative scope-limit list lives in
[CONTROL_STATEMENT.md](CONTROL_STATEMENT.md#what-this-does-not-catch-scope-limits) so the
two never drift. In short: it trusts the screen object and the SDN list it is handed (a
forged or unsigned result, or a poisoned list, defeats it), it does no name or fuzzy
matching, no 50%-rule ownership, no license determinations, and no non-payment actions. It
does not catch a compromised second approver or multi-turn collusion, and it orders on a
monotonic sequence, not wall-clock time.

## Verify the polarity yourself (60 seconds)

The claim is falsifiable. Strip the ordering enforcement and the centerpiece test must turn red:

```bash
# Comment out the ORDERING_ASSERTION check in src/agent_funds_gate/gate.py, then:
pytest tests/test_gate.py::test_race_screen_resolves_after_transfer_denies
# -> FAILS. With the gate removed, the race is allowed again.
```

`test_gate_removed_lets_race_through` shows the same hole from the other side: in `naive_mode` the race is `ALLOW` on purpose.

## A note on honesty

This repo demonstrates a *designed* failure mode and the control that closes it. It makes no claim that the gate caught a real production incident — it didn't, and inventing one would be the opposite of the point. The test below is the assertion that closes it.

## License

MIT.
