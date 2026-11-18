# START_MODULE_CONTRACT
# PURPOSE: Verify runner report semantics independently of exit-code summaries.
# SCOPE: Synthetic Playwright and Vitest reports, profiles and retry states.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_playwright_rows - test playwright rows
# test_vitest_identity - test vitest identity
# test_zero_and_wrong_collection - test zero and wrong collection
# END_MODULE_MAP
import json
import pytest
from conftest import gate


@pytest.mark.parametrize('case', ['positive', 'skip', 'xfail', 'retry', 'missing-profile', 'duplicate'])
def test_playwright_rows(repo, case):
    test = {'projectName': 'desktop-en', 'expectedStatus': 'passed', 'status': 'expected', 'results': [{'status': 'passed', 'retry': 0}]}
    if case == 'skip': test['results'][0]['status'] = 'skipped'
    if case == 'xfail': test['expectedStatus'] = 'failed'
    if case == 'retry': test['results'].insert(0, {'status': 'failed', 'retry': 0})
    tests = [test, test] if case == 'duplicate' else [test]
    report = repo / 'pw.json'
    report.write_text(json.dumps({'suites': [{'specs': [{'file': 'a.spec.ts', 'title': 'required', 'tests': tests}]}]}))
    collected, rows = gate._parse('playwright', report, repo)
    scenario = {'tests': ['a.spec.ts::required'], 'profiles': ['desktop-en', 'mobile-en'] if case == 'missing-profile' else ['desktop-en']}
    if case == 'positive':
        gate._validate_rows(scenario, collected, rows)
    else:
        with pytest.raises(gate._Denied): gate._validate_rows(scenario, collected, rows)


def test_vitest_identity(repo):
    report = repo / 'vitest.json'
    report.write_text(json.dumps({'version': 1, 'collected': ['tests/x.test.ts::group case'], 'results': [{'id': 'tests/x.test.ts::group case', 'profile': 'default', 'status': 'passed', 'retry': 0}]}))
    collected, rows = gate._parse('vitest', report, repo)
    gate._validate_rows({'tests': ['tests/x.test.ts::group case'], 'profiles': ['default']}, collected, rows)


def test_zero_and_wrong_collection():
    for collected, rows in [([], []), (['wrong'], [{'id': 'wrong', 'profile': 'default', 'status': 'passed', 'retry': 0}])]:
        with pytest.raises(gate._Denied): gate._validate_rows({'tests': ['required'], 'profiles': ['default']}, collected, rows)
