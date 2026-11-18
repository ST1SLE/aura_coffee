# START_MODULE_CONTRACT
# PURPOSE: Verify exact lifecycle normalization and bypass rejection.
# SCOPE: Synthetic approved/applied bundle fixtures.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_permitted_closure - test permitted closure
# test_closure_does_not_normalize_requirements - test closure does not normalize requirements
# test_cannot_generate_applied_evidence - test cannot generate applied evidence
# test_deleted_bundle - test deleted bundle
# test_deleted_gate_assertion - test deleted gate assertion
# END_MODULE_MAP
import shutil
import pytest
from conftest import gate, _run, _check


def _apply(root):
    old = root / '.grace/changes/active/C-TEST'
    for name in ['spec.xml', 'plan.xml']:
        p = old / name
        p.write_text(p.read_text().replace('status="approved"', 'status="applied"'))
    dest = root / '.grace/changes/archive/C-TEST'
    dest.parent.mkdir(exist_ok=True)
    old.rename(dest)
    return dest


def test_permitted_closure(repo):
    _run(repo)
    _apply(repo)
    assert _check(repo)['status'] == 'passed'


def test_closure_does_not_normalize_requirements(repo):
    _run(repo)
    p = _apply(repo) / 'spec.xml'
    p.write_text(p.read_text().replace('test</Summary>', 'weakened</Summary>'))
    with pytest.raises(gate._Denied, match='STALE_EVIDENCE'): _check(repo)


def test_cannot_generate_applied_evidence(repo):
    _apply(repo)
    with pytest.raises(gate._Denied, match='LIFECYCLE_BYPASS'): _run(repo)


def test_deleted_bundle(repo):
    _run(repo)
    shutil.rmtree(repo / '.grace/changes/active/C-TEST')
    with pytest.raises(gate._Denied, match='LIFECYCLE_BYPASS'): _check(repo)


def test_deleted_gate_assertion(repo):
    _run(repo)
    p = repo / '.grace/changes/active/C-TEST/plan.xml'
    p.write_text(p.read_text().replace('gate.py check', 'echo passed'))
    with pytest.raises(gate._Denied, match='MISSING_GATE_ASSERTION'): _check(repo)
