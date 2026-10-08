#!/usr/bin/env python3
"""Offline preparation and receipt gate; actual DC calls belong to the pilot."""
from __future__ import annotations
import argparse
import importlib.util
import sys
import uuid
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

module_path = Path(__file__).resolve().parents[2] / "syncpilot-codex/scripts/project_sync.py"
spec = importlib.util.spec_from_file_location("project_sync_dc_core", module_path)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

endpoint = core.dc_endpoint

def location(device, path):
    return "dc://" + device + "/" + quote(path, safe="")

def profile(contract):
    core.validate_contract(contract)
    transport = contract["transport"]
    core.require(transport["channel"] == "desktop-commander", "DC must be selected explicitly")
    device, root, pathmod = endpoint(transport["locator"])
    return device, root, pathmod

def prepare(args):
    artifacts = []
    if args.kind == "document-sync":
        core.require(args.input and args.requirement and not args.contract and not args.files and not args.mission, "Document sync requires only carrier and independent requirement")
        r = core.load(args.requirement)
        raw, archive = core.input_zip(args.input)
        core.require(not raw.startswith(b"PK"), "Use exact canonical text carrier for DC write_file")
        manifest, entries = core.verify_zip(archive, r)
        contract = core.decode(entries[core.CONTRACT])
        identity = {"project_id": r["project_id"], "destination": r["destination"], "sync_id": manifest["sync_id"], "source_commit": r["source_commit"], "requirement_sha256": core.digest(core.encode(r))}
        artifacts = [(args.input, "carrier.json", raw), (args.requirement, "requirement.json", args.requirement.read_bytes())]
    else:
        core.require(args.contract and args.files and args.mission and not args.input and not args.requirement, "Mission return requires explicit profile, mission and report files")
        contract = core.load(args.contract)
        core.text(args.mission)
        core.require(len(args.mission) <= 128 and all(c.isalnum() or c in "-_." for c in args.mission), "Invalid mission ID")
        identity = {"project_id": contract["project_id"], "destination": contract["destination"], "mission_id": args.mission, "contract_sha256": core.digest(args.contract.read_bytes())}
        core.require(len(args.files) <= core.MAX_ENTRIES, "Too many reports")
        for file in args.files:
            core.safe_path(file.name)
            core.require(file.is_file() and not file.is_symlink() and file.suffix.lower() in (".md", ".txt", ".json"), "Only explicit regular text reports")
            core.require(file.stat().st_size <= core.MAX_FILE, "Report too large")
            raw = file.read_bytes()
            core.documentary(file.name, raw)
            artifacts.append((file, file.name, raw))
    core.text(args.thread)
    core.text(args.authority)
    core.path_list([name for _, name, _ in artifacts])
    core.require(sum(len(raw) for _, _, raw in artifacts) <= core.MAX_TOTAL, "Transfer too large")
    device, root, pathmod = profile(contract)
    nonce = str(uuid.uuid4())
    bound_files = [{"name": name, "size": len(raw), "sha256": core.digest(raw)} for _, name, raw in artifacts]
    operation = core.digest(core.encode({"kind": args.kind, "identity": identity, "nonce": nonce, "thread": args.thread, "device_id": device, "account": contract["transport"]["account"], "authority": args.authority, "files": bound_files}))
    operation_root = pathmod.join(root, contract["project_id"], operation)
    inventory = []
    for source, name, raw in artifacts:
        target = pathmod.join(operation_root, name)
        inventory.append({"name": name, "source": str(source.resolve()), "target": target, "locator": location(device, target), "size": len(raw), "sha256": core.digest(raw)})
    return {"format": "PROJECT-SYNC-DC-PLAN", "schema_version": 1, "kind": args.kind, "operation_id": operation, "nonce": nonce, "identity": identity, "destination_thread": args.thread, "device_id": device, "account": contract["transport"]["account"], "authority": args.authority, "receipt_locator": location(device, pathmod.join(operation_root, "receipt.json")), "artifacts": inventory, "state": "PREPARED", "canonical_mirror_changed": False}

def confirm(args):
    plan = core.load(args.plan)
    core.fields(plan, "format schema_version kind operation_id nonce identity destination_thread device_id account authority receipt_locator artifacts state canonical_mirror_changed")
    core.require(plan["format"] == "PROJECT-SYNC-DC-PLAN" and plan["schema_version"] == 1 and plan["state"] == "PREPARED" and plan["canonical_mirror_changed"] is False, "Unsupported plan")
    core.require(plan["kind"] in ("document-sync", "mission-return"), "Unknown transfer kind")
    core.require(str(uuid.UUID(plan["nonce"])) == plan["nonce"], "Invalid nonce")
    core.hex_value(plan["operation_id"], 64)
    receipt = core.load(args.receipt)
    core.fields(receipt, "format schema_version operation_id nonce identity destination_thread status files proof_sha256")
    core.require(receipt["format"] == "PROJECT-SYNC-DC-RECEIPT" and receipt["schema_version"] == 1 and receipt["status"] == "RECEIVED_VERIFIED", "No verified receipt")
    for key in ("operation_id", "nonce", "identity", "destination_thread"):
        core.require(receipt[key] == plan[key], "Wrong receipt " + key)
    core.require(isinstance(plan["artifacts"], list) and bool(plan["artifacts"]), "Nonempty inventory required")
    core.path_list([e["name"] for e in plan["artifacts"]])
    expected = []
    for entry in plan["artifacts"]:
        core.fields(entry, "name source target locator size sha256")
        core.safe_path(entry["name"])
        core.hex_value(entry["sha256"], 64)
        core.require(type(entry["size"]) is int and 0 <= entry["size"] <= core.MAX_TOTAL * 2, "Invalid byte size")
        device, path, _ = endpoint(entry["locator"])
        core.require(device == plan["device_id"] and path == entry["target"], "Wrong artifact device or target")
        expected.append({"name": entry["name"], "size": entry["size"], "sha256": entry["sha256"]})
    binding = {"kind": plan["kind"], "identity": plan["identity"], "nonce": plan["nonce"], "thread": plan["destination_thread"], "device_id": plan["device_id"], "account": plan["account"], "authority": plan["authority"], "files": expected}
    core.require(plan["operation_id"] == core.digest(core.encode(binding)), "Plan identity or inventory changed")
    core.require(receipt["files"] == expected, "Incomplete receipt or byte mismatch")
    observed = core.load(args.observation)
    core.fields(observed, "device_id destination_thread receipt_locator receipt_sha256 authenticated_channel authority")
    for key in ("device_id", "destination_thread", "receipt_locator"):
        core.require(observed[key] == plan[key], "Wrong observed origin " + key)
    core.require(observed["authenticated_channel"] == "remote-desktop-commander", "Authenticated DC observation required")
    core.text(observed["authority"])
    core.require(observed["receipt_sha256"] == core.digest(args.receipt.read_bytes()), "Receipt bytes not reread")
    result = {"state": "RECEIPT_VERIFIED", "operation_id": plan["operation_id"], "kind": plan["kind"], "canonical_mirror_changed": False, "identity_authentication": "pilot-qualified; JSON alone is not an identity signature"}
    if plan["kind"] == "document-sync":
        core.require(args.input and args.requirement and args.proof and args.evidence, "Canonical acceptance inputs required")
        r = core.load(args.requirement)
        raw, archive = core.input_zip(args.input)
        m, entries = core.verify_zip(archive, r)
        contract = core.decode(entries[core.CONTRACT])
        device, base_root, pathmod = profile(contract)
        core.require(device == plan["device_id"] and contract["transport"]["account"] == plan["account"], "Wrong contract endpoint")
        identity = {"project_id": r["project_id"], "destination": r["destination"], "sync_id": m["sync_id"], "source_commit": r["source_commit"], "requirement_sha256": core.digest(core.encode(r))}
        core.require(identity == plan["identity"], "Wrong canonical sync identity")
        operation_root = pathmod.join(base_root, contract["project_id"], plan["operation_id"])
        core.require(plan["receipt_locator"] == location(device, pathmod.join(operation_root, "receipt.json")), "Receipt outside configured root")
        for entry in plan["artifacts"]:
            core.require(entry["target"] == pathmod.join(operation_root, entry["name"]), "Artifact outside configured root")
        by_name = {entry["name"]: entry for entry in expected}
        core.require(by_name == {"carrier.json": {"name": "carrier.json", "size": len(raw), "sha256": core.digest(raw)}, "requirement.json": {"name": "requirement.json", "size": args.requirement.stat().st_size, "sha256": core.digest(args.requirement.read_bytes())}}, "Canonical input bytes changed")
        core.require(receipt["proof_sha256"] == core.digest(args.proof.read_bytes()), "Canonical proof not bound to receipt")
        accepted = core.accept(args)
        core.require(accepted["evidence"]["destination_thread"] == plan["destination_thread"] and accepted["evidence"]["artifact_locator"] == next(e["locator"] for e in plan["artifacts"] if e["name"] == "carrier.json"), "Wrong canonical receipt origin")
        result["canonical_acceptance"] = accepted
    else:
        core.require(receipt["proof_sha256"] is None and not any((args.input, args.requirement, args.proof, args.evidence)), "Mission reports do not establish a canonical mirror")
        core.require(args.contract, "Independent mission profile required")
        contract = core.load(args.contract)
        core.require(core.digest(args.contract.read_bytes()) == plan["identity"]["contract_sha256"], "Mission profile changed")
        device, base_root, pathmod = profile(contract)
        core.require(contract["project_id"] == plan["identity"]["project_id"] and contract["destination"] == plan["identity"]["destination"] and device == plan["device_id"] and contract["transport"]["account"] == plan["account"], "Wrong mission profile")
        operation_root = pathmod.join(base_root, contract["project_id"], plan["operation_id"])
        core.require(plan["receipt_locator"] == location(device, pathmod.join(operation_root, "receipt.json")), "Receipt outside configured root")
        for entry in plan["artifacts"]:
            core.require(entry["target"] == pathmod.join(operation_root, entry["name"]), "Report outside configured root")
    return result

def main():
    core.utf8_stdio()
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--kind", choices=("document-sync", "mission-return"), required=True)
    for name in ("input", "requirement", "contract"):
        plan.add_argument("--" + name, type=Path)
    plan.add_argument("--file", dest="files", type=Path, action="append")
    plan.add_argument("--mission")
    plan.add_argument("--thread", required=True)
    plan.add_argument("--authority", required=True)
    plan.add_argument("--output", type=Path, required=True)
    ack = sub.add_parser("confirm")
    for name in ("plan", "receipt", "observation"):
        ack.add_argument("--" + name, type=Path, required=True)
    for name in ("input", "requirement", "proof", "evidence", "contract"):
        ack.add_argument("--" + name, type=Path)
    args = p.parse_args()
    try:
        result = prepare(args) if args.command == "plan" else confirm(args)
        if args.command == "plan":
            core.write_new(args.output, core.encode(result))
        print(core.encode(result).decode("utf-8"), end="")
        return 0
    except (core.SyncError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(core.encode({"state": "NOT_VERIFIED", "error": str(exc)}).decode("utf-8"), end="")
        return 2

if __name__ == "__main__":
    sys.exit(main())
