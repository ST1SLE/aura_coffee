# Required evidence gate

Initial registry covers C-REQUIRED-EVIDENCE-GATE tooling contracts only. It is
not a claim of product coverage. Unknown changed scopes block CI. Adding
business/browser/LDD obligations requires reviewed trusted-policy expansion;
the backend-LDD adapter intentionally blocks until that deferred task exists.

Use a disposable `/tmp/aura-coffee-audit-*` copy without production `.env`,
services or credentials. Install locked dependencies there. With Python 3.12:

```
python3 tools/verification/gate.py run --change C-REQUIRED-EVIDENCE-GATE --evidence-dir .verification-results/C-REQUIRED-EVIDENCE-GATE
python3 tools/verification/gate.py check --change C-REQUIRED-EVIDENCE-GATE --evidence-dir .verification-results/C-REQUIRED-EVIDENCE-GATE
```

`run` requires a fresh output directory and an active approved bundle. It
captures the exact input identity before/after, executes fixed obligations and
signs sanitized results with a local key outside the checkout. `check` neither
starts services nor reruns tests. Root spec/plan status approved→applied and
this bundle's active→archive move alone preserve identity. All other edits
invalidate evidence. No key/evidence is committed. The local signature guards
against accidentally authored/tampered JSON, not a malicious process with the
same user permissions. Temporary native browser reports are private and removed
even on timeout/parse failure; exported rows contain identities and outcomes only.

Budgets: whole pilot 900 seconds, contract leaf 120 seconds, evidence leaf
30 seconds; unchanged Full Verification Gate 60 minutes. A timeout blocks.
Do not increase limits automatically. Skip, expected-failure and retry outcomes
cannot satisfy a required test. Playwright evidence includes file, suite, test
and each required locale/viewport. Fresh frontend builds precede browser runs.
API mocks remain browser evidence only, never backend authorization or LDD proof.

## CI trust and activation

The additional producer uses base tooling, fresh candidate content, no repository
secrets and a read-only job token. Required Evidence Gate runs separately from
the trusted base and never imports candidate modules. It rejects non-success
dependencies, protected-file differences, unknown changed scopes, missing or
stale reports. CI artifacts must come from that workflow's producer in the same
run and attempt; local receipts are never imported as CI evidence. Context JSON
alone is not an attestation outside this workflow.

Repository files cannot enforce GitHub protections by themselves. Before remote
activation the owner must review/bootstrap the trusted base, protect workflow,
policy and test definitions, require both named checks, and restrict bypass.
Absent that protected base the producer/checker deliberately fail; there is no
candidate-controlled bootstrap switch. The first increment protects the entire
frontend tree to prevent weakening future test/config inputs. Scope expansion
must review that conservative boundary explicitly.

Continuous CI revalidation of an already applied base bundle is allowed but is
not closure evidence. A newly applied candidate cannot invent an earlier
approved run. First closure of one registered bundle in a same-repository pull request requires
the previous successful approved run on the same PR and base, an ancestor head,
and byte-identical Git trees after the two root status edits and bundle move.
The final job records the SHA-256 of authorization.json after verifying every
producer. Its successful step binds the digest to the exact attempt. Both the
preparation step and final checker retrieve the bounded artifact through the
GitHub API with a step-scoped read token, verify its digest and issuer, and reject
missing, ambiguous or expired (over seven days) proof. The producer independently
executes the applied candidate; its fresh results remain mandatory.
First closure on push stays blocked. Rollback restores that same denial for PRs.
Activation requires owner-reviewed bootstrap of this tooling on the trusted base
and real positive/negative PR probes, including the post-merge push behavior. Local approved→applied/archive verification is tested and supported.

No GitHub settings have been activated by creating these files. No business bug
is repaired by a successful negative test of the checker. The known admin
IN_DELIVERY cancellation witness must remain a failed product obligation.
