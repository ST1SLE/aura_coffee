# START_MODULE_CONTRACT
# PURPOSE: Bind first CI closure to an earlier successful approved PR verification.
# SCOPE: GitHub Actions read-only provenance, Git ancestry, snapshot and artifact identity.
# DEPENDS: Python standard library, git, gh and gate.
# LINKS: C-CI-CLOSURE-EVIDENCE, C-REQUIRED-EVIDENCE-GATE
# ROLE: SCRIPT
# MAP_MODE: LOCALS
# END_MODULE_CONTRACT
# START_MODULE_MAP
# _resolve - confirm prior authorization independently for one first closure
# _issue - publish a bounded document after current CI aggregation
# END_MODULE_MAP
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import zipfile

import gate

_WORKFLOW = ".github/workflows/verify.yml"
_MAX = 1024 * 1024
_require = gate._require


def _event():
    _require(os.environ["GITHUB_EVENT_NAME"] == "pull_request", "PR_REQUIRED")
    event = gate._json(Path(os.environ["GITHUB_EVENT_PATH"]))
    pr = event["pull_request"]
    repo = os.environ["GITHUB_REPOSITORY"]
    _require(
        pr["base"]["repo"]["full_name"] == repo == pr["head"]["repo"]["full_name"],
        "WRONG_REPOSITORY",
    )
    _require(pr["base"]["sha"] == os.environ["AURA_BASE_SHA"], "WRONG_BASE")
    return dict(
        repository=repo,
        repository_id=pr["base"]["repo"]["id"],
        pr=pr["number"],
        base=pr["base"]["sha"],
        head=pr["head"]["sha"],
        candidate=os.environ["AURA_CANDIDATE_SHA"],
        run=int(os.environ["AURA_RUN_ID"]),
        attempt=int(os.environ["AURA_RUN_ATTEMPT"]),
    )


def _binding(base, candidate, change):
    digest = lambda value: gate._digest(gate._canonical(value))
    return dict(
        version=1,
        change=change,
        snapshot=digest(gate._snapshot(candidate, change)),
        policy=digest(gate._policy(base, change)),
        workflow=gate._digest((base / _WORKFLOW).read_bytes()),
    )


def _issue(base, candidate, evidence, change, path):
    _require(
        gate._bundle(candidate, change, running=True).parent.name == "active",
        "APPROVED_REQUIRED",
    )
    receipt = gate._json(evidence / change / "receipt.json")["payload"]
    _require(
        (receipt["started_status"], receipt["kind"]) == ("approved", "closure"),
        "APPROVED_REQUIRED",
    )
    data = dict(
        **_event(),
        **_binding(base, candidate, change),
        receipt=gate._digest((evidence / change / "receipt.json").read_bytes()),
    )
    raw = gate._canonical(data)
    path.write_bytes(raw)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        print("digest=" + gate._digest(raw), file=output)


def _api(route, binary=False):
    # gh handles authenticated GitHub redirects. Never accept an artifact-supplied URL.
    _require(
        re.fullmatch(r"[A-Za-z0-9_./?=&%:+-]+", route) is not None, "INVALID_API_ROUTE"
    )
    with tempfile.TemporaryFile() as out:
        subprocess.run(
            ["gh", "api", "--hostname", "github.com", route],
            stdout=out,
            check=True,
            timeout=25,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX, _MAX)),
        )
        _require(out.tell() <= _MAX, "RESPONSE_TOO_LARGE")
        out.seek(0)
        raw = out.read()
    return raw if binary else json.loads(raw, object_pairs_hook=gate._unique)


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], timeout=15).strip()


def _only_closure(root, old, new, change):
    # Compare complete Git trees, including files excluded from the runtime fingerprint.
    def tree(rev, phase):
        entries = _git(root, "ls-tree", "-rz", rev)
        result = {}
        prefix = f".grace/changes/{phase}/{change}/".encode()
        for row in entries.rstrip(b"\0").split(b"\0"):
            meta, name = row.split(b"\t", 1)
            if name.startswith(prefix):
                key = b"\0" + name[len(prefix) :]
                if key in (b"\0plan.xml", b"\0spec.xml"):
                    mode, typ, oid = meta.split()
                    data = subprocess.check_output(
                        ["git", "-C", str(root), "cat-file", "blob", oid]
                    )
                    if phase == "archive":
                        data, count = re.subn(
                            rb'^(\s*(?:<\?xml[^?]*\?>\s*)?<GraceChange(?:Spec|Plan)\b[^>]*?\bstatus=")applied(")',
                            rb"\g<1>approved\2",
                            data,
                            count=1,
                        )
                        _require(count == 1, "INVALID_CLOSURE_XML")
                    meta = (mode, typ, data)
                name = key
            result[name] = meta
        return result

    return tree(old, "active") == tree(new, "archive")


def _resolve(base, candidate, change, git_root, api=_api):
    ctx = _event()
    repo = "repos/" + ctx["repository"]
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    route = f"{repo}/actions/workflows/verify.yml/runs?event=pull_request&status=success&created=%3E%3D{cutoff}&per_page=100"
    listing = api(route)
    _require(
        listing["total_count"] == len(listing["workflow_runs"]), "INCOMPLETE_RUN_LIST"
    )
    binding = _binding(base, candidate, change)
    matches = []
    for run in listing["workflow_runs"]:
        if run["id"] == ctx["run"] or run["head_sha"] == ctx["head"]:
            continue
        prs = [
            pr
            for pr in run["pull_requests"]
            if pr["number"] == ctx["pr"] and pr["base"]["sha"] == ctx["base"]
        ]
        if len(prs) != 1:
            continue
        head = run["head_sha"]
        _require(
            re.fullmatch("[0-9a-f]{40}", head) and prs[0]["head"]["sha"] == head,
            "WRONG_HEAD",
        )
        if subprocess.run(
            [
                "git",
                "-C",
                str(git_root),
                "merge-base",
                "--is-ancestor",
                head,
                ctx["head"],
            ]
        ).returncode:
            continue
        if not _only_closure(git_root, head, ctx["head"], change):
            continue
        _require(
            run["repository"]["id"]
            == run["head_repository"]["id"]
            == ctx["repository_id"]
            and run["path"] == _WORKFLOW
            and run["event"] == "pull_request"
            and run["status"] == "completed"
            and run["conclusion"] == "success",
            "UNTRUSTED_RUN",
        )
        _require(
            _git(git_root, "rev-parse", head + ":.github/workflows")
            == _git(git_root, "rev-parse", ctx["base"] + ":.github/workflows"),
            "UNTRUSTED_WORKFLOW",
        )
        rid, attempt = int(run["id"]), int(run["run_attempt"])
        prior = f"{repo}/actions/runs/{rid}"
        jobs = api(f"{prior}/attempts/{attempt}/jobs?per_page=100")
        _require(jobs["total_count"] == len(jobs["jobs"]), "INCOMPLETE_JOB_LIST")
        issuers = [
            j
            for j in jobs["jobs"]
            if j["name"] == "Required Evidence Gate" and j["conclusion"] == "success"
        ]
        _require(len(issuers) == 1, "ISSUER_MISSING")
        # The marker is written by the trusted final job after validating both dependencies.
        marks = [
            s["name"][len("Issued closure ") :]
            for s in issuers[0]["steps"]
            if s["name"].startswith("Issued closure ") and s["conclusion"] == "success"
        ]
        _require(
            len(marks) == 1 and re.fullmatch("[0-9a-f]{64}", marks[0]), "ISSUER_MISSING"
        )
        artifacts = api(f"{prior}/artifacts?name=closure-{rid}-{attempt}")
        _require(
            artifacts["total_count"] == len(artifacts["artifacts"]) == 1,
            "AMBIGUOUS_ARTIFACT",
        )
        art = artifacts["artifacts"][0]
        issued = dt.datetime.fromisoformat(art["created_at"])
        _require(
            not art["expired"]
            and dt.timedelta(0) <= now - issued <= dt.timedelta(days=7)
            and art["size_in_bytes"] <= _MAX,
            "EXPIRED_OR_OVERSIZED",
        )
        raw = api(f"{repo}/actions/artifacts/{int(art['id'])}/zip", binary=True)
        _require("sha256:" + gate._digest(raw) == art["digest"], "ARCHIVE_DIGEST")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            _require(
                z.namelist() == ["authorization.json"]
                and z.infolist()[0].file_size <= 8192,
                "INVALID_ARCHIVE",
            )
            doc = z.read("authorization.json")
        _require(gate._digest(doc) == marks[0], "ISSUER_DIGEST")
        data = json.loads(doc, object_pairs_hook=gate._unique)
        expected = dict(ctx, **binding)
        expected.update(head=head, run=rid, attempt=attempt)
        # Old synthetic merge SHA belongs to the signed-by-job context. It differs
        # from the old PR head and from the current synthetic merge SHA.
        _require(
            re.fullmatch("[0-9a-f]{40}", data["candidate"])
            and re.fullmatch("[0-9a-f]{64}", data["receipt"]),
            "INVALID_AUTHORIZATION",
        )
        expected.update(candidate=data["candidate"], receipt=data["receipt"])
        _require(data == expected, "WRONG_AUTHORIZATION")
        matches.append(marks[0])
    _require(len(matches) == 1, "MISSING_OR_AMBIGUOUS_AUTHORIZATION")
    return matches[0]
