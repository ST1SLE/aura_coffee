#!/usr/bin/env python3
# START_MODULE_CONTRACT
# PURPOSE: Fail-closed local evidence runner and verifier; local receipts are not remote attestations.
# SCOPE: Scenario selection, content identity, adapters, signed receipts and lifecycle checks.
# DEPENDS: Python standard library; external pytest/Vitest/Playwright executables.
# LINKS: .grace/context/principles.xml, .grace/verification/main.xml, C-REQUIRED-EVIDENCE-GATE
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# main - Parse CLI arguments and return a fail-closed verdict
# END_MODULE_MAP
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import signal
import subprocess
import sys
import time
import tempfile
import importlib.metadata
import xml.etree.ElementTree as ET

_LIMIT = 16 * 1024 * 1024
_CHANGE = re.compile(r"C-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")
_SKIP_DIRS = {'__pycache__', '.pytest_cache', '.ruff_cache'}
_GENERATED = {'web/admin/dist', 'web/customer/dist', 'tests/e2e/test-results',
              'tests/e2e/playwright-report', '.git', '.venv', '.verification-results', '.worktrees',
              'web/admin/node_modules', 'web/customer/node_modules', 'tests/e2e/node_modules',
              'tools/grace/node_modules', 'node_modules'}


class _Denied(Exception):
    def __init__(self, code):
        self.code = code


def _require(condition, code):
    if not condition:
        raise _Denied(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    out = {}
    for k, v in pairs:
        _require(k not in out, 'DUPLICATE_KEY')
        out[k] = v
    return out


def _json(path):
    _require(path.is_file() and not path.is_symlink(), 'MISSING_REPORT')
    _require(path.stat().st_size <= _LIMIT, 'REPORT_TOO_LARGE')
    try:
        return json.loads(path.read_text(), object_pairs_hook=_unique)
    except (ValueError, UnicodeError):
        raise _Denied('MALFORMED_REPORT') from None


def _inside(root, relative):
    p = root / relative
    _require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'UNSAFE_PATH')
    _require(p.resolve().is_relative_to(root.resolve()), 'UNSAFE_PATH')
    _require(not p.is_symlink(), 'UNSAFE_PATH')
    return p


def _xml(path):
    _require(path.is_file() and not path.is_symlink(), 'MISSING_BUNDLE')
    data = path.read_bytes()
    _require(len(data) < _LIMIT and b'<!DOCTYPE' not in data and b'<!ENTITY' not in data, 'UNSAFE_XML')
    return ET.fromstring(data)


def _bundle(root, change, running=False):
    locations = [root / '.grace/changes' / phase / change for phase in ('active', 'archive')]
    found = [p for p in locations if p.is_dir()]
    _require(len(found) == 1, 'LIFECYCLE_BYPASS')
    bundle = found[0]
    states = []
    for name, tag in [('spec.xml', 'GraceChangeSpec'), ('plan.xml', 'GraceChangePlan')]:
        doc = _xml(bundle / name)
        _require(doc.tag == tag and len(doc) == 1 and doc[0].tag == change, 'INVALID_BUNDLE')
        states.append(doc.get('status'))
    _require(states[0] == states[1] and states[0] in ('approved', 'applied'), 'LIFECYCLE_BYPASS')
    if running:
        _require(bundle.parent.name == 'active' and states == ['approved', 'approved'], 'LIFECYCLE_BYPASS')
    if bundle.parent.name == 'archive':
        _require(states == ['applied', 'applied'], 'LIFECYCLE_BYPASS')
    plan = _xml(bundle / 'plan.xml')
    commands = [x.text or '' for x in plan.findall('.//TargetAssertions/MustPassCommand/Command')]
    expected = ['python3', 'tools/verification/gate.py', 'check', '--change', change,
                '--evidence-dir', f'.verification-results/{change}']
    _require(any(shlex.split(c) == expected for c in commands), 'MISSING_GATE_ASSERTION')
    return bundle


def _snapshot(root, change):
    result = {}
    _bundle(root, change)
    visible = None
    if (root / '.git').exists():
        # Match the disposable archive's source inventory; never open arbitrary
        # ignored workstation files (.envrc, credentials, caches, screenshots).
        inventory = subprocess.run(['git', '-C', str(root), 'ls-files', '--cached', '--others',
                                    '--exclude-standard', '-z'], capture_output=True, check=True)
        visible = set(inventory.stdout.decode().split('\0')) - {''}
    visible_dirs = {p.as_posix() for name in (visible or ()) for p in Path(name).parents}
    for parent, dirs, files in os.walk(root, followlinks=False):
        rel = Path(parent).relative_to(root)
        for name in list(dirs):
            p = Path(parent) / name
            key = (rel / name).as_posix()
            if (visible is not None and key not in visible_dirs and key not in visible) or name in _SKIP_DIRS or key in _GENERATED:
                dirs.remove(name)
            else:
                _require(not p.is_symlink(), 'SYMLINK_INPUT')
        for name in sorted(files):
            p = Path(parent) / name
            key = (rel / name).as_posix()
            if visible is not None and key not in visible:
                continue
            if key in {'.env', '.env.local'} or name.endswith(('.pyc', '.tsbuildinfo')):
                continue
            _require(not name.startswith('.env') or name in ('.env.example', '.env.production.example'), 'SENSITIVE_INPUT')
            if name == '.run.lock' and key.startswith('research/deep-research/'):
                continue
            _require(not p.is_symlink(), 'SYMLINK_INPUT')
            _require(not name.endswith(('.pem', '.key', '.sqlite', '.sqlite3', '.db')), 'SENSITIVE_INPUT')
            data = p.read_bytes()
            # Normalize only this bundle's two root status attributes and relocation.
            prefix = f'.grace/changes/{rel.parts[2]}/{change}/' if len(rel.parts) >= 4 and rel.parts[:2] == ('.grace', 'changes') and rel.parts[3] == change else None
            if prefix and key.startswith(prefix):
                key = key.replace(prefix, f'.grace/changes/normalized/{change}/', 1)
                if name in ('spec.xml', 'plan.xml'):
                    data = re.sub(rb'(<GraceChange(?:Spec|Plan)\b[^>]*\bstatus=")[^"]*(")', rb'\1approved\2', data, count=1)
            _require(key not in result, 'DUPLICATE_INPUT')
            result[key] = {'sha256': _digest(data), 'mode': '755' if p.stat().st_mode & 0o111 else '644'}
    return result


def _policy(root, change):
    doc = _json(root / 'tools/verification/policy.json')
    _require(set(doc) == {'version', 'changes'} and doc['version'] == 1, 'POLICY_SCHEMA')
    _require(change in doc['changes'], 'UNKNOWN_SCOPE')
    spec = doc['changes'][change]
    _require(set(spec) == {'scenarios', 'scope', 'non_applicability'}, 'POLICY_SCHEMA')
    _require(isinstance(spec['non_applicability'], str) and spec['non_applicability'].strip(), 'MISSING_APPLICABILITY')
    _require(isinstance(spec['scope'], list) and bool(spec['scope']), 'UNKNOWN_SCOPE')
    scenarios = spec['scenarios']
    _require(isinstance(scenarios, list) and bool(scenarios), 'NO_OBLIGATIONS')
    seen = set()
    for s in scenarios:
        _require(set(s) - {'config'} == {'id', 'adapter', 'layer', 'cwd', 'selectors', 'profiles', 'tests', 'timeout', 'mocks'}, 'SCENARIO_SCHEMA')
        if 'config' in s:
            _require(s['adapter'] == 'playwright' and _inside(root, s['config']).is_file(), 'INVALID_CONFIG')
        _require(re.fullmatch(r'[A-Z0-9-]+', s['id']) and s['id'] not in seen, 'DUPLICATE_SCENARIO')
        seen.add(s['id'])
        _require(s['adapter'] in ('pytest', 'vitest', 'playwright'), 'UNSUPPORTED_ADAPTER')
        _require(s['layer'] in ('tool-contract', 'unit', 'browser', 'backend-ldd'), 'WRONG_LAYER')
        _require((s['adapter'] == 'playwright') == (s['layer'] == 'browser'), 'WRONG_LAYER')
        # This increment cannot establish arbitrary backend LDD from an exit code.
        _require(s['layer'] != 'backend-ldd', 'LDD_ADAPTER_NOT_IMPLEMENTED')
        for field in ('selectors', 'profiles', 'tests'):
            _require(isinstance(s[field], list) and bool(s[field]) and len(s[field]) == len(set(s[field])) and all(isinstance(v, str) and v for v in s[field]), 'EMPTY_OR_DUPLICATE_SELECTION')
        _require(all(not x.startswith('-') and not Path(x).is_absolute() and '..' not in Path(x).parts for x in s['selectors']), 'UNSAFE_SELECTOR')
        _require(type(s['timeout']) is int and 0 < s['timeout'] <= 900, 'INVALID_BUDGET')
        _require(isinstance(s['mocks'], list), 'SCENARIO_SCHEMA')
        cwd = _inside(root, s['cwd'])
        for selector in s['selectors']:
            selected = (cwd / selector.split('::')[0]).relative_to(root).as_posix()
            _require(not any(selected == p or selected.startswith(p + '/') for p in _GENERATED)
                     and not any(p in _SKIP_DIRS for p in Path(selected).parts), 'EXCLUDED_TEST_INPUT')
    return spec


def _key(root):
    path = Path(os.environ.get('AURA_EVIDENCE_KEY', str(Path.home() / '.cache/aura-verification/local.key')))
    _require(path.is_absolute() and not path.resolve().is_relative_to(root.resolve()), 'UNSAFE_KEY_LOCATION')
    _require(path.is_file() and not path.is_symlink(), 'LOCAL_TRUST_NOT_INITIALIZED')
    _require(path.stat().st_mode & 0o077 == 0, 'UNSAFE_KEY_PERMISSIONS')
    value = path.read_bytes()
    _require(len(value) == 32, 'INVALID_LOCAL_KEY')
    return value


def _sign(root, payload):
    return hmac.new(_key(root), _canonical(payload), hashlib.sha256).hexdigest()


def _init_key(root):
    path = Path(os.environ.get('AURA_EVIDENCE_KEY', str(Path.home() / '.cache/aura-verification/local.key')))
    _require(path.is_absolute() and not path.resolve().is_relative_to(root.resolve()), 'UNSAFE_KEY_LOCATION')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
            f.write(secrets.token_bytes(32))
    _key(root)


def _execute(argv, cwd, env, budget):
    start = time.monotonic()
    # Never persist arbitrary runner stdout: it can contain secrets or raw PII.
    with subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, start_new_session=True) as p:
        try:
            code = p.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            raise _Denied('PRODUCER_TIMEOUT') from None
    return code, round(time.monotonic() - start, 3)


def _parse(adapter, path, root):
    doc = _json(path)
    rows = []
    if adapter in ('pytest', 'vitest'):
        _require(doc.get('version') == 1 and isinstance(doc.get('collected'), list), 'MALFORMED_REPORT')
        return doc['collected'], doc['results']
    def visit(suite, parents=()):
        for spec in suite.get('specs', []):
            identity = spec['file'] + '::' + ' > '.join((*parents, spec['title']))
            for test in spec['tests']:
                results = test.get('results', [])
                status = 'passed' if test.get('expectedStatus') == 'passed' and test.get('status') == 'expected' and len(results) == 1 and results[0].get('status') == 'passed' and results[0].get('retry', 0) == 0 else 'not-passed'
                rows.append({'id': identity, 'profile': test['projectName'], 'status': status,
                             'retry': max(0, len(results) - 1)})
        for child in suite.get('suites', []):
            visit(child, (*parents, child['title']))
    _require(isinstance(doc.get('suites'), list), 'MALFORMED_REPORT')
    for suite in doc['suites']:
        visit(suite)
    return [r['id'] for r in rows], rows


def _validate_rows(scenario, collected, rows):
    expected = {(t, p) for t in scenario['tests'] for p in scenario['profiles']}
    _require(bool(collected) and bool(rows), 'ZERO_TESTS')
    _require(set(collected) == set(scenario['tests']), 'COLLECTION_MISMATCH')
    actual = [(r['id'], r['profile']) for r in rows]
    _require(len(actual) == len(set(actual)), 'DUPLICATE_TEST')
    _require(set(actual) == expected, 'PROFILE_OR_TEST_GAP')
    _require(all(r.get('status') == 'passed' and r.get('retry') == 0 for r in rows), 'REQUIRED_TEST_NOT_PASSED')


def _validate_versions(adapter, versions):
    expected = {adapter, 'python' if adapter == 'pytest' else 'node'}
    _require(isinstance(versions, dict) and set(versions) == expected and
             all(isinstance(v, str) and v for v in versions.values()), 'MISSING_RUNTIME_IDENTITY')


def _run(root, change, evidence, continuous=False):
    _require(str(root.resolve()).startswith('/tmp/aura-coffee-audit-'), 'ISOLATION_REQUIRED')
    bundle = _bundle(root, change, running=not continuous)
    started_status = _xml(bundle / 'plan.xml').get('status')
    policy = _policy(root, change)
    _init_key(root)
    before = _snapshot(root, change)
    _require(not evidence.exists(), 'EVIDENCE_ALREADY_EXISTS')
    evidence.mkdir(parents=True, mode=0o700)
    run_id = secrets.token_hex(16)
    producers = []
    started = time.monotonic()
    if any(s['adapter'] == 'playwright' for s in policy['scenarios']):
        for app in ('web/admin', 'web/customer'):
            code, _ = _execute(['npm', 'run', 'build'], root / app, dict(os.environ), 120)
            _require(code == 0, 'BUILD_FAILED')
    for s in policy['scenarios']:
        report = evidence / (s['id'] + '.json')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        env.pop('AURA_EVIDENCE_KEY', None)
        cwd = _inside(root, s['cwd'])
        if s['adapter'] == 'pytest':
            # A fresh cache prefix prevents importing candidate unchecked-hash bytecode.
            env['PYTHONPYCACHEPREFIX'] = tempfile.mkdtemp(prefix='aura-gate-python-cache-')
            env['PYTHONPATH'] = str(root / 'tools/verification')
            env['AURA_GATE_REPORT'] = str(report)
            argv = [sys.executable, '-X', 'pycache_prefix=' + env['PYTHONPYCACHEPREFIX'], '-m', 'pytest', '-p', 'pytest_evidence', '-q', '-ra', '--strict-markers', *s['selectors']]
            versions = {'python': sys.version.split()[0], 'pytest': importlib.metadata.version('pytest')}
        elif s['adapter'] == 'vitest':
            env['AURA_GATE_REPORT'] = str(report)
            env['AURA_GATE_ROOT'] = str(root)
            selectors = [str((cwd / value).relative_to(root)) for value in s['selectors']]
            argv = ['npm', 'exec', '--no', '--', 'vitest', 'run', *selectors, '--root=' + str(root), '--config=' + str(cwd / 'vitest.config.ts'), '--retry=0', '--reporter=' + str(root / 'tools/verification/vitest-reporter.mjs')]
            versions = {'vitest': _json(cwd / 'node_modules/vitest/package.json')['version']}
        else:
            env['PLAYWRIGHT_JSON_OUTPUT_NAME'] = str(report)
            argv = ['npm', 'exec', '--no', '--', 'playwright', 'test', *s['selectors'], '--reporter=json', '--retries=0']
            if 'config' in s:
                argv += ['--config=' + str(_inside(root, s['config']))]
            versions = {'playwright': _json(cwd / 'node_modules/playwright/package.json')['version']}
        if s['adapter'] != 'pytest':
            node = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5, check=True)
            _require(bool(re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+\s*', node.stdout)), 'INVALID_RUNTIME_VERSION')
            versions['node'] = node.stdout.strip()
        budget = min(s['timeout'], max(0.01, 900 - (time.monotonic() - started)))
        try:
            code, seconds = _execute(argv, cwd, env, budget)
            collected, rows = _parse(s['adapter'], report, root)
        finally:
            # Even failed/time-limited native reports may contain diagnostic payloads.
            report.unlink(missing_ok=True)
        _require(set(collected) <= set(s['tests']) and all(r.get('id') in s['tests'] and r.get('profile') in s['profiles'] for r in rows), 'UNEXPECTED_REPORT_IDENTITY')
        rows = [{'id': r['id'], 'profile': r['profile'],
                 'status': 'passed' if r.get('status') == 'passed' else 'not-passed',
                 'retry': r.get('retry') if type(r.get('retry')) is int else -1} for r in rows]
        # Raw runner reports contain diagnostics; replace with bounded, non-payload facts.
        sanitized = {'version': 1, 'collected': collected, 'results': rows}
        report.write_bytes(_canonical(sanitized))
        producers.append({'scenario': s['id'], 'adapter': s['adapter'], 'layer': s['layer'],
                          'mocks': s['mocks'], 'command': argv, 'exit': code, 'seconds': seconds, 'versions': versions,
                          'artifact': report.name, 'sha256': _digest(report.read_bytes())})
    after = _snapshot(root, change)
    _require(before == after, 'INPUT_CHANGED_DURING_RUN')
    payload = {'version': 1, 'change': change, 'run_id': run_id, 'scope': 'local-only',
               'snapshot': before, 'policy': _digest(_canonical(policy)), 'producers': producers,
               'duration': round(time.monotonic() - started, 3), 'started_status': started_status,
               'kind': 'continuous' if continuous else 'closure',
               'python': sys.version.split()[0]}
    receipt = {'payload': payload, 'signature': _sign(root, payload)}
    (evidence / 'receipt.json').write_bytes(_canonical(receipt))
    return _check(root, change, evidence)


def _check(root, change, evidence):
    policy = _policy(root, change)
    receipt = _json(evidence / 'receipt.json')
    _require(set(receipt) == {'payload', 'signature'}, 'UNSIGNED_EVIDENCE')
    payload = receipt['payload']
    _require(isinstance(receipt['signature'], str) and hmac.compare_digest(receipt['signature'], _sign(root, payload)), 'TAMPERED_RECEIPT')
    _require(payload.get('version') == 1 and payload.get('change') == change and payload.get('scope') == 'local-only', 'WRONG_CONTEXT')
    _require(payload.get('kind') in ('closure', 'continuous') and (payload.get('started_status') == 'approved' or (payload.get('kind') == 'continuous' and payload.get('started_status') == 'applied')), 'WRONG_CONTEXT')
    _require(payload.get('policy') == _digest(_canonical(policy)), 'POLICY_CHANGED')
    _require(payload.get('snapshot') == _snapshot(root, change), 'STALE_EVIDENCE')
    producers = payload.get('producers', [])
    _require(len(producers) == len(policy['scenarios']) and len({p['scenario'] for p in producers}) == len(producers), 'MISSING_OR_DUPLICATE_SCENARIO')
    by_id = {p['scenario']: p for p in producers}
    for s in policy['scenarios']:
        _require(s['id'] in by_id, 'MISSING_SCENARIO')
        p = by_id[s['id']]
        _validate_versions(s['adapter'], p.get('versions'))
        _require(p['adapter'] == s['adapter'] and p['layer'] == s['layer'] and p['mocks'] == s['mocks'], 'WRONG_LAYER')
        report = _inside(evidence, p['artifact'])
        doc = _json(report)
        _require(_digest(report.read_bytes()) == p['sha256'], 'ARTIFACT_TAMPERED')
        _require(p['exit'] == 0, 'PRODUCER_FAILED')
        _validate_rows(s, doc['collected'], doc['results'])
    return {'status': 'passed', 'scope': 'local-only', 'change': change, 'run_id': payload['run_id']}


# START_CONTRACT: main
# PURPOSE: Execute the scoped evidence CLI entry point.
# INPUTS: CLI arguments and environment — validated by the entry point
# OUTPUTS: Exit status or completion; invalid evidence blocks
# SIDE_EFFECTS: Local evidence files and isolated subprocesses where applicable
# LINKS: C-REQUIRED-EVIDENCE-GATE, .grace/verification/main.xml
# END_CONTRACT: main
def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['run', 'check'])
    parser.add_argument('--change', required=True)
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--root', default='.')
    a = parser.parse_args(argv)
    try:
        _require(bool(_CHANGE.fullmatch(a.change)), 'INVALID_CHANGE')
        root = Path(a.root).resolve()
        evidence = Path(a.evidence_dir).absolute()
        _require(evidence.resolve().is_relative_to(root / '.verification-results'), 'UNSAFE_EVIDENCE_LOCATION')
        out = (_run if a.action == 'run' else _check)(root, a.change, evidence)
        print(json.dumps(out))
        return 0
    except _Denied as e:
        print(json.dumps({'status': 'blocked', 'reason': e.code}))
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ET.ParseError, subprocess.SubprocessError):
        # Do not serialize exception values: input strings may contain secrets.
        print(json.dumps({'status': 'blocked', 'reason': 'INVALID_OR_UNAVAILABLE_INPUT'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
