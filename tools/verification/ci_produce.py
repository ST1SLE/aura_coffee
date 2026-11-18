#!/usr/bin/env python3
# START_MODULE_CONTRACT
# PURPOSE: Produce fresh evidence with trusted base tooling in an unprivileged disposable job.
# SCOPE: No secrets, no external services; current registry is tooling-only.
# DEPENDS: gate, ci_check, pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# main - Produce fresh isolated evidence using trusted base policy
# END_MODULE_MAP
import argparse
import json
import os
from pathlib import Path
import gate
import ci_check
import closure


# START_CONTRACT: main
# PURPOSE: Execute the scoped evidence CLI entry point.
# INPUTS: CLI arguments and environment — validated by the entry point
# OUTPUTS: Exit status or completion; invalid evidence blocks
# SIDE_EFFECTS: Local evidence files and isolated subprocesses where applicable
# LINKS: C-REQUIRED-EVIDENCE-GATE, .grace/verification/main.xml
# END_CONTRACT: main
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate-root', required=True)
    parser.add_argument('--prepare', type=Path, help='Git checkout for read-only prior-run verification')
    parser.add_argument('--authority-file', type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    candidate = Path(args.candidate_root).resolve()
    ci_check._protected(base, candidate)
    policy = gate._json(base / 'tools/verification/policy.json')
    closing = [c for c in policy['changes'] if ci_check._first_closure(base, candidate, c)]
    gate._require(len(closing) <= 1, 'MULTIPLE_CLOSURES')
    if args.prepare:
        authorities = {c: closure._resolve(base, candidate, c, args.prepare) for c in closing}
        args.authority_file.write_text(json.dumps(authorities))
        return 0
    authorities = gate._json(args.authority_file) if args.authority_file else {}
    gate._require(set(authorities) == set(closing), 'CLOSURE_REQUIRES_PRIOR_APPROVED_EVIDENCE')
    for change in policy['changes']:
        state = gate._xml(gate._bundle(candidate, change) / 'plan.xml').get('status')
        gate._run(candidate, change, candidate / '.verification-results' / change, continuous=state == 'applied')
    (candidate / '.verification-results/closure-authority.json').write_text(json.dumps(authorities))
    context = {k: os.environ['AURA_' + k.upper()] for k in ('candidate_sha', 'base_sha', 'run_id', 'run_attempt')}
    (candidate / '.verification-results/ci-context.json').write_text(json.dumps(context))


if __name__ == '__main__':
    try:
        main()
    except (gate._Denied, OSError, ValueError, KeyError):
        print('Evidence producer blocked; no successful artifact is authoritative.')
        raise SystemExit(1)
