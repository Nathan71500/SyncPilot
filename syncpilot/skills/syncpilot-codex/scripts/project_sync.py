#!/usr/bin/env python3
"""SyncPilot v1: explicit project contracts, exact Git snapshots, destination proof.

Standard library only. No network, Git mutations, background service or automatic
integration. A JSON observation is evidence input, never an identity signature.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILE = 2_000_000
MAX_TOTAL = 20_000_000
MAX_ENTRIES = 500
CONTRACT = "project-sync.json"


class SyncError(Exception):
    pass


def utf8_stdio():
    """Keep CLI bytes deterministic, including Windows error output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict")


def require(ok, message):
    if not ok:
        raise SyncError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def decode(data):
    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, "Duplicate JSON key")
            obj[key] = value
        return obj
    obj = json.loads(data, object_pairs_hook=pairs,
                     parse_constant=lambda _: require(False, "Invalid JSON constant"))
    require(isinstance(obj, dict), "JSON object required")
    return obj


def load(path):
    require(path.stat().st_size <= MAX_FILE, "JSON too large")
    return decode(path.read_bytes())


def fields(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names.split()), "Unexpected or missing fields")


def text(value):
    require(isinstance(value, str) and bool(value.strip()), "Nonempty string required")


def hex_value(value, length):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value), "Invalid digest or commit")


def safe_path(value):
    text(value)
    require(not any(c in value for c in "\\:\x00\r\n"), "Unsafe path")
    require(PurePosixPath(value).as_posix() == value and not value.startswith("/"), "Noncanonical path")
    parts = value.split("/")
    require(all(p not in ("", ".", "..") for p in parts), "Path traversal")
    require(all(not p.endswith((".", " ")) for p in parts), "Ambiguous Windows path")
    require(all(not re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?", p) for p in parts), "Reserved Windows name")
    return value


def path_list(values):
    require(isinstance(values, list) and bool(values), "Nonempty explicit file list required")
    for value in values:
        safe_path(value)
    require(len(values) == len(set(v.casefold() for v in values)), "Duplicate or case-colliding paths")



def dc_endpoint(locator):
    from urllib.parse import quote, unquote, urlsplit
    import uuid
    import ntpath
    import posixpath
    text(locator)
    url = urlsplit(locator)
    require(url.scheme == "dc" and not url.query and not url.fragment, "Invalid DC locator")
    require(url.netloc == str(uuid.UUID(url.netloc)), "Canonical device UUID required")
    root = unquote(url.path[1:])
    require(root and not any(c in root for c in "\0\r\n"), "Invalid DC path")
    if ntpath.splitdrive(root)[0]:
        require(re.fullmatch(r"[A-Za-z]:", ntpath.splitdrive(root)[0]) and ntpath.isabs(root), "Local absolute Windows root required")
        parts = root.replace("\\", "/").split("/")[1:]
        require(all(not any(c in p for c in '<>:"|?*') and not re.fullmatch(r"(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\\..*)?", p) for p in parts if p), "Invalid Windows root component")
        pathmod = ntpath
    else:
        require(root.startswith("/") and not root.startswith("//"), "Absolute root required")
        parts = root.split("/")[1:]
        pathmod = posixpath
    require(all(p not in (".", "..") and not p.endswith((" ", ".")) for p in parts if p), "Ambiguous or traversing root")
    require(quote(root, safe="") == url.path[1:], "Canonical percent-encoded root required")
    return url.netloc, root, pathmod

def validate_contract(c):
    version = c.get("schema_version")
    fields(c, "schema_version project_id repository reference_branch destination authority shared_sources domains transport" + (" decision_sync" if version in (3, 4, 5) else "") + (" work_persistence" if version == 4 or (version == 5 and "work_persistence" in c) else ""))
    require(type(version) is int and version in (1, 2, 3, 4, 5), "Unsupported contract")
    for key in ("project_id", "destination", "authority"):
        text(c[key])
        require("REPLACE_" not in c[key], "Template must be configured")
    git_pending = version in (3, 4, 5) and c["repository"] is None and c["reference_branch"] is None
    if not git_pending:
        for key in ("repository", "reference_branch"):
            text(c[key])
            require("REPLACE_" not in c[key], "Template must be configured")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", c["project_id"]), "Invalid project ID")
    require(git_pending or (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", c["reference_branch"]) and ".." not in c["reference_branch"]), "Invalid branch")
    require(isinstance(c["shared_sources"], list), "Explicit shared_sources required")
    require(isinstance(c["domains"], dict) and bool(c["domains"]), "Explicit domains required")
    all_paths = list(c["shared_sources"]) + [CONTRACT]
    for domain, paths in c["domains"].items():
        text(domain)
        path_list(paths)
        all_paths.extend(paths)
    path_list(sorted(set(all_paths)))
    require(all(PurePosixPath(p).suffix.lower() in (".md", ".txt", ".json", ".csv", ".yaml", ".yml") for p in all_paths), "Only documentary formats allowed")
    require(all(not any(part.casefold() in (".git", ".env", "secrets", "credentials") for part in p.split("/")) for p in all_paths), "Sensitive path excluded")
    if version in (2, 3, 4, 5):
        validate_transport_policy(c["transport"])
        if version in (3, 4, 5):
            validate_decision_config(c)
        if "work_persistence" in c:
            validate_work_persistence(c)
        return
    validate_endpoint(c["transport"], legacy=True)


def validate_work_persistence(c):
    p = c["work_persistence"]
    fields(p, "target registry policy")
    fields(p["target"], "kind project_id container_id")
    target = p["target"]
    require(target["kind"] in ("page-files", "project-sources"), "Unknown Work persistence target")
    for value in (target["project_id"], target["container_id"], p["registry"]):
        text(value)
        require("REPLACE_" not in value, "Work persistence must be qualified")
    require(target["project_id"] == c["destination"], "Wrong Work persistence project")
    require(p["policy"] == {"required": True, "write": "reuse-before-create", "unknown_commit": "inspect-before-retry", "revalidation": "fresh-read-at-mission-start", "transport": "separate-from-publication"}, "Unsafe Work persistence policy")


def validate_decision_config(c):
    d = c["decision_sync"]
    fields(d, "participants sources registries policy")
    for key in ("participants", "sources", "registries"):
        fields(d[key], "work codex")
    for environment in ("work", "codex"):
        fields(d["participants"][environment], "project_id" if c["schema_version"] == 5 else "project_id thread_id")
        values = list(d["participants"][environment].values()) + [d["registries"][environment]]
        require(isinstance(d["sources"][environment], list) and bool(d["sources"][environment]), "Qualified decision sources required")
        values += d["sources"][environment]
        for value in values:
            text(value)
            require("REPLACE_" not in value, "Decision configuration incomplete")
    require(d["participants"]["work"]["project_id"] == c["destination"], "Work project differs from legacy destination")
    if c["schema_version"] != 5:
        require(d["participants"]["work"]["thread_id"] != d["participants"]["codex"]["thread_id"], "Distinct environments required")
    else:
        require(d["participants"]["work"]["project_id"] != d["participants"]["codex"]["project_id"], "Distinct Work/Codex project identities required")
    require(d["policy"] == {"capture": "human-validated-only", "oral": "preserve-existing-validation", "conflicts": "block-and-arbitrate", "git": "review-before-integration", "new_project": "recommend-if-work-and-codex"}, "Unsafe decision policy")


def validate_endpoint(endpoint, legacy=False):
    fields(endpoint, "channel locator account")
    require(endpoint["channel"] in (("manual", "drive", "project-sources", "desktop-commander") if legacy else ("drive", "desktop-commander")), "Unsupported transport")
    for key in ("locator", "account"):
        require(isinstance(endpoint[key], str), "Transport values must be strings")
    if endpoint["channel"] != "manual":
        for key in ("locator", "account"):
            text(endpoint[key])
            require("REPLACE_" not in endpoint[key], "Endpoint must be configured")
    if endpoint["channel"] == "desktop-commander":
        dc_endpoint(endpoint["locator"])
    if endpoint["channel"] == "drive" and not legacy:
        require(re.fullmatch(r"gdrive:folder:[A-Za-z0-9_-]+", endpoint["locator"]), "Canonical Drive folder locator required")


def validate_transport_policy(t):
    fields(t, "primary fallback policy persistence")
    validate_endpoint(t["primary"])
    validate_endpoint(t["fallback"])
    require(t["primary"]["channel"] == "desktop-commander" and t["fallback"]["channel"] == "drive", "DC primary and Drive fallback required")
    fields(t["policy"], "fallback_on uncertain_reception validation_rejected resume")
    require(t["policy"] == {"fallback_on": ["desktop-commander-unavailable"], "uncertain_reception": "collect-before-resume", "validation_rejected": "block", "resume": "same-operation"}, "Unsafe fallback or resume policy")
    fields(t["persistence"], "desktop_commander drive work_sources")
    require(t["persistence"] == {"desktop_commander": "external-folder", "drive": "external-folder", "work_sources": "explicit-ingestion-required"}, "Persistence must distinguish transport from Work Sources")


def select_paths(c, domains):
    require(isinstance(domains, list) and domains and len(set(domains)) == len(domains), "Unique domains required")
    require(all(isinstance(d, str) and d in c["domains"] for d in domains), "Unknown project domain")
    return sorted(set([CONTRACT] + c["shared_sources"] + [p for d in domains for p in c["domains"][d]]))


def validate_requirement(r):
    fields(r, "schema_version project_id repository reference_branch destination source_commit contract_sha256 domains sources authority")
    require(r["schema_version"] == 1, "Unsupported requirement")
    for key in ("project_id", "repository", "reference_branch", "destination", "authority"):
        text(r[key])
    require(isinstance(r["domains"], list) and r["domains"] and all(isinstance(x, str) for x in r["domains"]), "Invalid domains")
    require(r["domains"] == sorted(set(r["domains"])), "Domains must be sorted and unique")
    path_list(r["sources"])
    require(r["sources"] == sorted(r["sources"]), "Sources must be sorted")
    hex_value(r["source_commit"], 40)
    hex_value(r["contract_sha256"], 64)


def bind(c, raw, r):
    validate_contract(c)
    validate_requirement(r)
    for key in ("project_id", "repository", "reference_branch", "destination"):
        require(c[key] == r[key], "Contract/requirement identity mismatch: " + key)
    require(digest(raw) == r["contract_sha256"], "Wrong contract version")
    require(select_paths(c, r["domains"]) == r["sources"], "Contract scope mismatch")


def git(repo, *args, input_data=None):
    result = subprocess.run(["git", "-C", str(repo), *args], input=input_data, capture_output=True)
    require(result.returncode == 0, "Git command failed: " + args[0])
    return result.stdout


def snapshot(repo, commit, path):
    safe_path(path)
    listing = git(repo, "ls-tree", "-z", commit, "--", ":(literal)" + path)
    require(listing.count(b"\x00") == 1, "Source missing or ambiguous: " + path)
    entry = listing[:-1].split(b"\t", 1)
    require(len(entry) == 2 and entry[1].decode("utf-8") == path and entry[0].startswith((b"100644 blob ", b"100755 blob ")), "Source must be regular Git file: " + path)
    blob = entry[0].split()[2].decode("ascii")
    size = int(git(repo, "cat-file", "-s", blob))
    require(size <= MAX_FILE, "Source too large")
    return git(repo, "cat-file", "blob", blob)


def snapshots(repo, commit, paths):
    """Read one exact commit in bounded batches; never cache across operations."""
    path_list(paths)
    require(len(paths) <= MAX_ENTRIES, "Scope too large")
    blobs = {}
    batches, batch, units = [], [], 0
    for path in paths:
        literal = ":(literal)" + path
        cost = len(subprocess.list2cmdline([literal]).encode("utf-16-le")) // 2 + 1
        require(cost <= 12_000, "Source path too long")
        if units + cost > 12_000:
            batches.append(batch)
            batch, units = [], 0
        batch.append(literal)
        units += cost
    batches.append(batch)
    selected = set(paths)
    for batch in batches:
        listing = git(repo, "ls-tree", "-z", "--full-tree", commit, "--", *batch)
        require(not listing or listing.endswith(b"\x00"), "Invalid Git tree response")
        for record in listing.split(b"\x00")[:-1]:
            entry = record.split(b"\t", 1)
            require(len(entry) == 2, "Invalid Git tree entry")
            path = entry[1].decode("utf-8")
            metadata = entry[0].split()
            require(path in selected and path not in blobs and len(metadata) == 3
                    and metadata[0] in (b"100644", b"100755") and metadata[1] == b"blob",
                    "Source missing, ambiguous or not a regular Git file: " + path)
            blob = metadata[2].decode("ascii")
            hex_value(blob, 40)
            blobs[path] = blob
    require(set(blobs) == selected, "Source missing or not a regular Git file")
    # Check every advertised size before requesting blob contents.
    object_ids = list(dict.fromkeys(blobs.values()))
    request = ("\n".join(object_ids) + "\n").encode("ascii")
    checked = git(repo, "cat-file", "--batch-check", input_data=request).splitlines()
    require(len(checked) == len(object_ids), "Incomplete Git size response")
    sizes = {}
    for blob, record in zip(object_ids, checked):
        fields = record.split()
        require(len(fields) == 3 and fields[:2] == [blob.encode("ascii"), b"blob"]
                and fields[2].isdigit(), "Invalid Git size response")
        size = int(fields[2])
        require(size <= MAX_FILE, "Source too large")
        sizes[blob] = size
    require(sum(sizes[blobs[path]] for path in paths) <= MAX_TOTAL, "Scope too large")
    stream = io.BytesIO(git(repo, "cat-file", "--batch", input_data=request))
    contents = {}
    for blob in object_ids:
        expected = (blob + " blob " + str(sizes[blob]) + "\n").encode("ascii")
        require(stream.readline() == expected, "Invalid Git blob response")
        data = stream.read(sizes[blob])
        require(len(data) == sizes[blob] and stream.read(1) == b"\n", "Incomplete Git blob response")
        require(hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest() == blob,
                "Git blob identity mismatch")
        contents[blob] = data
    require(stream.read(1) == b"", "Unexpected Git blob response")
    return {path: contents[blobs[path]] for path in paths}


def source_check(repo, commit, c):
    hex_value(commit, 40)
    require(Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() == repo.resolve(), "Use repository root")
    require(git(repo, "status", "--porcelain", "--untracked-files=all") == b"", "Dirty worktree: establish ownership before proceeding")
    require(git(repo, "remote", "get-url", "origin").decode().strip() == c["repository"], "Wrong repository remote")
    require(git(repo, "symbolic-ref", "--short", "HEAD").decode().strip() == c["reference_branch"], "Wrong active branch")
    require(git(repo, "rev-parse", "HEAD").decode().strip() == commit, "Wrong source HEAD")
    require(git(repo, "rev-parse", "--verify", "refs/heads/" + c["reference_branch"]).decode().strip() == commit, "Wrong reference tip")


def documentary(path, data):
    require(len(data) <= MAX_FILE, "Document too large")
    data.decode("utf-8")
    require(not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16}", data), "Possible secret in " + path)


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(data)


def prepare_requirement(args):
    raw = snapshot(args.repository, args.commit, CONTRACT)
    c = decode(raw)
    validate_contract(c)
    source_check(args.repository, args.commit, c)
    r = {key: c[key] for key in ("project_id", "repository", "reference_branch", "destination")}
    r.update(schema_version=1, source_commit=args.commit, contract_sha256=digest(raw), domains=sorted(args.domain), sources=select_paths(c, args.domain), authority=args.authority)
    validate_requirement(r)
    write_new(args.output, encode(r))
    return {"requirement": str(args.output), "mirror_status": "UNKNOWN"}


def archive_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return stream.getvalue()


def build(args):
    r = load(args.requirement)
    validate_requirement(r)
    raw = snapshot(args.repository, r["source_commit"], CONTRACT)
    c = decode(raw)
    bind(c, raw, r)
    source_check(args.repository, r["source_commit"], c)
    require(len(r["sources"]) <= MAX_ENTRIES, "Scope too large")
    sources = {CONTRACT: raw}
    other_paths = [path for path in r["sources"] if path != CONTRACT]
    if other_paths:
        sources.update(snapshots(args.repository, r["source_commit"], other_paths))
    entries = {}
    for path in r["sources"]:
        data = sources[path]
        documentary(path, data)
        entries["sources/" + path] = data
    require(len(entries) <= MAX_ENTRIES and sum(map(len, entries.values())) <= MAX_TOTAL, "Scope too large")
    inventory = [{"path": p, "size": len(entries["sources/" + p]), "sha256": digest(entries["sources/" + p])} for p in r["sources"]]
    attestation = None
    if args.attestation:
        attestation = load(args.attestation)
        fields(attestation, "requirement_sha256 approved_by authority missing_validated_items")
        require(attestation["requirement_sha256"] == digest(encode(r)) and attestation["missing_validated_items"] == [], "Attestation not bound to exact requirement")
        text(attestation["approved_by"])
        text(attestation["authority"])
    identity = {"requirement": r, "files": inventory, "completeness_attestation": attestation}
    m = {"format": "PROJECT-SYNC", "schema_version": 1, "package_type": "full-scoped", "sync_id": digest(encode(identity)), "requirement": r, "files": inventory, "source_status": "COMPLETE" if attestation else "UNKNOWN", "completeness_attestation": attestation}
    entries["manifest.json"] = encode(m)
    data = archive_bytes(entries)
    verify_zip(data, r)
    write_new(args.output, data)
    if args.carrier:
        write_new(args.carrier, encode({"format": "PROJECT-SYNC-TRANSPORT", "schema_version": 1, "zip_sha256": digest(data), "zip_base64": base64.b64encode(data).decode("ascii")}))
    return {"sync_id": m["sync_id"], "source_status": m["source_status"], "mirror_status": "UNKNOWN", "package_sha256": digest(data)}


def verify_zip(data, r):
    require(len(data) <= MAX_TOTAL, "Archive too large")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = z.infolist()
        require(len(infos) <= MAX_ENTRIES + 1 and sum(i.file_size for i in infos) <= MAX_TOTAL, "Archive expansion too large")
        names = [i.filename for i in infos]
        require(len(names) == len(set(n.casefold() for n in names)), "Duplicate archive entries")
        for i in infos:
            safe_path(i.filename)
            require(not i.is_dir() and i.file_size <= MAX_FILE and not (i.flag_bits & 1), "Invalid archive member")
            mode = i.external_attr >> 16
            require(mode & 0o170000 in (0, 0o100000), "Archive symlink or special file")
        require("manifest.json" in names, "Missing manifest")
        m = decode(z.read("manifest.json"))
        fields(m, "format schema_version package_type sync_id requirement files source_status completeness_attestation")
        require(m["format"] == "PROJECT-SYNC" and m["schema_version"] == 1 and m["package_type"] == "full-scoped", "Unsupported package")
        validate_requirement(r)
        require(m["requirement"] == r, "Package belongs to another requirement")
        require(set(names) == {"manifest.json"} | {"sources/" + p for p in r["sources"]}, "Missing or unexpected source")
        raw = z.read("sources/" + CONTRACT)
        bind(decode(raw), raw, r)
        inventory = []
        entries = {}
        for path in r["sources"]:
            content = z.read("sources/" + path)
            documentary(path, content)
            inventory.append({"path": path, "size": len(content), "sha256": digest(content)})
            entries[path] = content
        require(m["files"] == inventory, "Content checksum or inventory mismatch")
        a = m["completeness_attestation"]
        require(m["source_status"] in ("UNKNOWN", "COMPLETE"), "Invalid source status")
        if a is not None:
            fields(a, "requirement_sha256 approved_by authority missing_validated_items")
            text(a["approved_by"])
            text(a["authority"])
            require(a["requirement_sha256"] == digest(encode(r)) and a["missing_validated_items"] == [] and m["source_status"] == "COMPLETE", "Invalid completeness attestation")
        else:
            require(m["source_status"] == "UNKNOWN", "Completeness not attested")
        require(m["sync_id"] == digest(encode({"requirement": r, "files": inventory, "completeness_attestation": a})), "Wrong sync identity")
        return m, entries


def input_zip(path):
    require(path.stat().st_size <= MAX_TOTAL * 2, "Transport too large")
    raw = path.read_bytes()
    if raw.startswith(b"PK"):
        return raw, raw
    carrier = decode(raw)
    fields(carrier, "format schema_version zip_sha256 zip_base64")
    require(carrier["format"] == "PROJECT-SYNC-TRANSPORT" and carrier["schema_version"] == 1, "Unknown carrier")
    data = base64.b64decode(carrier["zip_base64"], validate=True)
    require(digest(data) == carrier["zip_sha256"], "Carrier checksum mismatch")
    return raw, data


def proof_for(m, r, data, observation):
    fields(observation, "destination artifact_locator retrieved_sha256")
    require(observation["destination"] == r["destination"], "Wrong observed destination")
    text(observation["artifact_locator"])
    hex_value(observation["retrieved_sha256"], 64)
    return {"format": "PROJECT-SYNC-PROOF", "schema_version": 1, "sync_id": m["sync_id"], "requirement_sha256": digest(encode(r)), "project_id": r["project_id"], "source_commit": r["source_commit"], "domains": r["domains"], "sources": r["sources"], "destination": r["destination"], "package_sha256": digest(data), "files": m["files"], "observation": observation, "mirror_status": "CURRENT"}


def check_store(store, r, expected=None):
    require(store.is_dir() and not store.is_symlink(), "Missing regular mirror directory")
    require((store / "package.zip").stat().st_size <= MAX_TOTAL, "Stored package too large")
    m, entries = verify_zip((store / "package.zip").read_bytes(), r)
    actual = set()
    for p in store.rglob("*"):
        require(not p.is_symlink(), "Mirror contains symlink")
        if p.is_file():
            actual.add(p.relative_to(store).as_posix())
    require(actual == {"package.zip", "proof.json"} | {"sources/" + p for p in entries}, "Unexpected mirror files")
    for path, data in entries.items():
        require((store / "sources" / path).read_bytes() == data, "Mirror was modified: " + path)
    proof = load(store / "proof.json")
    require(proof == proof_for(m, r, (store / "package.zip").read_bytes(), proof["observation"]), "Invalid mirror proof")
    if expected:
        require(proof == expected, "Proof mismatch after installation")
    return proof


def receive(args):
    r = load(args.requirement)
    raw, data = input_zip(args.input)
    m, entries = verify_zip(data, r)
    o = load(args.observation)
    proof = proof_for(m, r, data, o)
    require(o["retrieved_sha256"] == digest(raw), "Observation does not match reread transport")
    require(not args.store.exists(), "Use a new operation directory; preserve previous mirror")
    require(not args.output.exists(), "Proof output already exists")
    args.store.parent.mkdir(parents=True, exist_ok=True)
    args.store.mkdir()
    write_new(args.store / "package.zip", data)
    for path, content in entries.items():
        write_new(args.store / "sources" / path, content)
    write_new(args.store / "proof.json", encode(proof))
    check_store(args.store, r, proof)
    write_new(args.output, encode(proof))
    return proof


def accept(args):
    r = load(args.requirement)
    raw, data = input_zip(args.input)
    m, entries = verify_zip(data, r)
    p = load(args.proof)
    expected = proof_for(m, r, data, p["observation"])
    require(p == expected, "Destination proof does not match expected package")
    require(p["observation"]["retrieved_sha256"] == digest(raw), "Proof does not identify the actual transported artifact")
    e = load(args.evidence)
    fields(e, "destination destination_thread artifact_locator proof_locator proof_sha256 authenticated_channel authority")
    for value in e.values():
        text(value)
    require(e["destination"] == r["destination"] and e["artifact_locator"] == p["observation"]["artifact_locator"], "Wrong proof origin")
    require(e["proof_sha256"] == digest(args.proof.read_bytes()), "Proof reread checksum mismatch")
    result = {"mirror_status": "CURRENT", "project_id": r["project_id"], "source_commit": r["source_commit"], "domains": r["domains"], "sync_id": m["sync_id"], "source_status": m["source_status"], "destination": r["destination"], "evidence": e}
    if "work_persistence" in decode(entries[CONTRACT]):
        result.update(completion_status="RECEIVED_VERIFIED_PERSISTENCE_PENDING", work_availability="NOT_VERIFIED")
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    req = sub.add_parser("requirement", help="Create independent expectation from configured exact Git HEAD")
    req.add_argument("--repository", type=Path, required=True)
    req.add_argument("--commit", required=True)
    req.add_argument("--domain", action="append", required=True)
    req.add_argument("--authority", required=True)
    req.add_argument("--output", type=Path, required=True)
    b = sub.add_parser("build", help="Create full package, initially mirror UNKNOWN")
    b.add_argument("--repository", type=Path, required=True)
    b.add_argument("--requirement", type=Path, required=True)
    b.add_argument("--output", type=Path, required=True)
    b.add_argument("--carrier", type=Path)
    b.add_argument("--attestation", type=Path)
    for command in ("verify", "receive", "check", "accept"):
        q = sub.add_parser(command)
        q.add_argument("--requirement", type=Path, required=True)
        if command != "check":
            q.add_argument("--input", type=Path, required=True)
        if command in ("receive", "check"):
            q.add_argument("--store", type=Path, required=True)
        if command == "receive":
            q.add_argument("--observation", type=Path, required=True)
            q.add_argument("--output", type=Path, required=True)
        if command == "accept":
            q.add_argument("--proof", type=Path, required=True)
            q.add_argument("--evidence", type=Path, required=True)
    return p


def main():
    utf8_stdio()
    args = parser().parse_args()
    try:
        if args.command == "requirement":
            result = prepare_requirement(args)
        elif args.command == "build":
            result = build(args)
        elif args.command == "receive":
            result = receive(args)
        elif args.command == "accept":
            result = accept(args)
        elif args.command == "check":
            result = check_store(args.store, load(args.requirement))
        else:
            _, data = input_zip(args.input)
            m, _ = verify_zip(data, load(args.requirement))
            result = {"sync_id": m["sync_id"], "source_status": m["source_status"], "mirror_status": "UNKNOWN"}
        print(encode(result).decode(), end="")
        return 0
    except (SyncError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        print(encode({"mirror_status": "UNKNOWN", "error": str(exc)}).decode(), end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
