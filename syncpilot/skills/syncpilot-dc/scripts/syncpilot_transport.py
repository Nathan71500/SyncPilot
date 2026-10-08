#!/usr/bin/env python3
"""Offline SyncPilot operation gate. Connectors are called by the pilot, never here."""
from __future__ import annotations
import argparse
import copy
import importlib.util
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

spec = importlib.util.spec_from_file_location("syncpilot_core", Path(__file__).resolve().parents[2] / "syncpilot-codex/scripts/project_sync.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
POLICY = {"fallback_on": ["desktop-commander-unavailable"], "uncertain_reception": "collect-before-resume", "validation_rejected": "block", "resume": "same-operation"}
PERSISTENCE = {"desktop_commander": "external-folder", "drive": "external-folder", "work_sources": "explicit-ingestion-required"}
EVENTS = ("DEPOSITED", "RECEIVED", "TRANSPORT_FAILED", "DC_UNAVAILABLE", "RECEPTION_UNCERTAIN", "VALIDATION_REJECTED", "VERIFIED")


def now():
    return datetime.now(timezone.utc).isoformat()


def profiles(contract):
    core.validate_contract(contract)
    if contract["schema_version"] == 1:
        return {"primary": contract["transport"]}
    return {key: contract["transport"][key] for key in ("primary", "fallback")}


def prepare(input_path, requirement_path, thread, authority):
    r = core.load(requirement_path)
    raw, archive = core.input_zip(input_path)
    m, entries = core.verify_zip(archive, r)
    c = core.decode(entries[core.CONTRACT])
    core.require(not raw.startswith(b"PK"), "Text carrier required for a shared DC/Drive operation")
    core.text(thread)
    core.text(authority)
    identity = {"project_id": r["project_id"], "destination": r["destination"], "source_commit": r["source_commit"], "sync_id": m["sync_id"], "requirement_sha256": core.digest(core.encode(r)), "contract_sha256": r["contract_sha256"]}
    operation = {"nonce": str(uuid.uuid4()), "identity": identity, "destination_thread": thread, "authority": authority, "profiles": profiles(c), "files": [{"name": "carrier.json", "size": len(raw), "sha256": core.digest(raw)}, {"name": "requirement.json", "size": requirement_path.stat().st_size, "sha256": core.digest(requirement_path.read_bytes())}]}
    operation["operation_id"] = core.digest(core.encode(operation))
    return {"format": "SYNCPILOT-OPERATION", "schema_version": 1, "operation": operation, "events": []}


def validate(j):
    core.fields(j, "format schema_version operation events")
    core.require(j["format"] == "SYNCPILOT-OPERATION" and j["schema_version"] == 1, "Unknown operation")
    op = j["operation"]
    core.fields(op, "operation_id nonce identity destination_thread authority profiles files")
    binding = {k: v for k, v in op.items() if k != "operation_id"}
    core.require(op["operation_id"] == core.digest(core.encode(binding)), "Operation identity changed")
    core.require(str(uuid.UUID(op["nonce"])) == op["nonce"], "Invalid nonce")
    core.fields(op["identity"], "project_id destination source_commit sync_id requirement_sha256 contract_sha256")
    for key in ("sync_id", "requirement_sha256", "contract_sha256"):
        core.hex_value(op["identity"][key], 64)
    core.hex_value(op["identity"]["source_commit"], 40)
    core.text(op["destination_thread"])
    core.text(op["authority"])
    core.require(set(op["profiles"]) in ({"primary"}, {"primary", "fallback"}), "Unknown profiles")
    for p in op["profiles"].values():
        core.validate_endpoint(p, legacy=len(op["profiles"]) == 1)
    if "fallback" in op["profiles"]:
        core.require(op["profiles"]["primary"]["channel"] == "desktop-commander" and op["profiles"]["fallback"]["channel"] == "drive", "Invalid channel priority")
    core.require([f["name"] for f in op["files"]] == ["carrier.json", "requirement.json"], "Wrong operation files")
    for f in op["files"]:
        core.fields(f, "name size sha256")
        core.require(type(f["size"]) is int and 0 <= f["size"] <= core.MAX_TOTAL * 2, "Invalid file size")
        core.hex_value(f["sha256"], 64)
    core.require(isinstance(j["events"], list), "Invalid history")
    prior = {**j, "events": []}
    for e in j["events"]:
        core.fields(e, "status channel delivery reference observed_at previous_sha256")
        core.require(e["previous_sha256"] == core.digest(core.encode(prior)), "History binding changed")
        check_event(prior, e)
        prior["events"] = prior["events"] + [e]
    return op


def state(j):
    statuses = [e["status"] for e in j["events"]]
    if "VALIDATION_REJECTED" in statuses:
        return "BLOCKED"
    if "VERIFIED" in statuses:
        return "VERIFIED"
    for e in reversed(j["events"]):
        if e["status"] in ("DEPOSITED", "RECEIVED", "RECEPTION_UNCERTAIN"):
            return e["status"]
    return "PREPARED"


def check_event(j, e):
    core.require(state(j) not in ("BLOCKED", "VERIFIED"), "Operation is terminal")
    core.require(e["status"] in EVENTS and e["channel"] in j["operation"]["profiles"], "Invalid transition")
    if e["channel"] == "fallback":
        core.require(any(prior["status"] == "DC_UNAVAILABLE" and prior["delivery"] == "not-delivered" for prior in j["events"]), "Drive requires a previously observed DC unavailability and conclusive non-delivery")
    core.require(e["delivery"] in ("not-delivered", "unknown", "present"), "Invalid delivery certainty")
    core.text(e["reference"])
    core.text(e["observed_at"])
    if e["status"] == "DC_UNAVAILABLE":
        core.require(e["channel"] == "primary" and j["operation"]["profiles"]["primary"]["channel"] == "desktop-commander", "Only primary DC can be unavailable")
    if e["status"] in ("DEPOSITED", "RECEIVED", "VERIFIED"):
        core.require(e["delivery"] == "present", "Observed bytes required")


def record(j, status, channel, delivery, reference):
    core.require(status != "VERIFIED", "VERIFIED requires confirm with independent destination proof")
    return append_event(j, status, channel, delivery, reference)


def append_event(j, status, channel, delivery, reference):
    validate(j)
    e = {"status": status, "channel": channel, "delivery": delivery, "reference": reference, "observed_at": now(), "previous_sha256": core.digest(core.encode(j))}
    check_event(j, e)
    result = copy.deepcopy(j)
    result["events"].append(e)
    validate(result)
    return result


def validate_discovery(j, d):
    op = validate(j)
    core.fields(d, "operation_id nonce journal_sha256 results authority observed_at")
    core.require(d["operation_id"] == op["operation_id"] and d["nonce"] == op["nonce"] and d["journal_sha256"] == core.digest(core.encode(j)), "Stale or wrong discovery")
    core.text(d["authority"])
    core.text(d["observed_at"])
    core.require(set(d["results"]) == set(op["profiles"]), "Search every configured channel before resume")
    for name, finding in d["results"].items():
        core.fields(finding, "status reference")
        core.require(finding["status"] in ("absent", "unavailable", "available", "rejected"), "Invalid discovery")
        core.text(finding["reference"])
    return op


def plan(j, d, channel):
    op = validate_discovery(j, d)
    core.require(channel in op["profiles"], "Channel not configured")
    statuses = [v["status"] for v in d["results"].values()]
    if state(j) == "BLOCKED" or "rejected" in statuses:
        return {"action": "BLOCKED", "operation_id": op["operation_id"], "reason": "Validation rejection cannot be bypassed"}
    if state(j) == "VERIFIED":
        return {"action": "DONE", "operation_id": op["operation_id"]}
    if "available" in statuses:
        return {"action": "COLLECT_EXISTING", "operation_id": op["operation_id"], "reason": "Inspect existing artifacts/receipts/proofs; never upload again"}
    if state(j) in ("DEPOSITED", "RECEIVED", "RECEPTION_UNCERTAIN") or any(e["delivery"] != "not-delivered" for e in j["events"] if e["status"] in ("TRANSPORT_FAILED", "DC_UNAVAILABLE")):
        return {"action": "BLOCKED", "operation_id": op["operation_id"], "reason": "Reception uncertain; collect or obtain conclusive non-delivery before any retry"}
    if channel == "fallback":
        unavailable = any(e["status"] == "DC_UNAVAILABLE" and e["delivery"] == "not-delivered" for e in j["events"])
        core.require(unavailable and d["results"]["primary"]["status"] == "unavailable", "Drive only while Desktop Commander is unavailable")
    else:
        core.require(d["results"]["primary"]["status"] == "absent", "Primary endpoint unavailable")
    core.require(d["results"][channel]["status"] == "absent", "Selected endpoint not confirmed empty")
    p = op["profiles"][channel]
    if p["channel"] == "desktop-commander":
        device, root, pathmod = core.dc_endpoint(p["locator"])
        targets = {f["name"]: "dc://" + device + "/" + quote(pathmod.join(root, op["identity"]["project_id"], op["operation_id"], f["name"]), safe="") for f in op["files"]}
        receipt = "dc://" + device + "/" + quote(pathmod.join(root, op["identity"]["project_id"], op["operation_id"], "receipt.json"), safe="")
    else:
        core.require(p["channel"] == "drive", "Legacy manual transport uses explicit handoff; no generated network plan")
        targets = {f["name"]: {"parent": p["locator"], "name": op["operation_id"] + "-" + f["name"]} for f in op["files"]}
        receipt = {"parent": p["locator"], "name": op["operation_id"] + "-receipt.json"}
    return {"action": "DEPOSIT_ONCE", "operation_id": op["operation_id"], "nonce": op["nonce"], "channel": channel, "profile": p, "files": op["files"], "targets": targets, "receipt_target": receipt, "state": state(j)}


def confirm(j, receipt_path, observation, input_path, requirement_path, proof_path, evidence_path):
    op = validate(j)
    core.require(state(j) not in ("BLOCKED", "VERIFIED"), "Operation terminal")
    receipt = core.load(receipt_path)
    core.fields(receipt, "format schema_version operation_id nonce identity destination_thread channel status files proof_sha256")
    core.require(receipt["format"] == "SYNCPILOT-RECEIPT" and receipt["schema_version"] == 1 and receipt["status"] == "RECEIVED_VERIFIED", "Independent verified receipt required")
    for key in ("operation_id", "nonce", "identity", "destination_thread", "files"):
        core.require(receipt[key] == op[key], "Receipt mismatch: " + key)
    channel = receipt["channel"]
    core.require(channel in op["profiles"], "Wrong receipt channel")
    profile = op["profiles"][channel]
    core.fields(observation, "destination destination_thread channel account storage_root receipt_locator receipt_sha256 artifact_locator proof_locator authenticated_channel authority work_finished")
    core.require(observation["destination"] == op["identity"]["destination"] and observation["destination_thread"] == op["destination_thread"], "Wrong observed destination")
    core.require(observation["channel"] == channel and observation["account"] == profile["account"] and observation["work_finished"] is True, "Origin or execution not qualified")
    core.require(observation["storage_root"] == profile["locator"], "Wrong observed storage root")
    core.require(observation["authenticated_channel"] == profile["channel"], "Wrong authenticated channel")
    for key in ("authority", "receipt_locator", "artifact_locator"):
        core.text(observation[key])
    core.require(observation["receipt_sha256"] == core.digest(receipt_path.read_bytes()), "Receipt bytes not reread")
    if profile["channel"] == "desktop-commander":
        device, root, pm = core.dc_endpoint(profile["locator"])
        base = pm.join(root, op["identity"]["project_id"], op["operation_id"])
        for key, name in (("receipt_locator", "receipt.json"), ("artifact_locator", "carrier.json"), ("proof_locator", "proof.json")):
            actual_device, path, _ = core.dc_endpoint(observation[key])
            core.require(actual_device == device and path == pm.join(base, name), "DC object outside exact operation root")
    else:
        core.require(profile["channel"] == "drive" and all(value.startswith("gdrive:file:") for value in (observation["receipt_locator"], observation["artifact_locator"], observation["proof_locator"])), "Exact Drive file locators required")
    core.require(receipt["proof_sha256"] == core.digest(proof_path.read_bytes()), "Proof not bound to receipt")
    raw, archive = core.input_zip(input_path)
    req_raw = requirement_path.read_bytes()
    core.require(op["files"] == [{"name": "carrier.json", "size": len(raw), "sha256": core.digest(raw)}, {"name": "requirement.json", "size": len(req_raw), "sha256": core.digest(req_raw)}], "Operation bytes changed")
    req = core.load(requirement_path)
    m, entries = core.verify_zip(archive, req)
    contract = core.decode(entries[core.CONTRACT])
    core.require(profiles(contract) == op["profiles"] and req["contract_sha256"] == op["identity"]["contract_sha256"] and m["sync_id"] == op["identity"]["sync_id"], "Operation not bound to package contract")
    evidence = core.load(evidence_path)
    core.require(evidence["destination_thread"] == op["destination_thread"] and evidence["artifact_locator"] == observation["artifact_locator"] and evidence["proof_locator"] == observation["proof_locator"], "Canonical proof origin differs")
    accepted = core.accept(argparse.Namespace(input=input_path, requirement=requirement_path, proof=proof_path, evidence=evidence_path))
    updated = append_event(j, "VERIFIED", channel, "present", observation["authority"])
    return updated, accepted


def migrate(contract_path, primary, fallback):
    c = core.load(contract_path)
    core.validate_contract(c)
    core.require(c["schema_version"] == 1, "Only an explicit v1 migration is supported")
    core.require(c["transport"]["channel"] in ("desktop-commander", "drive", "manual"), "Project Sources require an explicit project-specific migration; preserve the v1 contract")
    if c["transport"]["channel"] == "manual":
        core.require(c["transport"]["locator"] == "" and c["transport"]["account"] == "", "Preserve nonempty manual settings with a reviewed project-specific migration")
    core.validate_endpoint(primary)
    core.validate_endpoint(fallback)
    if c["transport"]["channel"] == "desktop-commander":
        core.require(c["transport"] == primary, "Preserve existing DC configuration")
    if c["transport"]["channel"] == "drive":
        core.require(c["transport"] == fallback, "Preserve existing Drive configuration")
    migrated = copy.deepcopy(c)
    migrated["schema_version"] = 2
    migrated["transport"] = {"primary": primary, "fallback": fallback, "policy": POLICY, "persistence": PERSISTENCE}
    core.validate_contract(migrated)
    return migrated


def main():
    core.utf8_stdio()
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for key in ("input", "requirement", "output"):
        prep.add_argument("--" + key, type=Path, required=True)
    prep.add_argument("--thread", required=True)
    prep.add_argument("--authority", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--journal", type=Path, required=True)
    pl.add_argument("--discovery", type=Path, required=True)
    pl.add_argument("--channel", choices=("primary", "fallback"), default="primary")
    rec = sub.add_parser("record")
    rec.add_argument("--journal", type=Path, required=True)
    rec.add_argument("--status", choices=tuple(x for x in EVENTS if x != "VERIFIED"), required=True)
    rec.add_argument("--channel", choices=("primary", "fallback"), required=True)
    rec.add_argument("--delivery", choices=("not-delivered", "unknown", "present"), required=True)
    rec.add_argument("--reference", required=True)
    rec.add_argument("--output", type=Path, required=True)
    ack = sub.add_parser("confirm")
    for key in ("journal", "receipt", "observation", "input", "requirement", "proof", "evidence", "output"):
        ack.add_argument("--" + key, type=Path, required=True)
    mig = sub.add_parser("migrate")
    for key in ("contract", "primary", "fallback", "output"):
        mig.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.input, args.requirement, args.thread, args.authority)
        elif args.command == "record":
            result = record(core.load(args.journal), args.status, args.channel, args.delivery, args.reference)
        elif args.command == "plan":
            result = plan(core.load(args.journal), core.load(args.discovery), args.channel)
        elif args.command == "migrate":
            result = migrate(args.contract, core.load(args.primary), core.load(args.fallback))
        else:
            result, accepted = confirm(core.load(args.journal), args.receipt, core.load(args.observation), args.input, args.requirement, args.proof, args.evidence)
        if hasattr(args, "output"):
            core.write_new(args.output, core.encode(result))
        print(core.encode({"journal": result, "acceptance": accepted} if args.command == "confirm" else result).decode(), end="")
        return 0
    except (core.SyncError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(core.encode({"state": "BLOCKED", "mirror_status": "UNKNOWN", "error": str(exc)}).decode(), end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
