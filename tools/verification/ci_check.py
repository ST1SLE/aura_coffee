#!/usr/bin/env python3
# START_MODULE_CONTRACT
# PURPOSE: Independent base-policy CI acceptance and lifecycle comparison; no candidate execution.
# SCOPE: Bounded report parsing, exact input identity, protected files, job context and transitions.
# DEPENDS: gate helpers from this trusted checkout; stdlib.
# LINKS: C-REQUIRED-EVIDENCE-GATE, .grace/verification/main.xml
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# main - Evaluate trusted-base CI evidence without importing candidate code
# END_MODULE_MAP
import argparse
import json
from pathlib import Path
import os

import closure
import gate


def _inventory(root):
    result = {}
    for phase in ('active', 'archive'):
        directory = root / '.grace/changes' / phase
        if not directory.exists():
            continue
        for p in directory.iterdir():
            if p.is_dir() and p.name.startswith('C-'):
                gate._require(p.name not in result, 'DUPLICATE_BUNDLE')
                states = tuple(gate._xml(p / f).get('status') for f in ('spec.xml', 'plan.xml') if (p / f).is_file())
                result[p.name] = (phase, states)
    return result


def _lifecycle(base, candidate, proved):
    old, new = _inventory(base), _inventory(candidate)
    for change, state in old.items():
        gate._require(change in new, 'BUNDLE_DISAPPEARED')
        if state != new[change]:
            gate._require(change in proved, 'UNPROVED_LIFECYCLE_TRANSITION')
    for change, state in new.items():
        if change not in old and (state[0] == 'archive' or 'applied' in state[1]):
            gate._require(change in proved, 'UNPROVED_LIFECYCLE_TRANSITION')


def _first_closure(base, candidate, change):
    bundle = gate._bundle(candidate, change)
    old = gate._bundle(base, change)
    return (gate._xml(bundle / 'plan.xml').get('status') == 'applied'
            and gate._xml(old / 'plan.xml').get('status') != 'applied')


def _manifest_authority(evidence, change):
    return gate._json(evidence / 'closure-authority.json')[change]


def _protected(base, candidate):
    # Trust changes are intentionally a separate bootstrap operation. No candidate exemption flag.
    paths = ['tools/verification', 'tests/verification', '.github/workflows', '.grace/context/principles.xml',
             'tests', 'web/admin', 'web/customer', 'packages/shared/tests',
             'services/core-api/tests', 'services/payment-worker/tests', 'services/sms-worker/tests']
    # Initial registry is tooling-only: frontend changes require a separately reviewed
    # policy expansion. Never let a candidate redefine its own tests/configuration.
    change = next(iter(gate._json(base / 'tools/verification/policy.json')['changes']))
    a, b = gate._snapshot(base, change), gate._snapshot(candidate, change)
    selected = lambda data: {p: v for p, v in data.items() if any(p == n or p.startswith(n + '/') for n in paths)}
    gate._require(selected(a) == selected(b), 'TRUST_BASE_CHANGE_REQUIRES_BOOTSTRAP')


def _verify(base, candidate, evidence, context, needs, resolve=None):
    gate._require(all(isinstance(context.get(k), str) and context[k] for k in ('candidate_sha', 'base_sha', 'run_id', 'run_attempt')), 'MISSING_CI_CONTEXT')
    gate._require(set(needs) == {'full-gate', 'evidence-producer'} and all(v.get('result') == 'success' for v in needs.values()), 'CI_PRODUCER_INCOMPLETE')
    gate._require((base / 'tools/verification/policy.json').is_file(), 'TRUST_BASE_NOT_BOOTSTRAPPED')
    _protected(base, candidate)
    policy = gate._json(base / 'tools/verification/policy.json')
    manifest = gate._json(evidence / 'ci-context.json')
    gate._require(manifest == context, 'WRONG_CI_CONTEXT')
    changes = sorted(policy['changes'])
    # Every known obligation executes; no path-filter fast-pass in the first increment.
    proved = set()
    for change in changes:
        spec = gate._policy(base, change)
        receipt = gate._json(evidence / change / 'receipt.json')
        payload = receipt.get('payload', {})
        gate._require(payload.get('change') == change and payload.get('started_status') in ('approved', 'applied'), 'WRONG_CONTEXT')
        gate._require(payload.get('snapshot') == gate._snapshot(candidate, change), 'STALE_EVIDENCE')
        gate._require(payload.get('policy') == gate._digest(gate._canonical(spec)), 'POLICY_CHANGED')
        producers = payload.get('producers', [])
        gate._require(len(producers) == len(spec['scenarios']) and len({p['scenario'] for p in producers}) == len(producers), 'MISSING_OR_DUPLICATE_SCENARIO')
        by_id = {p['scenario']: p for p in producers}
        for s in spec['scenarios']:
            gate._require(s['id'] in by_id, 'MISSING_SCENARIO')
            p = by_id[s['id']]
            gate._validate_versions(s['adapter'], p.get('versions'))
            gate._require(p['adapter'] == s['adapter'] and p['layer'] == s['layer'] and p['mocks'] == s['mocks'], 'WRONG_LAYER')
            artifact = gate._inside(evidence / change, p['artifact'])
            doc = gate._json(artifact)
            gate._require(gate._digest(artifact.read_bytes()) == p['sha256'], 'ARTIFACT_TAMPERED')
            gate._require(p['exit'] == 0, 'PRODUCER_FAILED')
            gate._validate_rows(s, doc['collected'], doc['results'])
        proved.add(change)
    old = gate._snapshot(base, changes[0])
    new = gate._snapshot(candidate, changes[0])
    scopes = [scope for c in policy['changes'].values() for scope in c['scope']]
    changed = {p for p in set(old) | set(new) if old.get(p) != new.get(p)}
    gate._require(all(any(p == scope or p.startswith(scope.rstrip('/') + '/') for scope in scopes) for p in changed), 'UNKNOWN_CHANGED_SCOPE')
    closure_proved = set()
    for change in proved:
        if _first_closure(base, candidate, change):
            gate._require(not closure_proved and resolve is not None, 'CLOSURE_REQUIRES_PRIOR_APPROVED_EVIDENCE')
            payload = gate._json(evidence / change / 'receipt.json')['payload']
            gate._require((payload['kind'], payload['started_status']) == ('continuous', 'applied'), 'FRESH_APPLIED_RUN_REQUIRED')
            gate._require(resolve(base, candidate, change, candidate) == _manifest_authority(evidence, change), 'WRONG_AUTHORIZATION')
            closure_proved.add(change)
    _lifecycle(base, candidate, closure_proved)
    return {'status': 'passed', 'scope': 'ci-artifacts', 'changes': sorted(proved)}


# START_CONTRACT: main
# PURPOSE: Execute the scoped evidence CLI entry point.
# INPUTS: CLI arguments and environment — validated by the entry point
# OUTPUTS: Exit status or completion; invalid evidence blocks
# SIDE_EFFECTS: Local evidence files and isolated subprocesses where applicable
# LINKS: C-REQUIRED-EVIDENCE-GATE, .grace/verification/main.xml
# END_CONTRACT: main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-root', required=True)
    parser.add_argument('--candidate-root', required=True)
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--issue', type=Path)
    args = parser.parse_args()
    try:
        context = {k: os.environ.get('AURA_' + k.upper(), '') for k in ('candidate_sha', 'base_sha', 'run_id', 'run_attempt')}
        needs = json.loads(os.environ.get('AURA_JOB_RESULTS', '{}'))
        out = _verify(Path(args.base_root), Path(args.candidate_root), Path(args.evidence_dir), context, needs, closure._resolve)
        if args.issue and os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
            base, candidate = Path(args.base_root), Path(args.candidate_root)
            approved = [c for c in out['changes'] if gate._xml(gate._bundle(candidate, c) / 'plan.xml').get('status') == 'approved']
            if len(approved) == 1:
                closure._issue(base, candidate, Path(args.evidence_dir), approved[0], args.issue)
        print(json.dumps(out))
        return 0
    except gate._Denied as e:
        print(json.dumps({'status': 'blocked', 'reason': e.code}))
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print(json.dumps({'status': 'blocked', 'reason': 'INVALID_CI_INPUT'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
