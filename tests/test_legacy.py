"""Isolated fixtures only; no Work or real repository proof is produced."""
import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "syncpilot/skills/syncpilot-codex/scripts/project_sync.py"
spec = importlib.util.spec_from_file_location("project_sync", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class ProjectSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo, self.req = self.project("alpha")
        self.package = self.root / "package.zip"
        self.carrier = self.root / "carrier.json"
        self.build()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
        return result.stdout.decode().strip()

    def project(self, name):
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "-b", "main")
        self.git(repo, "config", "user.name", "Project Sync Fixture")
        self.git(repo, "config", "user.email", "fixture@example.invalid")
        self.git(repo, "config", "core.autocrlf", "false")
        self.git(repo, "remote", "add", "origin", "https://example.invalid/" + name)
        contract = {"schema_version": 1, "project_id": name, "repository": "https://example.invalid/" + name,
                    "reference_branch": "main", "destination": "work:" + name, "authority": "TEST ONLY",
                    "shared_sources": ["AGENTS.md"], "domains": {"rules": ["canon/rules.txt"], "art": ["art.txt"]},
                    "transport": {"channel": "manual", "locator": "", "account": ""}}
        (repo / "project-sync.json").write_bytes(sync.encode(contract))
        (repo / "AGENTS.md").write_text("# Test fixture\n", encoding="utf-8")
        (repo / "canon").mkdir()
        (repo / "canon/rules.txt").write_text("Règles de " + name + "\n", encoding="utf-8")
        (repo / "art.txt").write_text("art", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "Fixture")
        commit = self.git(repo, "rev-parse", "HEAD")
        output = self.root / (name + "-requirement.json")
        sync.prepare_requirement(argparse.Namespace(repository=repo, commit=commit, domain=["rules"], authority="TEST ONLY", output=output))
        return repo, output

    def build(self, **kw):
        values = dict(repository=self.repo, requirement=self.req, output=self.package, carrier=self.carrier, attestation=None)
        values.update(kw)
        return sync.build(argparse.Namespace(**values))

    def receive(self, source=None):
        source = source or self.carrier
        observation = self.root / "observation.json"
        observation.write_bytes(sync.encode({"destination": "work:alpha", "artifact_locator": "test:fixture-carrier", "retrieved_sha256": sync.digest(source.read_bytes())}))
        proof_path = self.root / "proof.json"
        store = self.root / "mirror"
        result = sync.receive(argparse.Namespace(requirement=self.req, input=source, observation=observation, store=store, output=proof_path))
        return result, store, proof_path

    def test_roundtrip_carrier_and_accept(self):
        proof, store, proof_path = self.receive()
        self.assertEqual(proof, sync.check_store(store, sync.load(self.req)))
        evidence = self.root / "evidence.json"
        evidence.write_bytes(sync.encode({"destination": "work:alpha", "destination_thread": "test:fixture-thread",
                                         "artifact_locator": "test:fixture-carrier", "proof_locator": "test:fixture-proof",
                                         "proof_sha256": sync.digest(proof_path.read_bytes()), "authenticated_channel": "TEST ONLY",
                                         "authority": "TEST ONLY; NOT A WORK PROOF"}))
        result = sync.accept(argparse.Namespace(requirement=self.req, input=self.carrier, proof=proof_path, evidence=evidence))
        self.assertEqual(result["mirror_status"], "CURRENT")
        self.assertEqual(result["source_status"], "UNKNOWN")
        with self.assertRaises(sync.SyncError):
            sync.accept(argparse.Namespace(requirement=self.req, input=self.package, proof=proof_path, evidence=evidence))

    def test_raw_zip_roundtrip(self):
        proof, _, _ = self.receive(self.package)
        self.assertEqual(proof["source_commit"], sync.load(self.req)["source_commit"])

    def test_wrong_project(self):
        _, beta = self.project("beta")
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(self.package.read_bytes(), sync.load(beta))

    def test_wrong_destination(self):
        req = sync.load(self.req)
        req["destination"] = "work:beta"
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(self.package.read_bytes(), req)

    def test_wrong_commit(self):
        req = sync.load(self.req)
        req["source_commit"] = "0" * 40
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(self.package.read_bytes(), req)

    def test_wrong_scope(self):
        req = sync.load(self.req)
        req["domains"] = ["art"]
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(self.package.read_bytes(), req)

    def modified_zip(self, transform):
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(self.package.read_bytes())) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        transform(entries)
        return sync.archive_bytes(entries)

    def test_modified_content(self):
        data = self.modified_zip(lambda e: e.update({"sources/canon/rules.txt": b"changed"}))
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(data, sync.load(self.req))

    def test_unexpected_source(self):
        data = self.modified_zip(lambda e: e.update({"sources/extra.txt": b"extra"}))
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(data, sync.load(self.req))

    def test_traversal(self):
        data = self.modified_zip(lambda e: e.update({"../escape.txt": b"escape"}))
        with self.assertRaises(sync.SyncError):
            sync.verify_zip(data, sync.load(self.req))

    def test_modified_mirror(self):
        _, store, _ = self.receive()
        (store / "sources/canon/rules.txt").write_text("changed")
        with self.assertRaises(sync.SyncError):
            sync.check_store(store, sync.load(self.req))

    def test_dirty_worktree(self):
        (self.repo / "canon/rules.txt").write_text("new changes")
        with self.assertRaises(sync.SyncError):
            self.build(output=self.root / "second.zip", carrier=None)

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):
            self.build()
        self.receive()
        with self.assertRaises(sync.SyncError):
            self.receive()

    def test_wrong_observation(self):
        o = self.root / "wrong-observation.json"
        o.write_bytes(sync.encode({"destination": "work:alpha", "artifact_locator": "test:fixture", "retrieved_sha256": "0" * 64}))
        with self.assertRaises(sync.SyncError):
            sync.receive(argparse.Namespace(requirement=self.req, input=self.carrier, observation=o, store=self.root / "failed-store", output=self.root / "bad-proof.json"))
        self.assertFalse((self.root / "failed-store").exists())

    def test_complete_requires_bound_attestation(self):
        a = self.root / "attestation.json"
        a.write_bytes(sync.encode({"requirement_sha256": sync.digest(self.req.read_bytes()), "approved_by": "TEST ONLY", "authority": "TEST ONLY", "missing_validated_items": []}))
        result = self.build(output=self.root / "complete.zip", carrier=None, attestation=a)
        self.assertEqual(result["source_status"], "COMPLETE")
        wrong = sync.load(a)
        wrong["requirement_sha256"] = "0" * 64
        a.write_bytes(sync.encode(wrong))
        with self.assertRaises(sync.SyncError):
            self.build(output=self.root / "bad-complete.zip", carrier=None, attestation=a)

    def test_secret_refused(self):
        with self.assertRaises(sync.SyncError):
            sync.documentary("docs/key.md", b"-----BEGIN PRIVATE KEY-----")

    def test_duplicate_json(self):
        with self.assertRaises(sync.SyncError):
            sync.decode(b'{"a":1,"a":2}')

    def test_cli_verify(self):
        result = subprocess.run(["python", str(SCRIPT), "verify", "--input", str(self.package), "--requirement", str(self.req)], capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["mirror_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
