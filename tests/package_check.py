"""Portable offline package checks. Does not install, send or publish."""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "syncpilot"


def check():
    generic = json.loads((PLUGIN / "plugin.json").read_bytes())
    codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_bytes())
    assert generic["name"] == codex["name"] == "syncpilot"
    assert generic["version"] == codex["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", generic["version"])
    assert generic["extensions"]["com.openai"]["interface"] == codex["interface"]
    assert json.loads((PLUGIN / ".app.json").read_bytes()) == {"apps": {}}
    assert (PLUGIN / "skills/syncpilot-codex/scripts/project_sync.py").read_bytes() == (
        PLUGIN / "skills/syncpilot-work/scripts/project_sync.py").read_bytes()
    files = []
    for path in sorted(PLUGIN.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        assert not path.is_symlink()
        data = path.read_bytes()
        value = data.decode("utf-8")
        if path.name == "SKILL.md":
            lines = value.splitlines()
            assert lines[0] == "---" and lines[1].startswith("name: ")
            assert lines[2].startswith("description: ") and lines[3] == "---"
            assert lines[1].removeprefix("name: ") == path.parent.name
        if path.suffix == ".json":
            json.loads(value)
        if path.suffix == ".py":
            ast.parse(value, filename=str(path))
        files.append({"path": path.relative_to(PLUGIN).as_posix(),
                      "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    assert len(list((PLUGIN / "skills").glob("*/SKILL.md"))) == 6
    return {"version": generic["version"], "file_count": len(files), "files": files}


if __name__ == "__main__":
    result = check()
    print(json.dumps({"version": result["version"], "package_files": result["file_count"],
                      "engine_copies_identical": True, "provider_bindings": 0}))
