# START_MODULE_CONTRACT
# PURPOSE: Assert green unrelated tests cannot override a failed browser requirement.
# SCOPE: Synthetic producer reports; live Chromium witness is a separate acceptance run.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_green_unit_does_not_override_browser_failure - test green unit does not override browser failure
# test_missing_receipt_never_passes - test missing receipt never passes
# END_MODULE_MAP
import pytest
from conftest import gate


def test_green_unit_does_not_override_browser_failure():
    scenario = {'tests': ['admin in_delivery cancel availability'], 'profiles': ['desktop-ru','desktop-en','mobile-ru','mobile-en']}
    rows = [{'id': scenario['tests'][0], 'profile': p, 'status': 'failed', 'retry': 0} for p in scenario['profiles']]
    with pytest.raises(gate._Denied, match='REQUIRED_TEST_NOT_PASSED'):
        gate._validate_rows(scenario, [scenario['tests'][0]], rows)


def test_missing_receipt_never_passes(repo):
    with pytest.raises(gate._Denied, match='MISSING_REPORT'):
        gate._check(repo, 'C-TEST', repo / '.verification-results/C-TEST')
