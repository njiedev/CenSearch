"""Validate local fixture folders without exposing their image contents."""

from pathlib import Path

from mockweb.seed import photos

PHOTO_ERROR = "Pass PHOTOS=/path/to/fixtures containing reference, originals and wild photo folders."


def select_person(root: Path, name: str | None = None) -> Path:
    try:
        if not str(root) or not root.is_dir():
            raise ValueError
        people = root / "people" if (root / "people").is_dir() else root
        candidates = sorted(path for path in people.iterdir() if (path / "reference").is_dir())
        person = people / name if name else next(iter(candidates), None)
        if person is None or not all(
            (person / category).is_dir() and photos(person / category)
            for category in ("reference", "originals", "wild")
        ):
            raise ValueError
        return person
    except (OSError, ValueError):
        raise SystemExit(PHOTO_ERROR) from None
