# START_MODULE_CONTRACT
# PURPOSE: Exercise trusted-base CI aggregation and lifecycle rejection without network.
# SCOPE: Synthetic contexts and candidate snapshots; no GitHub mutations.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_positive_ci - test positive ci
# test_bad_producer - test bad producer
# test_old_ci_context - test old ci context
# test_candidate_cannot_weaken_checker - test candidate cannot weaken checker
# test_missing_active_bundle_detected_from_base - test missing active bundle detected from base
# test_new_applied_bundle_requires_evidence - test new applied bundle requires evidence
# END_MODULE_MAP
import json
import shutil
from pathlib import Path
import tempfile
import pytest
from conftest import gate, ci_check, _run, _edit_json


def _setup(repo):
    base = Path(tempfile.mkdtemp(prefix='aura-coffee-audit-gate-base-')) / 'base'
    shutil.copytree(repo, base)
    _run(repo)
    context = {'candidate_sha': 'a' * 40, 'base_sha': 'b' * 40, 'run_id': '100', 'run_attempt': '1'}
    evidence = repo / '.verification-results'
    (evidence / 'ci-context.json').write_text(json.dumps(context))
    needs = {'full-gate': {'result': 'success'}, 'evidence-producer': {'result': 'success'}}
    return base, evidence, context, needs


def test_positive_ci(repo):
    base, ev, ctx, needs = _setup(repo)
    assert ci_check._verify(base, repo, ev, ctx, needs)['status'] == 'passed'


@pytest.mark.parametrize('state', ['failure', 'skipped', 'cancelled', 'timed_out', 'missing'])
def test_bad_producer(repo, state):
    base, ev, ctx, needs = _setup(repo)
    if state == 'missing': del needs['evidence-producer']
    else: needs['evidence-producer']['result'] = state
    with pytest.raises(gate._Denied, match='CI_PRODUCER_INCOMPLETE'): ci_check._verify(base, repo, ev, ctx, needs)


def test_old_ci_context(repo):
    base, ev, ctx, needs = _setup(repo)
    ctx['candidate_sha'] = 'c' * 40
    with pytest.raises(gate._Denied, match='WRONG_CI_CONTEXT'): ci_check._verify(base, repo, ev, ctx, needs)


def test_candidate_cannot_weaken_checker(repo):
    base, ev, ctx, needs = _setup(repo)
    (repo / 'tools/verification/gate.py').write_text('raise SystemExit(0)')
    with pytest.raises(gate._Denied, match='TRUST_BASE_CHANGE_REQUIRES_BOOTSTRAP'): ci_check._verify(base, repo, ev, ctx, needs)


def test_missing_active_bundle_detected_from_base(repo):
    base, ev, ctx, needs = _setup(repo)
    shutil.rmtree(repo / '.grace/changes/active/C-TEST')
    with pytest.raises(gate._Denied): ci_check._verify(base, repo, ev, ctx, needs)


def test_new_applied_bundle_requires_evidence(repo):
    base, ev, ctx, needs = _setup(repo)
    p = repo / '.grace/changes/archive/C-OTHER';p.mkdir(parents=True)
    for name in ['spec', 'plan']:
        (p / (name+'.xml')).write_text(f'<x status="applied"><C-OTHER /></x>')
    with pytest.raises(gate._Denied, match='UNPROVED_LIFECYCLE_TRANSITION'): ci_check._lifecycle(base, repo, {'C-TEST'})
