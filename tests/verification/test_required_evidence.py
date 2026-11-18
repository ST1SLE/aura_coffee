# START_MODULE_CONTRACT
# PURPOSE: Independent subprocess acceptance and negative evidence contracts.
# SCOPE: Synthetic producer/receipt rejection, no application behavior edits.
# DEPENDS: pytest, gate fixture.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_positive_cli - test positive cli
# test_missing - test missing
# test_stale_inputs - test stale inputs
# test_tampered_artifact - test tampered artifact
# test_handwritten_report - test handwritten report
# test_failed_skipped_xfail_producer - test failed skipped xfail producer
# test_zero_collection - test zero collection
# test_during_run_change - test during run change
# test_timeout - test timeout
# test_wrong_policy_after_run - test wrong policy after run
# test_sensitive_log_not_persisted - test sensitive log not persisted
# test_external_artifact_path - test external artifact path
# END_MODULE_MAP
import json
import os
import subprocess
import sys

import pytest
from conftest import _run, _check, _report, _receipt, _edit_json, gate


def test_positive_cli(repo):
    args = [sys.executable, str(repo / 'tools/verification/gate.py'), 'run', '--change', 'C-TEST', '--evidence-dir', '.verification-results/C-TEST']
    p = subprocess.run(args, cwd=repo, capture_output=True)
    assert p.returncode == 0, p.stdout
    args[2] = 'check'
    p = subprocess.run(args, cwd=repo, capture_output=True)
    assert p.returncode == 0 and json.loads(p.stdout)['scope'] == 'local-only'


@pytest.mark.parametrize('kind', ['receipt', 'artifact'])
def test_missing(repo, kind):
    _run(repo)
    (_receipt(repo) if kind == 'receipt' else _report(repo)).unlink()
    with pytest.raises(gate._Denied, match='MISSING_REPORT'):
        _check(repo)


@pytest.mark.parametrize('path', ['tests/test_sample.py', 'requirements.txt', 'app.py'])
def test_stale_inputs(repo, path):
    _run(repo)
    (repo / path).write_text('changed\n')
    with pytest.raises(gate._Denied, match='STALE_EVIDENCE'):
        _check(repo)


def test_tampered_artifact(repo):
    _run(repo)
    _edit_json(_report(repo), lambda x: x.update(results=[]))
    with pytest.raises(gate._Denied, match='ARTIFACT_TAMPERED'):
        _check(repo)


def test_handwritten_report(repo):
    _run(repo)
    _edit_json(_receipt(repo), lambda x: x['payload'].update(run_id='forged'))
    with pytest.raises(gate._Denied, match='TAMPERED_RECEIPT'):
        _check(repo)


@pytest.mark.parametrize('body', ['import pytest\n@pytest.mark.skip\ndef test_ok(): pass\n', 'import pytest\n@pytest.mark.xfail\ndef test_ok(): assert False\n', 'def test_ok(): assert False\n'])
def test_failed_skipped_xfail_producer(repo, body):
    (repo / 'tests/test_sample.py').write_text(body)
    with pytest.raises(gate._Denied):
        _run(repo)


def test_zero_collection(repo):
    (repo / 'tests/test_sample.py').write_text('value=1\n')
    with pytest.raises(gate._Denied):
        _run(repo)


def test_during_run_change(repo):
    (repo / 'tests/test_sample.py').write_text('from pathlib import Path\ndef test_ok():\n    Path("changed.py").write_text("x=1")\n')
    with pytest.raises(gate._Denied, match='INPUT_CHANGED_DURING_RUN'):
        _run(repo)


def test_timeout(repo):
    (repo / 'tests/test_sample.py').write_text('import time\ndef test_ok(): time.sleep(10)\n')
    _edit_json(repo / 'tools/verification/policy.json', lambda x: x['changes']['C-TEST']['scenarios'][0].update(timeout=1))
    with pytest.raises(gate._Denied, match='PRODUCER_TIMEOUT'):
        _run(repo)


def test_wrong_policy_after_run(repo):
    _run(repo)
    _edit_json(repo / 'tools/verification/policy.json', lambda x: x['changes']['C-TEST']['scenarios'][0].update(mocks=['different']))
    with pytest.raises(gate._Denied, match='POLICY_CHANGED'):
        _check(repo)


def test_sensitive_log_not_persisted(repo):
    (repo / 'tests/test_sample.py').write_text('def test_ok():\n    print("private-canary-not-for-evidence")\n    assert True\n')
    _run(repo)
    for path in (repo / '.verification-results').rglob('*'):
        if path.is_file():
            assert 'private-canary-not-for-evidence' not in path.read_text()


def test_external_artifact_path(repo):
    with pytest.raises(gate._Denied, match='UNSAFE_PATH'):
        gate._inside(repo, '../external.json')
