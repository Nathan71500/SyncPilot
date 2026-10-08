"""Isolated Git simulations: performance changes must preserve exact bytes."""
import argparse
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "syncpilot/skills/syncpilot-codex/scripts/project_sync.py"
spec = importlib.util.spec_from_file_location("performance_core", SCRIPT)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class BatchSnapshotsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.run_git("init", "-b", "main")
        self.run_git("config", "user.name", "Batch fixture")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.run_git("config", "core.autocrlf", "false")
        self.contract = {"schema_version": 1, "project_id": "batch-fixture",
                         "repository": "https://example.invalid/batch-fixture",
                         "reference_branch": "main", "destination": "test:work",
                         "authority": "TEST ONLY", "shared_sources": [],
                         "domains": {"docs": ["docs/été space.txt", "empty.txt", "binary.txt"]},
                         "transport": {"channel": "manual", "locator": "", "account": ""}}
        self.run_git("remote", "add", "origin", self.contract["repository"])
        self.entries = {c.CONTRACT: c.encode(self.contract),
                        "docs/été space.txt": "Été 🧭\r\nTEST ONLY\n".encode("utf-8"),
                        "empty.txt": b"", "binary.txt": b"TEST ONLY\n\x00end"}
        for name, raw in self.entries.items():
            file = self.repo / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        self.run_git("add", ".")
        self.head = self.commit("batch fixture")

    def run_git(self, *args, input_data=None):
        return subprocess.run(["git", "-C", str(self.repo), *args], input=input_data,
                              capture_output=True, check=True).stdout.decode().strip()

    def commit(self, message):
        self.run_git("-c", "commit.gpgsign=false", "commit", "-m", message)
        return self.run_git("rev-parse", "HEAD")

    def test_batch_and_serial_are_identical_for_exact_binary_and_utf8(self):
        paths = list(self.entries)
        expected = {path: c.snapshot(self.repo, self.head, path) for path in paths}
        with patch.object(c, "git", wraps=c.git) as calls:
            actual = c.snapshots(self.repo, self.head, paths)
        self.assertEqual(actual, expected)
        self.assertEqual(actual, self.entries)
        self.assertEqual(calls.call_count, 3)

    def test_literal_wildcards_tabs_and_dash_paths_from_git_tree(self):
        # Git trees can contain POSIX names that Windows cannot materialize.
        paths = ["tab\tname.txt", "literal*.txt", "-option.txt"]
        raw = b"TEST ONLY literal paths\n"
        blob = self.run_git("hash-object", "-w", "--stdin", input_data=raw)
        records = b"".join(("100644 blob " + blob + "\t" + path).encode("utf-8") + b"\0" for path in sorted(paths))
        tree = self.run_git("mktree", "-z", input_data=records)
        head = self.run_git("-c", "commit.gpgsign=false", "commit-tree", tree, "-m", "TEST ONLY POSIX names")
        self.assertEqual(c.snapshots(self.repo, head, paths), dict.fromkeys(paths, raw))

    def test_missing_directory_and_unsafe_paths_refused(self):
        for paths in (["missing.txt"], ["docs"], ["../outside.txt"], ["empty.txt", "empty.txt"]):
            with self.subTest(paths=paths), self.assertRaises(c.SyncError):
                c.snapshots(self.repo, self.head, paths)

    def test_symlink_refused_before_blob_read(self):
        blob = self.run_git("hash-object", "-w", "--stdin", input_data=b"empty.txt")
        self.run_git("update-index", "--add", "--cacheinfo", "120000", blob, "link.txt")
        head = self.commit("TEST ONLY symlink index")
        with patch.object(c, "git", wraps=c.git) as calls, self.assertRaises(c.SyncError):
            c.snapshots(self.repo, head, ["link.txt"])
        self.assertFalse(any(call.args[1] == "cat-file" for call in calls.call_args_list))

    def test_size_and_total_limits_precede_blob_read(self):
        for key, limit in (("MAX_FILE", 1), ("MAX_TOTAL", 1)):
            with self.subTest(key=key), patch.object(c, key, limit), \
                    patch.object(c, "git", wraps=c.git) as calls, self.assertRaises(c.SyncError):
                c.snapshots(self.repo, self.head, ["docs/été space.txt"])
            self.assertFalse(any("--batch" in call.args for call in calls.call_args_list))

    def test_duplicate_blob_contents_read_once_and_total_counts_each_path(self):
        (self.repo / "same.txt").write_bytes(self.entries["docs/été space.txt"])
        self.run_git("add", "same.txt")
        head = self.commit("TEST ONLY duplicate blob")
        paths = ["docs/été space.txt", "same.txt"]
        with patch.object(c, "git", wraps=c.git) as calls:
            actual = c.snapshots(self.repo, head, paths)
        self.assertEqual(actual[paths[0]], actual[paths[1]])
        batch_request = next(call.kwargs["input_data"] for call in calls.call_args_list if "--batch" in call.args)
        self.assertEqual(len(batch_request.splitlines()), 1)
        with patch.object(c, "MAX_TOTAL", len(actual[paths[0]]) + 1), self.assertRaises(c.SyncError):
            c.snapshots(self.repo, head, paths)

    def test_blob_corruption_truncation_and_unexpected_bytes_refused(self):
        original_git = c.git
        for mutate in (lambda raw: raw.replace(b"TEST ONLY", b"BEST ONLY"),
                       lambda raw: raw[:-2], lambda raw: raw + b"extra"):
            def fake_git(repo, *args, input_data=None):
                raw = original_git(repo, *args, input_data=input_data)
                return mutate(raw) if "--batch" in args else raw
            with self.subTest(mutate=mutate), patch.object(c, "git", side_effect=fake_git), self.assertRaises(c.SyncError):
                c.snapshots(self.repo, self.head, ["docs/été space.txt"])

    def test_windows_command_budget_uses_multiple_bounded_batches(self):
        paths = ["docs/" + ("x" * 160) + str(i) + ".txt" for i in range(150)]
        blob = self.run_git("hash-object", "-w", "--stdin", input_data=b"TEST ONLY\n")
        index = "".join("100644 " + blob + "\t" + path + "\n" for path in paths).encode("utf-8")
        self.run_git("update-index", "--index-info", input_data=index)
        head = self.commit("TEST ONLY command budget")
        with patch.object(c, "git", wraps=c.git) as calls:
            actual = c.snapshots(self.repo, head, paths)
        tree_calls = [call for call in calls.call_args_list if call.args[1] == "ls-tree"]
        self.assertGreater(len(tree_calls), 1)
        for call in tree_calls:
            command = subprocess.list2cmdline(["git", "-C", str(self.repo), *call.args[1:]])
            self.assertLess(len(command.encode("utf-16-le")) // 2, 32767)
        self.assertEqual(actual, dict.fromkeys(paths, b"TEST ONLY\n"))

    def test_same_commit_is_reread_and_new_head_is_not_silently_accepted(self):
        paths = ["docs/été space.txt"]
        self.assertEqual(c.snapshots(self.repo, self.head, paths)[paths[0]], self.entries[paths[0]])
        (self.repo / paths[0]).write_bytes(b"TEST ONLY next version\n")
        with self.assertRaises(c.SyncError):
            c.source_check(self.repo, self.head, self.contract)
        self.run_git("add", ".")
        new_head = self.commit("TEST ONLY changed canon")
        self.assertEqual(c.snapshots(self.repo, new_head, paths)[paths[0]], b"TEST ONLY next version\n")
        with self.assertRaises(c.SyncError):
            c.source_check(self.repo, self.head, self.contract)


if __name__ == "__main__":
    unittest.main(verbosity=2)
