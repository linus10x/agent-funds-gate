# agent-funds-gate

A small, runnable, fail-closed control: **a value-moving agent action is denied unless a version-pinned OFAC SDN screen *completed before* the transfer executed.** We attacked our own gate and showed it holds.

## What broke (the defeat, first)

An agent fires a $250,000 transfer at sequence 10. The OFAC screen for the same party does not resolve until sequence 15 — *after* the money already moved. A naive check asks only "was a screen run?" and there is a clear screen result sitting there, so it passes. The payment to a blocked party shipped.

```
[A] naive gate   -> ALLOW  ($250,000 sent; screen had not completed)
[B] this gate    -> DENY   {rule_cite: "31 CFR Chapter V (OFAC)...",
                            failing_assertion: "screen_completion_precedes_execution"}
```

The gate's whole value is the ordering check. The test proves it.

## Run it in 90 seconds

```bash
pip install -e .
pytest                 # 9 tests, all green
python demo/demo.py    # the defeat, then the gate
```

## What this enforces

A transfer is `ALLOW` only if all hold, else `DENY` with the failed assertion named:
1. a screen is present (`screen_present`),
2. it is not an SDN hit (`sdn_hit`) and did not error (`screen_error`),
3. it **completed before** the transfer fired — `completed_seq < transfer_seq` (`screen_completion_precedes_execution`),
4. it ran against the pinned SDN-list version (`sdn_version_pinned`).

The decision is a structured object — `{decision, rule_cite, failing_assertion, sdn_list_version, evidence}` — so it reads like a control, not a print statement. No SDN list is bundled; a deployer wires its own version-pinned list. The repo ships a tiny synthetic fixture for the tests only.

## What this does NOT catch

- A **compromised or colluding second approver**.
- **Multi-turn collusion** spread across several actions.
- A **forged screen result.** v1 trusts the `ScreenResult` it is handed and does not cryptographically verify it. Here, "the screen COMPLETED" means a terminal result stamped with a monotonic sequence before execution. In production, "completed" must mean a *signed* result from the screening service, verified before execution — that signature check is the boundary of v1, named here rather than hand-waved.
- A correct screen against a **poisoned SDN list** (garbage in).
- Sub-abstraction **clock skew** — the gate uses a monotonic sequence, not wall-clock time.

## Verify the polarity yourself (60 seconds)

The claim is falsifiable. Strip the ordering enforcement and the centerpiece test must turn red:

```bash
# Comment out the ORDERING_ASSERTION check in src/agent_funds_gate/gate.py, then:
pytest tests/test_gate.py::test_race_screen_resolves_after_transfer_denies
# -> FAILS. With the gate removed, the race is allowed again.
```

`test_gate_removed_lets_race_through` shows the same hole from the other side: in `naive_mode` the race is `ALLOW` on purpose.

## A note on honesty

This repo demonstrates a *designed* failure mode and the control that closes it. It makes no claim that the gate caught a real production incident — it didn't, and inventing one would be the opposite of the point. We attacked our own gate; here is the assertion that holds it.

## License

MIT.
