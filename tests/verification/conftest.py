# START_MODULE_CONTRACT
# PURPOSE: Disposable repository fixtures for adversarial evidence tests.
# SCOPE: Synthetic files and local test key outside fixture root, no services.
# DEPENDS: pytest, standard library.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# repo - repo
# END_MODULE_MAP
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'tools/verification'
sys.path.insert(0, str(TOOLS))
import gate
import ci_check


@pytest.fixture
def repo(monkeypatch):
    root = Path(tempfile.mkdtemp(prefix='aura-coffee-audit-gate-fixture-'))
    keydir = Path(tempfile.mkdtemp(prefix='aura-coffee-audit-gate-key-'))
    monkeypatch.setenv('AURA_EVIDENCE_KEY', str(keydir / 'key'))
    bundle = root / '.grace/changes/active/C-TEST'
    bundle.mkdir(parents=True)
    for name, tag in [('spec', 'GraceChangeSpec'), ('plan', 'GraceChangePlan')]:
        content = '<TargetAssertions><MustPassCommand><Command>python3 tools/verification/gate.py check --change C-TEST --evidence-dir .verification-results/C-TEST</Command></MustPassCommand></TargetAssertions>' if name == 'plan' else '<Summary>test</Summary>'
        (bundle / f'{name}.xml').write_text(f'<{tag} status="approved"><C-TEST>{content}</C-TEST></{tag}>')
    (root / 'tests').mkdir()
    (root / 'tests/test_sample.py').write_text('def test_ok():\n    assert 2 + 2 == 4\n')
    (root / 'pytest.ini').write_text('[pytest]\n')
    shutil.copytree(TOOLS, root / 'tools/verification', ignore=shutil.ignore_patterns('__pycache__'))
    policy = {'version': 1, 'changes': {'C-TEST': {'scope': ['tests', '.grace'], 'non_applicability': 'Synthetic tool contract; no business/LDD operation.', 'scenarios': [{'id': 'S-ONE', 'adapter': 'pytest', 'layer': 'tool-contract', 'cwd': '.', 'selectors': ['tests/test_sample.py'], 'profiles': ['default'], 'tests': ['tests/test_sample.py::test_ok'], 'timeout': 15, 'mocks': []}]}}}
    (root / 'tools/verification/policy.json').write_text(json.dumps(policy))
    yield root
    # Fixtures contain synthetic material only; retained temporarily for diagnostics.


def _run(repo):
    return gate._run(repo, 'C-TEST', repo / '.verification-results/C-TEST')


def _check(repo):
    return gate._check(repo, 'C-TEST', repo / '.verification-results/C-TEST')


def _report(repo):
    return repo / '.verification-results/C-TEST/S-ONE.json'


def _receipt(repo):
    return repo / '.verification-results/C-TEST/receipt.json'


def _edit_json(path, edit):
    value = json.loads(path.read_text())
    edit(value)
    path.write_text(json.dumps(value))
