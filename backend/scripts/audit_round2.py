"""Offline handoff, boundary, formatting and cleanup-artifact checks."""

import ast
import json
from pathlib import Path
import re
from censearch.config import ROOT


def main():
    runs = [Path((ROOT / "data" / name).read_text()) for name in ("latest-e2e.txt", "latest-round2.txt")]
    examples = [item for run in runs for item in json.loads((run / "api-examples.json").read_text())]
    schema = json.loads((ROOT / "handoff/openapi.json").read_text())
    missing = []
    for path, methods in schema["paths"].items():
        for method in methods:
            pattern = re.sub(r"\{[^}]+\}", "[^/]+", path)
            if not any(
                item["method"].lower() == method and re.fullmatch(pattern, item["path"].split("?")[0])
                for item in examples
            ):
                missing.append([method, path])
    assert not missing, missing
    files = []
    for item in examples:
        files.extend(row["filename"] for row in item["request"].get("files", []))
    assert all(not re.search(r"[A-Z][a-z]+_[A-Z][a-z]+_\d{4}", name) for name in files), files
    for run in runs:
        assert json.loads((run / "cleanup.json").read_text())["stdout"] == ""
    long_lines = []
    syntax_files = []
    for folder in ("censearch", "mockweb", "scripts", "tests", "deploy"):
        for path in (ROOT / folder).rglob("*.py"):
            ast.parse(path.read_text())
            syntax_files.append(str(path.relative_to(ROOT)))
            for index, line in enumerate(path.read_text().splitlines(), 1):
                if len(line) > 120:
                    long_lines.append(f"{path.relative_to(ROOT)}:{index} ({len(line)})")
    assert not long_lines, long_lines
    assert len((ROOT / "handoff/NOTE_FOR_PARTNER.md").read_text().split()) < 300
    print(
        json.dumps(
            {
                "api_paths_with_actual_examples": len(schema["paths"]),
                "missing": missing,
                "syntax_files": len(syntax_files),
                "long_python_lines": long_lines,
                "fixture_filenames_neutral": True,
                "recorded_acceptance_cleanup": "no listeners",
            }
        )
    )


if __name__ == "__main__":
    main()
