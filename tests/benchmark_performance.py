"""Repeatable local simulations, with baseline/candidate on the same Git inputs.

Run: python tests/benchmark_performance.py --repeat 7 --output PATH.json
No network, real Work actor, model setting or business canon is involved.
"""
import argparse
import platform
import statistics
import subprocess
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = "syncpilot/skills/syncpilot-codex/scripts/project_sync.py"


def module(name, raw):
    loaded = types.ModuleType(name)
    loaded.__file__ = str(ROOT / CORE_PATH)
    exec(compile(raw, loaded.__file__, "exec"), loaded.__dict__)
    return loaded


def command(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          check=True).stdout.decode("utf-8").strip()


def fixture(root, docs, core):
    repo = root / ("fixture-" + str(docs))
    repo.mkdir()
    command(repo, "init", "-b", "main")
    command(repo, "config", "user.name", "SyncPilot performance fixture")
    command(repo, "config", "user.email", "fixture@example.invalid")
    command(repo, "config", "core.autocrlf", "false")
    paths = ["docs/source-" + str(i).zfill(3) + ".txt" for i in range(docs)]
    contract = {"schema_version": 1, "project_id": "performance-fixture",
                "repository": "https://example.invalid/performance-fixture",
                "reference_branch": "main", "destination": "test:work",
                "authority": "TEST ONLY performance simulation", "shared_sources": [],
                "domains": {"docs": paths}, "transport": {"channel": "manual", "locator": "", "account": ""}}
    command(repo, "remote", "add", "origin", contract["repository"])
    (repo / core.CONTRACT).write_bytes(core.encode(contract))
    for i, path in enumerate(paths):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(("TEST ONLY source " + str(i) + " — été 🧭\r\n" +
                           "".join("Ligne " + str(n) + ": Document témoin exact.\n" for n in range(512))).encode("utf-8"))
    command(repo, "add", ".")
    command(repo, "-c", "commit.gpgsign=false", "commit", "-m", "TEST ONLY performance fixture")
    return repo, command(repo, "rev-parse", "HEAD"), sum(p.stat().st_size for p in repo.rglob("*.txt"))


def measure(core, repo, head, output):
    output.mkdir()
    original_git = core.git
    metrics = {"git_calls": 0, "git_wall_s": 0.0}

    def observed_git(repo, *args, **kwargs):
        started = time.perf_counter()
        metrics["git_calls"] += 1
        try:
            return original_git(repo, *args, **kwargs)
        finally:
            metrics["git_wall_s"] += time.perf_counter() - started

    core.git = observed_git
    req = output / "requirement.json"
    package, carrier = output / "package.zip", output / "carrier.json"
    cpu_started, started = time.process_time(), time.perf_counter()
    try:
        step = time.perf_counter()
        core.prepare_requirement(argparse.Namespace(repository=repo, commit=head, domain=["docs"],
                                                   authority="TEST ONLY performance simulation", output=req))
        metrics["prepare_s"] = time.perf_counter() - step
        step = time.perf_counter()
        built = core.build(argparse.Namespace(repository=repo, requirement=req, output=package,
                                             carrier=carrier, attestation=None))
        metrics["build_s"] = time.perf_counter() - step
        step = time.perf_counter()
        observation = output / "observation.json"
        observation.write_bytes(core.encode({"destination": "test:work", "artifact_locator": "test:carrier",
                                             "retrieved_sha256": core.digest(carrier.read_bytes())}))
        proof = output / "proof.json"
        store = output / "store"
        core.receive(argparse.Namespace(input=carrier, requirement=req, observation=observation,
                                        store=store, output=proof))
        core.check_store(store, core.load(req))
        evidence = output / "evidence.json"
        evidence.write_bytes(core.encode({"destination": "test:work", "destination_thread": "test:thread",
                                          "artifact_locator": "test:carrier", "proof_locator": "test:proof",
                                          "proof_sha256": core.digest(proof.read_bytes()),
                                          "authenticated_channel": "TEST ONLY SIMULATION", "authority": "TEST ONLY SIMULATION"}))
        accepted = core.accept(argparse.Namespace(input=carrier, requirement=req, proof=proof, evidence=evidence))
        assert accepted["mirror_status"] == "CURRENT"  # Fixture only, never a real Work proof.
        metrics["receive_check_accept_s"] = time.perf_counter() - step
        metrics["wall_s"] = time.perf_counter() - started
        metrics["python_cpu_s"] = time.process_time() - cpu_started
    finally:
        core.git = original_git
    exact = {"requirement_sha256": core.digest(req.read_bytes()), "package_sha256": core.digest(package.read_bytes()),
             "carrier_sha256": core.digest(carrier.read_bytes()), "proof_sha256": core.digest(proof.read_bytes()),
             "sync_id": built["sync_id"]}
    return metrics, exact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-core", type=Path, help="Optional local engine source to compare; current source otherwise")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new proof path")
    if args.repeat < 3:
        parser.error("At least three measurements required")
    candidate_raw = (ROOT / CORE_PATH).read_bytes()
    baseline_raw = args.baseline_core.read_bytes() if args.baseline_core else candidate_raw
    baseline, candidate = module("baseline_core", baseline_raw), module("candidate_core", candidate_raw)
    report = {"kind": "LOCAL_SYNTHETIC_SIMULATION", "baseline_kind": "local-engine" if args.baseline_core else "same-engine-control",
              "baseline_core_sha256": candidate.digest(baseline_raw),
              "candidate_core_sha256": candidate.digest(candidate_raw), "platform": platform.platform(),
              "python": platform.python_version(), "git": command(ROOT, "--version"),
              "model": "NO AGENT OR MODEL INVOLVED", "repeat": args.repeat, "cases": []}
    with tempfile.TemporaryDirectory(prefix="syncpilot-performance-") as temporary:
        root = Path(temporary)
        for docs in (1, 44, 113):
            repo, head, size = fixture(root, docs, candidate)
            case = {"document_count": docs, "selected_sources": docs + 1, "document_bytes": size,
                    "fixture_commit": head, "runs": {"baseline": [], "candidate": []}}
            reference = None
            # Warm both code paths once, excluded from the comparisons.
            for label, core in (("baseline", baseline), ("candidate", candidate)):
                _, exact = measure(core, repo, head, root / (str(docs) + "-warm-" + label))
                if reference is not None:
                    assert reference == exact, "Baseline/candidate identity changed"
                reference = exact
            for number in range(args.repeat):
                ordered = (("baseline", baseline), ("candidate", candidate))
                if number % 2:
                    ordered = tuple(reversed(ordered))
                for label, core in ordered:
                    metrics, exact = measure(core, repo, head, root / (str(docs) + "-" + str(number) + "-" + label))
                    assert reference == exact, "Exact artifact equality changed between runs"
                    case["runs"][label].append(metrics)
            case["exact_artifacts"] = reference
            case["summary"] = {}
            for label, runs in case["runs"].items():
                case["summary"][label] = {key: {"median": statistics.median(run[key] for run in runs),
                                                "min": min(run[key] for run in runs), "max": max(run[key] for run in runs)}
                                           for key in runs[0]}
            case["median_wall_reduction_percent"] = 100 * (1 - case["summary"]["candidate"]["wall_s"]["median"] /
                                                               case["summary"]["baseline"]["wall_s"]["median"])
            report["cases"].append(case)
            print("TEST ONLY", docs, "docs", round(case["median_wall_reduction_percent"], 2), "%", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate.encode(report))
    print(str(args.output), flush=True)


if __name__ == "__main__":
    main()
