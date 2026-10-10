"""Fail closed on recognizable research fixtures before an owner-triggered upload."""

from pathlib import Path
import re
import sys


def validate(folder):
    folder = folder.resolve()
    if not folder.is_dir():
        raise ValueError("Photo folder does not exist")
    entries = [folder, *folder.rglob("*")]
    for path in entries:
        text = str(path).lower()
        if path.is_symlink():
            raise ValueError("Photo folder must not contain symlinks")
        if any(
            word in text for word in ("lfw", "labeled_faces", "labelled_faces", "fixture", "e2e-", "round2-")
        ):
            raise ValueError("Research fixture folder refused")
        if re.fullmatch(r"[A-Z][A-Za-z]+(?:_[A-Z][A-Za-z]+)+_\d{4}\.(jpg|png|jpeg)", path.name):
            raise ValueError("LFW-style filename refused")
    people = folder / "people" if (folder / "people").is_dir() else folder
    candidates = [p for p in people.iterdir() if (p / "reference").is_dir()]
    if not candidates or not all((p / "originals").is_dir() and (p / "wild").is_dir() for p in candidates):
        raise ValueError("Expected <person>/reference, originals and wild photo folders")


if __name__ == "__main__":
    try:
        validate(Path(sys.argv[1]))
    except (ValueError, IndexError) as error:
        raise SystemExit(str(error))
