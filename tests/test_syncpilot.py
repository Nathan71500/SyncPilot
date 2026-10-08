"""Isolated simulations: these tests never assert a real Work reception."""
import argparse
import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "syncpilot/skills/syncpilot-dc/scripts/syncpilot_transport.py"
spec = importlib.util.spec_from_file_location("transport", SCRIPT)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
c = t.core
DEVICE = "11111111-1111-4111-8111-111111111111"


class SyncPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.primary = {"channel": "desktop-commander", "locator": "dc://" + DEVICE + "/" + quote("/test/isolated", safe=""), "account": "test-dc"}
        self.fallback = {"channel": "drive", "locator": "gdrive:folder:TEST_ONLY", "account": "test-drive"}
        self.contract = {"schema_version": 2, "project_id": "fixture", "repository": "https://example.invalid/fixture", "reference_branch": "main", "destination": "test:work", "authority": "TEST ONLY", "shared_sources": [], "domains": {"docs": ["docs.txt"]}, "transport": {"primary": self.primary, "fallback": self.fallback, "policy": t.POLICY, "persistence": t.PERSISTENCE}}
        (self.repo / c.CONTRACT).write_bytes(c.encode(self.contract))
        (self.repo / "docs.txt").write_text("Document témoin TEST ONLY\n", encoding="utf-8")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("remote", "add", "origin", self.contract["repository"])
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-m", "TEST ONLY")
        self.req = self.root / "requirement.json"
        c.prepare_requirement(argparse.Namespace(repository=self.repo, commit=self.git("rev-parse", "HEAD"), domain=["docs"], authority="TEST ONLY", output=self.req))
        self.package = self.root / "package.zip"
        self.carrier = self.root / "carrier.json"
        c.build(argparse.Namespace(repository=self.repo, requirement=self.req, output=self.package, carrier=self.carrier, attestation=None))
        self.j = t.prepare(self.carrier, self.req, "test:thread", "TEST ONLY")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=True).stdout.decode().strip()

    def discovery(self, j=None, primary="absent", fallback="absent"):
        j = j or self.j
        return {"operation_id": j["operation"]["operation_id"], "nonce": j["operation"]["nonce"], "journal_sha256": c.digest(c.encode(j)), "authority": "TEST ONLY", "observed_at": t.now(), "results": {"primary": {"status": primary, "reference": "TEST ONLY observed DC"}, "fallback": {"status": fallback, "reference": "TEST ONLY observed Drive"}}}

    def test_dc_primary_and_no_drive_when_available(self):
        self.assertEqual(t.plan(self.j, self.discovery(), "primary")["action"], "DEPOSIT_ONCE")
        with self.assertRaises(c.SyncError):
            t.plan(self.j, self.discovery(), "fallback")

    def test_fallback_keeps_identity_and_nonce(self):
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY offline")
        p = t.plan(j, self.discovery(j, primary="unavailable"), "fallback")
        self.assertEqual(p["action"], "DEPOSIT_ONCE")
        self.assertEqual(p["operation_id"], self.j["operation"]["operation_id"])
        self.assertEqual(p["nonce"], self.j["operation"]["nonce"])
        self.assertEqual(p["files"], self.j["operation"]["files"])

    def test_generic_failure_does_not_enable_drive(self):
        j = t.record(self.j, "TRANSPORT_FAILED", "primary", "not-delivered", "TEST ONLY encoding failure")
        with self.assertRaises(c.SyncError):
            t.plan(j, self.discovery(j, primary="unavailable"), "fallback")

    def test_dc_recovered_before_fallback(self):
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY")
        with self.assertRaises(c.SyncError):
            t.plan(j, self.discovery(j), "fallback")
        self.assertEqual(t.plan(j, self.discovery(j), "primary")["action"], "DEPOSIT_ONCE")

    def test_interrupted_deposit_collects_without_duplicate(self):
        j = t.record(self.j, "DEPOSITED", "primary", "present", "TEST ONLY readback")
        self.assertEqual(t.plan(j, self.discovery(j, primary="available"), "primary")["action"], "COLLECT_EXISTING")
        self.assertEqual(t.plan(j, self.discovery(j, primary="unavailable"), "fallback")["action"], "BLOCKED")

    def test_uncertain_delivery_blocks_both_channels(self):
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "unknown", "TEST ONLY timed out after write")
        for channel in ("primary", "fallback"):
            self.assertEqual(t.plan(j, self.discovery(j, primary="unavailable"), channel)["action"], "BLOCKED")

    def test_rejection_is_terminal(self):
        j = t.record(self.j, "VALIDATION_REJECTED", "primary", "present", "TEST ONLY wrong identity")
        for channel in ("primary", "fallback"):
            self.assertEqual(t.plan(j, self.discovery(j, primary="unavailable"), channel)["action"], "BLOCKED")
        with self.assertRaises(c.SyncError):
            t.record(j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY")

    def test_discovery_rejection_never_routes(self):
        self.assertEqual(t.plan(self.j, self.discovery(primary="rejected"), "fallback")["action"], "BLOCKED")

    def test_stale_discovery_and_missing_channel(self):
        old = self.discovery()
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY")
        with self.assertRaises(c.SyncError):
            t.plan(j, old, "fallback")
        d = self.discovery()
        del d["results"]["fallback"]
        with self.assertRaises(c.SyncError):
            t.plan(self.j, d, "primary")

    def test_operation_and_history_tampering(self):
        j = copy.deepcopy(self.j)
        j["operation"]["destination_thread"] = "other"
        with self.assertRaises(c.SyncError):
            t.validate(j)
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY")
        j["events"][0]["previous_sha256"] = "0" * 64
        with self.assertRaises(c.SyncError):
            t.validate(j)

    def test_modified_package_and_wrong_destination(self):
        import zipfile
        with zipfile.ZipFile(self.package) as z:
            entries = {name: z.read(name) for name in z.namelist()}
        entries["sources/docs.txt"] = b"ALTERED"
        with self.assertRaises(c.SyncError):
            c.verify_zip(c.archive_bytes(entries), c.load(self.req))
        req = c.load(self.req)
        req["destination"] = "test:wrong"
        with self.assertRaises(c.SyncError):
            c.verify_zip(self.package.read_bytes(), req)

    def test_migration_preserves_configuration(self):
        v1 = copy.deepcopy(self.contract)
        v1["schema_version"] = 1
        v1["transport"] = self.primary
        path = self.root / "old.json"
        path.write_bytes(c.encode(v1))
        migrated = t.migrate(path, self.primary, self.fallback)
        self.assertEqual(migrated["transport"]["primary"], v1["transport"])
        for key in v1:
            if key not in ("schema_version", "transport"):
                self.assertEqual(migrated[key], v1[key])
        wrong = dict(self.primary, account="other")
        with self.assertRaises(c.SyncError):
            t.migrate(path, wrong, self.fallback)

    def test_unsafe_policy_rejected(self):
        bad = copy.deepcopy(self.contract)
        bad["transport"]["policy"]["fallback_on"] = ["validation-rejected"]
        with self.assertRaises(c.SyncError):
            c.validate_contract(bad)

    def test_fallback_event_requires_dc_unavailability(self):
        with self.assertRaises(c.SyncError):
            t.record(self.j, "DEPOSITED", "fallback", "present", "TEST ONLY bypass")
        receipt, observed, proof, evidence = self.receipt_fixture("fallback")
        with self.assertRaises(c.SyncError):
            t.confirm(self.j, receipt, observed, self.carrier, self.req, proof, evidence)

    def test_migration_refuses_loss_of_manual_or_source_settings(self):
        v1 = copy.deepcopy(self.contract)
        v1["schema_version"] = 1
        path = self.root / "old.json"
        for endpoint in ({"channel": "manual", "locator": "handoff:keep", "account": "keep"}, {"channel": "project-sources", "locator": "source:keep", "account": "keep"}):
            v1["transport"] = endpoint
            path.write_bytes(c.encode(v1))
            with self.assertRaises(c.SyncError):
                t.migrate(path, self.primary, self.fallback)

    def test_migration_preserves_old_drive(self):
        v1 = copy.deepcopy(self.contract)
        v1["schema_version"] = 1
        v1["transport"] = self.fallback
        path = self.root / "old.json"
        path.write_bytes(c.encode(v1))
        self.assertEqual(t.migrate(path, self.primary, self.fallback)["transport"]["fallback"], self.fallback)
        with self.assertRaises(c.SyncError):
            t.migrate(path, self.primary, dict(self.fallback, account="other"))

    def receipt_fixture(self, channel="primary"):
        op = self.j["operation"]
        p = t.plan(self.j, self.discovery(), "primary")
        artifact = p["targets"]["carrier.json"] if channel == "primary" else "gdrive:file:TEST_CARRIER"
        proof_locator = p["receipt_target"].replace("receipt.json", "proof.json") if channel == "primary" else "gdrive:file:TEST_PROOF"
        receipt_locator = p["receipt_target"] if channel == "primary" else "gdrive:file:TEST_RECEIPT"
        observation_path = self.root / "receive.json"
        observation_path.write_bytes(c.encode({"destination": "test:work", "artifact_locator": artifact, "retrieved_sha256": c.digest(self.carrier.read_bytes())}))
        proof = self.root / "proof.json"
        c.receive(argparse.Namespace(input=self.carrier, requirement=self.req, observation=observation_path, store=self.root / "store", output=proof))
        c.check_store(self.root / "store", c.load(self.req))
        receipt = self.root / "receipt.json"
        data = {"format": "SYNCPILOT-RECEIPT", "schema_version": 1, "operation_id": op["operation_id"], "nonce": op["nonce"], "identity": op["identity"], "destination_thread": op["destination_thread"], "channel": channel, "status": "RECEIVED_VERIFIED", "files": op["files"], "proof_sha256": c.digest(proof.read_bytes())}
        receipt.write_bytes(c.encode(data))
        profile = op["profiles"][channel]
        observed = {"destination": "test:work", "destination_thread": "test:thread", "channel": channel, "account": profile["account"], "storage_root": profile["locator"], "artifact_locator": artifact, "proof_locator": proof_locator, "receipt_locator": receipt_locator, "receipt_sha256": c.digest(receipt.read_bytes()), "authenticated_channel": profile["channel"], "authority": "TEST ONLY SIMULATION", "work_finished": True}
        evidence = self.root / "evidence.json"
        evidence.write_bytes(c.encode({"destination": "test:work", "destination_thread": "test:thread", "artifact_locator": artifact, "proof_locator": proof_locator, "proof_sha256": c.digest(proof.read_bytes()), "authenticated_channel": "TEST ONLY SIMULATION", "authority": "TEST ONLY SIMULATION"}))
        return receipt, observed, proof, evidence

    def test_independent_gate_simulation_dc(self):
        receipt, observed, proof, evidence = self.receipt_fixture()
        j, accepted = t.confirm(self.j, receipt, observed, self.carrier, self.req, proof, evidence)
        self.assertEqual(t.state(j), "VERIFIED")
        self.assertEqual(accepted["mirror_status"], "CURRENT")

    def test_v4_transport_verified_is_not_durable_completion(self):
        import test_decisions
        f = test_decisions.DecisionTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.contract['schema_version'] = 4
        ds = copy.deepcopy(f.config['decision_sync'])
        ds['participants']['work'] = {'project_id':'test:work','thread_id':'test:thread'}
        ds['sources']['work'] = ['chat:test:thread']
        self.contract['decision_sync'] = ds
        self.contract['work_persistence'] = {'target':{'kind':'page-files','project_id':'test:work','container_id':'qualified-page'},'registry':'page:qualified-page#registry','policy':{'required':True,'write':'reuse-before-create','unknown_commit':'inspect-before-retry','revalidation':'fresh-read-at-mission-start','transport':'separate-from-publication'}}
        (self.repo/c.CONTRACT).write_bytes(c.encode(self.contract))
        self.git('add',c.CONTRACT);self.git('-c','commit.gpgsign=false','commit','-m','TEST v4')
        self.req=self.root/'v4-requirement.json';self.package=self.root/'v4-package.zip';self.carrier=self.root/'v4-carrier.json'
        c.prepare_requirement(argparse.Namespace(repository=self.repo,commit=self.git('rev-parse','HEAD'),domain=['docs'],authority='TEST ONLY',output=self.req))
        c.build(argparse.Namespace(repository=self.repo,requirement=self.req,output=self.package,carrier=self.carrier,attestation=None))
        self.j=t.prepare(self.carrier,self.req,'test:thread','TEST ONLY')
        receipt,observed,proof,evidence=self.receipt_fixture()
        j,accepted=t.confirm(self.j,receipt,observed,self.carrier,self.req,proof,evidence)
        self.assertEqual(t.state(j),'VERIFIED')
        self.assertEqual(accepted['completion_status'],'RECEIVED_VERIFIED_PERSISTENCE_PENDING')
        self.assertEqual(accepted['work_availability'],'NOT_VERIFIED')

    def test_independent_gate_simulation_drive(self):
        receipt, observed, proof, evidence = self.receipt_fixture("fallback")
        j = t.record(self.j, "DC_UNAVAILABLE", "primary", "not-delivered", "TEST ONLY")
        j, _ = t.confirm(j, receipt, observed, self.carrier, self.req, proof, evidence)
        self.assertEqual(t.state(j), "VERIFIED")

    def test_wrong_receipt_identity_and_unfinished_work(self):
        receipt, observed, proof, evidence = self.receipt_fixture()
        observed["work_finished"] = False
        with self.assertRaises(c.SyncError):
            t.confirm(self.j, receipt, observed, self.carrier, self.req, proof, evidence)
        observed["work_finished"] = True
        data = c.load(receipt)
        data["nonce"] = str(__import__('uuid').uuid4())
        receipt.write_bytes(c.encode(data))
        observed["receipt_sha256"] = c.digest(receipt.read_bytes())
        with self.assertRaises(c.SyncError):
            t.confirm(self.j, receipt, observed, self.carrier, self.req, proof, evidence)

    def test_record_cannot_mark_verified(self):
        with self.assertRaises(c.SyncError):
            t.record(self.j, "VERIFIED", "primary", "present", "no proof")

    def test_output_never_overwritten(self):
        path = self.root / "journal.json"
        c.write_new(path, c.encode(self.j))
        with self.assertRaises(FileExistsError):
            c.write_new(path, b"changed")
        self.assertEqual(c.load(path), self.j)


if __name__ == "__main__":
    unittest.main()
