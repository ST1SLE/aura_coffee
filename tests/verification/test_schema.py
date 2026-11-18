# START_MODULE_CONTRACT
# PURPOSE: Reject unsupported or weakening obligation definitions.
# SCOPE: Policy fixtures only.
# DEPENDS: pytest.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# test_bad_schema - test bad schema
# test_duplicate_scenario - test duplicate scenario
# test_duplicate_json_key - test duplicate json key
# END_MODULE_MAP
import pytest
from conftest import gate, _edit_json


@pytest.mark.parametrize('field,value,code', [('tests', [], 'EMPTY_OR_DUPLICATE_SELECTION'), ('profiles', ['ru', 'ru'], 'EMPTY_OR_DUPLICATE_SELECTION'), ('adapter', 'shell', 'UNSUPPORTED_ADAPTER'), ('layer', 'browser', 'WRONG_LAYER'), ('layer', 'backend-ldd', 'LDD_ADAPTER_NOT_IMPLEMENTED'), ('timeout', 0, 'INVALID_BUDGET'), ('selectors', ['--passWithNoTests'], 'UNSAFE_SELECTOR')])
def test_bad_schema(repo, field, value, code):
    _edit_json(repo / 'tools/verification/policy.json', lambda x: x['changes']['C-TEST']['scenarios'][0].update({field: value}))
    with pytest.raises(gate._Denied, match=code):
        gate._policy(repo, 'C-TEST')


def test_duplicate_scenario(repo):
    _edit_json(repo / 'tools/verification/policy.json', lambda x: x['changes']['C-TEST']['scenarios'].append(x['changes']['C-TEST']['scenarios'][0]))
    with pytest.raises(gate._Denied, match='DUPLICATE_SCENARIO'):
        gate._policy(repo, 'C-TEST')


def test_duplicate_json_key(repo):
    p = repo / 'duplicate.json'
    p.write_text('{"status":"failed","status":"passed"}')
    with pytest.raises(gate._Denied, match='DUPLICATE_KEY'):
        gate._json(p)
