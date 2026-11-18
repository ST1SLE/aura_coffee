# START_MODULE_CONTRACT
# PURPOSE: Reproduce concrete bypasses found by independent review.
# SCOPE: Synthetic repositories and subprocess checker, no business services.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_shell_prefix_cannot_replace_leaf - test shell prefix cannot replace leaf
# test_nested_exclusion_name_is_an_input - test nested exclusion name is an input
# test_applied_revalidation_is_not_closure - test applied revalidation is not closure
# test_missing_report_subprocess_rejects - test missing report subprocess rejects
# test_candidate_cannot_replace_trusted_test_with_pass - test candidate cannot replace trusted test with pass
# test_invalid_report_removed_even_on_parse_failure - test invalid report removed even on parse failure
# test_unchecked_bytecode_cannot_forge_producer - test unchecked bytecode cannot forge producer
# test_receipt_records_actual_pytest_version - test receipt records actual pytest version
# END_MODULE_MAP
import json
import subprocess
import sys
import pytest
from conftest import gate, ci_check, _run, _check, _edit_json
from test_lifecycle import _apply
from test_ci import _setup


@pytest.mark.parametrize('command', ['true # ', 'echo ', 'false || '])
def test_shell_prefix_cannot_replace_leaf(repo, command):
    p = repo / '.grace/changes/active/C-TEST/plan.xml'
    p.write_text(p.read_text().replace('<Command>python3', '<Command>' + command + 'python3'))
    with pytest.raises(gate._Denied, match='MISSING_GATE_ASSERTION'): _run(repo)


@pytest.mark.parametrize('name', ['node_modules', '.verification-results', '.env-stuff'])
def test_nested_exclusion_name_is_an_input(repo, name):
    p = repo / 'tests' / name / 'business.txt';p.parent.mkdir()
    p.write_text('before')
    _run(repo)
    p.write_text('after')
    with pytest.raises(gate._Denied, match='STALE_EVIDENCE'): _check(repo)


def test_applied_revalidation_is_not_closure(repo):
    _apply(repo)
    result = gate._run(repo, 'C-TEST', repo / '.verification-results/C-TEST', continuous=True)
    assert result['status'] == 'passed'
    receipt = json.loads((repo / '.verification-results/C-TEST/receipt.json').read_text())
    assert receipt['payload']['kind'] == 'continuous'
    assert receipt['payload']['started_status'] == 'applied'


def test_missing_report_subprocess_rejects(repo):
    p = subprocess.run([sys.executable, str(repo / 'tools/verification/gate.py'), 'check', '--change', 'C-TEST', '--evidence-dir', '.verification-results/C-TEST'], cwd=repo, capture_output=True, text=True)
    assert p.returncode == 1
    assert json.loads(p.stdout)['reason'] == 'MISSING_REPORT'


def test_candidate_cannot_replace_trusted_test_with_pass(repo):
    base, ev, ctx, needs = _setup(repo)
    (repo / 'tests/test_sample.py').write_text('def test_ok():\n    pass\n')
    with pytest.raises(gate._Denied, match='TRUST_BASE_CHANGE_REQUIRES_BOOTSTRAP'):
        ci_check._verify(base, repo, ev, ctx, needs)


def test_invalid_report_removed_even_on_parse_failure(repo, monkeypatch):
    def execute(argv, cwd, env, budget):
        from pathlib import Path
        Path(env['AURA_GATE_REPORT']).write_text('private diagnostic malformed')
        return 0, 0.01
    monkeypatch.setattr(gate, '_execute', execute)
    with pytest.raises(gate._Denied, match='MALFORMED_REPORT'): _run(repo)
    assert not list((repo / '.verification-results').rglob('*.json'))


def test_unchecked_bytecode_cannot_forge_producer(repo, tmp_path):
    import importlib.util
    import py_compile
    (repo / 'tests/test_sample.py').write_text('import gate\ndef test_ok():\n    assert False\n')
    alternate = tmp_path / 'alternate.py'
    alternate.write_text("import os,json\nfrom pathlib import Path\nPath(os.environ['AURA_GATE_REPORT']).write_text(json.dumps({'version':1,'collected':['tests/test_sample.py::test_ok'],'results':[{'id':'tests/test_sample.py::test_ok','profile':'default','status':'passed','retry':0}]}))\nos._exit(0)\n")
    # Match the reviewed bypass: ordinary gate import, not pytest-rewritten plugin.
    cache = importlib.util.cache_from_source(str(repo / 'tools/verification/gate.py'))
    py_compile.compile(str(alternate), cfile=cache, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    with pytest.raises(gate._Denied, match='PRODUCER_FAILED'):
        _run(repo)


def test_receipt_records_actual_pytest_version(repo):
    import importlib.metadata
    _run(repo)
    payload = json.loads((repo / '.verification-results/C-TEST/receipt.json').read_text())['payload']
    assert payload['producers'][0]['versions']['pytest'] == importlib.metadata.version('pytest')
