"""Photo-folder seeder. Ground truth is an output, never input to the backend."""

import argparse
import hashlib
import html
from io import BytesIO
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

SITES = ("pixboard", "friendlink", "localnews", "shadygallery", "host", "search", "editorial")
SITE_PORTS = {site: index for index, site in enumerate(SITES)}
SITE_PORTS["editorial"] = 8


def encoded(image, quality=91):
    stream = BytesIO()
    image.convert("RGB").save(stream, "JPEG", quality=quality)
    return stream.getvalue()


def transforms(payload):
    with Image.open(BytesIO(payload)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    width, height = image.size
    border = Image.new("RGB", (width + 90, height + 110), "white")
    border.paste(image, (45, 65))
    ImageDraw.Draw(border).text((12, 12), "Shared photograph", fill="black")
    caption = image.copy()
    draw = ImageDraw.Draw(caption)
    draw.rectangle((0, height * 0.8, width, height), fill="white")
    draw.text((8, int(height * 0.83)), "A photo shared online", fill="black")
    return {
        "exact": payload,
        "resize": encoded(image.resize((max(1, width // 2), max(1, height // 2)))),
        "recompress": encoded(image, 12),
        "crop": encoded(
            image.crop((int(width * 0.13), int(height * 0.12), int(width * 0.89), int(height * 0.91)))
        ),
        "mirror": encoded(ImageOps.mirror(image)),
        "border": encoded(border),
        "caption_overlay": encoded(caption),
    }


def photos(directory):
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    )


class Seeder:
    def __init__(self, output, base_port):
        if output.exists() and any(output.iterdir()):
            raise ValueError("Seed output must be empty; choose a fresh directory")
        self.output = output
        self.base_port = base_port
        self.manifest = []
        self.links = {site: [] for site in SITES}
        for site in SITES:
            for folder in ("media", "post", "private", "feed"):
                (output / site / folder).mkdir(parents=True, exist_ok=True)
            (output / site / "robots.txt").write_text(
                "User-agent: *\nDisallow: /private/\nDisallow: /admin\n"
            )
        (output / "friendlink/profile.js").write_text(
            "const p=document.getElementById('profile');"
            "fetch(p.dataset.feed).then(r=>r.json()).then(d=>{p.innerHTML=d.html});"
        )

    def add(self, site, payload, person, transform, same_photo, accessible=True, authorized=False):
        number = len(self.manifest) + 1
        slug = f"{number:04d}"
        base = f"http://127.0.0.1:{self.base_port + SITE_PORTS[site]}"
        prefix = "post" if accessible else "private"
        page_path = f"/{prefix}/{slug}.html"
        image_path = f"/media/{slug}.jpg" if accessible else f"/private/{slug}.jpg"
        root = self.output / site
        (root / image_path.lstrip("/")).write_bytes(payload)
        safe_name = html.escape(person or "Community contributor")
        image = f'<img src="{image_path}" alt="Shared photograph">'
        if site == "pixboard":
            if number % 3 == 0:
                image = f'<picture><source srcset="{image_path} 1x"><img alt="Community upload"></picture>'
            body = f"<ol><li><figure>{image}<figcaption>Posted by {safe_name}</figcaption></figure></li></ol>"
        elif site == "friendlink":
            display_name = safe_name if authorized else "Morgan Example"
            feed = f"/feed/{slug}.json"
            (root / feed.lstrip("/")).write_text(
                json.dumps({"html": f"<section><h2>{display_name}</h2>{image}</section>"})
            )
            body = (
                f'<aside>Connections</aside><main id="profile" data-feed="{feed}">Loading profile...</main>'
                '<script src="/profile.js"></script>'
            )
        elif site == "localnews":
            body = (
                "<article><h1>Community event</h1><p>Editorial reporting. "
                f"Licensed photograph credited to {safe_name}.</p>{image}</article>"
            )
        else:
            body = f"<table><tr><th>SHADY GALLERY</th></tr><tr><td>Upload archive</td><td>{image}</td></tr></table>"
        document = (
            f"<!doctype html><html><head><title>{site}</title></head><body>{body}"
            '<footer><a href="/policy">Content policy and reports</a></footer></body></html>'
        )
        (root / page_path.lstrip("/")).write_text(document)
        self.links[site].append(page_path)
        self.manifest.append(
            {
                "site": site,
                "page_url": base + page_path,
                "image_url": base + image_path,
                "identity": person,
                "transform": transform,
                "same_photo": same_photo,
                "accessible": accessible,
                "authorized": authorized,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    def finish(self):
        for site in SITES:
            links = "".join(
                f'<li><a href="{url}">Entry {index + 1}</a></li>'
                for index, url in enumerate(self.links[site])
            )
            (self.output / site / "index.html").write_text(
                f'<!doctype html><title>{site}</title><h1>{site}</h1><ul>{links}</ul><a href="/policy">Policy</a>'
            )
        path = self.output / "ground_truth.json"
        path.write_text(json.dumps(self.manifest, indent=2))
        return {"appearances": len(self.manifest), "ground_truth": str(path)}


def seed(folder, output, base_port=8811, max_people=None, max_originals=None, max_distractors=None):
    people_root = folder / "people" if (folder / "people").is_dir() else folder
    people = sorted(path for path in people_root.iterdir() if (path / "reference").is_dir())
    if max_people:
        people = people[:max_people]
    if not people:
        raise ValueError("No <person>/reference directories found")
    seeder = Seeder(output, base_port)
    for person in people:
        originals = photos(person / "originals")
        wild = photos(person / "wild")
        if max_originals:
            originals = originals[:max_originals]
        if not originals or len(wild) < 3:
            raise ValueError(f"{person.name}: need at least one original and three wild photos")
        for original in originals:
            for transform, payload in transforms(original.read_bytes()).items():
                seeder.add("pixboard", payload, person.name, transform, True)
        seeder.add("friendlink", originals[0].read_bytes(), person.name, "js_copy", True)
        seeder.add("friendlink", wild[1].read_bytes(), person.name, "js_wild", False)
        seeder.add(
            "friendlink", wild[2].read_bytes(), person.name, "authorized_profile", False, authorized=True
        )
        seeder.add("localnews", wild[0].read_bytes(), person.name, "news_wild", False, authorized=True)
        seeder.add("shadygallery", originals[0].read_bytes(), person.name, "gallery_copy", True)
        seeder.add(
            "shadygallery", originals[0].read_bytes(), person.name, "robots_blocked", True, accessible=False
        )
    distractors = photos(folder / "distractors") if (folder / "distractors").is_dir() else []
    if max_distractors:
        distractors = distractors[:max_distractors]
    for index, path in enumerate(distractors):
        seeder.add(SITES[index % 4], path.read_bytes(), None, "distractor", False)
    return seeder.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-port", type=int, default=8811)
    args = parser.parse_args()
    print(json.dumps(seed(args.photos, args.output, args.base_port)))
