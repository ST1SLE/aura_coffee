# START_MODULE_CONTRACT
# PURPOSE: Verify first CI closure against separate runs, real Git trees and synthetic Actions metadata.
# SCOPE: Trusted issuer, artifact integrity, lifecycle and current obligations.
# DEPENDS: gate, ci_check, closure, pytest.
# LINKS: C-CI-CLOSURE-EVIDENCE
# ROLE: TEST
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# two_runs - provide approved and applied CI contexts
# test_first_closure - exercise both runs and independently change individual inputs
# END_MODULE_MAP
import copy
import datetime as dt
import io
import json
import shutil
import subprocess
import zipfile

import pytest

from conftest import gate, ci_check, _run
import closure
from test_lifecycle import _apply


# START_CONTRACT: two_runs
# PURPOSE: Prepare a previously verified approved commit and a fresh applied candidate.
# INPUTS: Disposable repository, temporary path and environment fixtures.
# OUTPUTS: Isolated run metadata and checker callback.
# SIDE_EFFECTS: Writes synthetic Git fixtures.
# LINKS: C-CI-CLOSURE-EVIDENCE
# END_CONTRACT: two_runs
@pytest.fixture
def two_runs(repo, tmp_path, monkeypatch):
    # Real commits make ancestry and the allowed lifecycle-only diff observable.
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], text=True
        ).strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@localhost")
    (repo / ".github/workflows").mkdir(parents=True)
    (repo / closure._WORKFLOW).write_text("trusted fixture")
    (repo / ".gitignore").write_text(
        ".verification-results/\n__pycache__/\n.pytest_cache/\n"
    )
    git("add", ".")
    git("commit", "-qm", "base")
    baseline = git("rev-parse", "HEAD")
    base = tmp_path / "base"
    shutil.copytree(repo, base)
    git("commit", "--allow-empty", "-qm", "approved")
    head = git("rev-parse", "HEAD")
    ctx = dict(
        repository="demo/repo",
        repository_id=1,
        pr=2,
        base=baseline,
        head=head,
        candidate="a" * 40,
        run=12,
        attempt=1,
    )
    monkeypatch.setattr(closure, "_event", lambda: dict(ctx))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    evidence = repo / ".verification-results"

    def current():
        ident = dict(
            run_id=str(ctx["run"]),
            run_attempt="1",
            base_sha=ctx["base"],
            candidate_sha=ctx["candidate"],
        )
        (evidence / "ci-context.json").write_text(json.dumps(ident))
        return ident

    jobs = {name: {"result": "success"} for name in ("full-gate", "evidence-producer")}
    change = "C-TEST"
    _run(repo)
    ci_check._verify(base, repo, evidence, current(), jobs)
    path = tmp_path / "authorization.json"
    closure._issue(base, repo, evidence, change, path)
    digest = gate._digest(path.read_bytes())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(path.name, path.read_bytes())
    raw = buf.getvalue()
    run = dict(
        id=12,
        head_sha=head,
        pull_requests=[dict(number=2, base={"sha": baseline}, head={"sha": head})],
        repository={"id": 1},
        head_repository={"id": 1},
        path=closure._WORKFLOW,
        event="pull_request",
        status="completed",
        conclusion="success",
        run_attempt=1,
    )
    listing = dict(total_count=1, workflow_runs=[run])
    issuer = dict(
        name="Required Evidence Gate",
        conclusion="success",
        steps=[dict(name="Issued closure " + digest, conclusion="success")],
    )
    artifact = dict(
        id=4,
        expired=False,
        created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        size_in_bytes=len(raw),
        digest="sha256:" + gate._digest(raw),
    )

    def api(route, binary=False):
        if "/actions/workflows/" in route:
            return listing
        if "/12/attempts/1/jobs?" in route:
            return dict(total_count=1, jobs=[issuer])
        if route.endswith("/12/artifacts?name=closure-12-1"):
            return dict(total_count=1, artifacts=[artifact])
        if binary and route.endswith("/4/zip"):
            return raw
        raise gate._Denied("UNEXPECTED_API_CONTEXT")

    _apply(repo)
    git("add", "-A")
    git("commit", "-qm", "close")
    ctx.update(head=git("rev-parse", "HEAD"), candidate="b" * 40, run=13)
    shutil.rmtree(evidence)
    gate._run(repo, change, evidence / change, continuous=True)
    (evidence / "closure-authority.json").write_text(json.dumps({change: digest}))
    ident = current()
    resolve = lambda base, candidate, change, root: closure._resolve(
        base, candidate, change, root, api
    )
    return dict(
        run=run,
        artifact=artifact,
        issuer=issuer,
        ctx=ctx,
        jobs=jobs,
        listing=listing,
        repo=repo,
        verify=lambda: ci_check._verify(base, repo, evidence, ident, jobs, resolve),
    )


# START_CONTRACT: test_first_closure
# PURPOSE: Check the legitimate transition and independent rejection cases.
# INPUTS: Two synthetic CI runs and a mutation case.
# OUTPUTS: None.
# SIDE_EFFECTS: Mutates disposable test data.
# LINKS: C-CI-CLOSURE-EVIDENCE
# END_CONTRACT: test_first_closure
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "wrong-pr",
        "wrong-base",
        "wrong-repository",
        "wrong-workflow",
        "wrong-attempt",
        "failed-prior",
        "expired",
        "corrupt",
        "substitution",
        "mixed",
        "missing",
        "ambiguous",
        "edit",
        "failed-current",
    ],
)
def test_first_closure(two_runs, case):
    x = two_runs
    r = x["run"]
    if case == "valid":
        assert x["verify"]()["status"] == "passed"
        return
    if case == "wrong-pr":
        r["pull_requests"][0]["number"] += 1
    if case == "wrong-base":
        r["pull_requests"][0]["base"]["sha"] = "c" * 40
    if case == "wrong-repository":
        r["repository"]["id"] += 1
    if case == "wrong-workflow":
        r["path"] = "other.yml"
    if case == "wrong-attempt":
        r["run_attempt"] += 1
    if case == "failed-prior":
        r["conclusion"] = "failure"
    if case == "expired":
        x["artifact"]["expired"] = True
    if case == "corrupt":
        x["artifact"]["digest"] = "sha256:" + "c" * 64
    if case == "substitution":
        x["issuer"]["steps"][0]["name"] = "Issued closure " + "d" * 64
    if case == "mixed":
        (x["repo"] / ".verification-results/closure-authority.json").write_text(
            '{"C-TEST":"wrong"}'
        )
    if case == "missing":
        x["listing"].update(total_count=0, workflow_runs=[])
    if case == "ambiguous":
        x["listing"].update(total_count=2, workflow_runs=[r, copy.deepcopy(r)])
    if case == "edit":
        (x["repo"] / "tests/test_sample.py").write_text("def test_ok(): pass")
    if case == "failed-current":
        x["jobs"]["full-gate"]["result"] = "failure"
    with pytest.raises(gate._Denied):
        x["verify"]()
