# START_MODULE_CONTRACT
# PURPOSE: Record pytest collection and actual per-test outcomes without captured payloads.
# SCOPE: Gate producer hook; skip/xfail/setup/teardown failures are never pass.
# DEPENDS: pytest runtime hook protocol, json, os, pathlib.
# LINKS: C-REQUIRED-EVIDENCE-GATE
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# pytest_collection_finish - pytest collection finish
# pytest_runtest_logreport - pytest runtest logreport
# pytest_sessionfinish - pytest sessionfinish
# END_MODULE_MAP
import json
import os
from pathlib import Path

_collected = []
_results = {}


# START_CONTRACT: pytest_collection_finish
# PURPOSE: Capture exact selected node IDs after collection.
# INPUTS: session: pytest session
# OUTPUTS: None
# SIDE_EFFECTS: updates producer collection memory
# LINKS: C-REQUIRED-EVIDENCE-GATE
# END_CONTRACT: pytest_collection_finish
def pytest_collection_finish(session):
    _collected[:] = [item.nodeid for item in session.items]


# START_CONTRACT: pytest_runtest_logreport
# PURPOSE: Accumulate actual test outcomes with setup and teardown failures preserved.
# INPUTS: report: pytest TestReport
# OUTPUTS: None
# SIDE_EFFECTS: updates producer result memory
# LINKS: C-REQUIRED-EVIDENCE-GATE
# END_CONTRACT: pytest_runtest_logreport
def pytest_runtest_logreport(report):
    row = _results.setdefault(report.nodeid, {'id': report.nodeid, 'profile': 'default', 'status': 'not-run', 'retry': 0})
    if report.failed or report.skipped or hasattr(report, 'wasxfail') or report.outcome == 'rerun':
        row['status'] = 'not-passed'
    elif report.when == 'call' and row['status'] != 'not-passed':
        if row['status'] == 'passed':
            row['retry'] += 1
        row['status'] = 'passed'


# START_CONTRACT: pytest_sessionfinish
# PURPOSE: Persist bounded structural results without messages, captured logs or PII.
# INPUTS: session: pytest session; exitstatus: runner exit
# OUTPUTS: None
# SIDE_EFFECTS: writes configured evidence report
# LINKS: C-REQUIRED-EVIDENCE-GATE
# END_CONTRACT: pytest_sessionfinish
def pytest_sessionfinish(session, exitstatus):
    Path(os.environ['AURA_GATE_REPORT']).write_text(json.dumps({'version': 1, 'collected': _collected, 'results': list(_results.values())}))
