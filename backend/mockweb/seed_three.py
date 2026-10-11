"""Staged public pages for a local, explicitly fictional removal demonstration."""

from html import escape
import hashlib

from PIL import Image, ImageOps

from mockweb.seed import Seeder, photos


PAGES = (
    ("Portrait print shop", "Unauthorized resale",
     "This full-resolution portrait was copied from the photographer's portfolio. "
     "The photographer owns the copyright and has not licensed this shop to reproduce "
     "or sell it. The uploader acknowledges having no permission. "
     "Unaltered portrait prints are offered for sale for $49; this is not commentary or reporting."),
    ("Community portrait exhibition", "Published with permission",
     "The photographer has granted this exhibition a current written license to display "
     "the portrait. The depicted person has also approved this use. "
     "Credit and permission are recorded with the exhibition organizer."),
)

STYLE = """
*{box-sizing:border-box}body{margin:0;background:#f6f3ed;color:#222;font:17px/1.6 system-ui,sans-serif}
nav,main,footer{max-width:1080px;margin:auto;padding:24px}nav{display:flex;justify-content:space-between;
gap:24px;border-bottom:1px solid #ccc}a{color:inherit;text-underline-offset:4px}h1{font-size:clamp(32px,5vw,56px);
line-height:1.12;letter-spacing:-.04em;margin:24px 0}p{max-width:720px}figure{margin:32px 0;
background:#e6e1d8;border-radius:16px;padding:24px}img{display:block;max-width:100%;height:400px;
object-fit:contain;margin:auto}figcaption{margin-top:16px;text-align:center}.banner{background:#e6ddf8;
padding:12px 24px;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(280px,100%),1fr));
gap:24px}.card{background:white;border:1px solid #ddd;border-radius:16px;padding:24px}.card h2{line-height:1.25}
.card a{display:inline-block;padding:12px 0}footer{border-top:1px solid #ccc;font-size:14px}
:focus-visible{outline:3px solid #643bb0;outline-offset:4px}.removed{padding:48px 24px;background:#e0ebde}
.article-page{font:16px/1.5 Georgia,serif;background:#f7f4ed;color:#282720}
.article-page .banner{background:#efe1c6;text-align:center;font-size:13px;padding:9px 20px}
.article-page nav{padding:14px 24px;font-size:15px;border-bottom:2px solid #282720}
.article-page nav a:first-child{font-size:22px;font-weight:bold;text-decoration:none}
.article-page main{padding:22px 24px 16px}
.article-page h1{font-size:clamp(30px,3.5vw,44px);letter-spacing:-.035em;margin:0 0 8px;line-height:1.12}
.article-page .deck{font-size:18px;color:#625d53;max-width:none;margin:0 0 12px}
.article-page .byline{font-size:13px;border-top:1px solid #cec7ba;padding-top:10px;margin:0 0 18px}
.article-layout{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:32px;align-items:start}
.article-copy p{margin:0 0 12px}.article-page figure{margin:0;padding:0;background:transparent;border-radius:0}
.article-page img{width:100%;height:288px;object-fit:contain;background:#e8e3d9}
.article-page figcaption{margin:8px 0 0;text-align:left;font-size:12px;color:#625d53}
.exposed-details{border:1px solid #c9b7a0;border-left:3px solid #a04b35;background:#efe8dc;padding:12px 16px;margin:16px 0}
.exposed-details h2{font:700 18px/1.3 Georgia,serif;margin:0 0 8px}
.exposed-details dl{margin:0;font-size:14px;display:grid;grid-template-columns:70px 1fr;gap:6px 12px}
.exposed-details dt{color:#625d53}.exposed-details dd{margin:0;overflow-wrap:anywhere}
.article-copy .disclosure{font-size:13px;color:#625d53;margin:0}
.article-page #removal-status{font-size:12px;color:#625d53;margin:10px 0 0}
.article-page footer{padding:12px 24px;font-size:12px}
@media(max-width:650px){.article-layout{grid-template-columns:1fr;gap:20px}.article-page nav{gap:12px;align-items:center}
.article-page nav a:first-child{font-size:18px}.article-page nav a:last-child{font-size:12px}.article-page main{padding-top:18px}}
@media print{.article-page{font-size:12px}.article-page main{padding-top:12px}.article-page h1{font-size:30px}
.article-page .article-layout{grid-template-columns:1.2fr 1fr}.article-page img{height:240px}.article-page article{break-inside:avoid}}
"""


def document(title, body, article=False):
    body_class = ' class="article-page"' if article else ""
    banner = (
        "Fictional doxxing demo · staged portrait · all names and contact details are placeholders."
        if article else
        "Local demo · dataset photos · fictional rights and permissions. No actual copyright claim is being made."
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(title)} · Portrait Exchange</title><style>{STYLE}</style></head><body{body_class}>'
        f'<div class="banner">{banner}</div>'
        '<nav><a href="/">Portrait Exchange</a><a href="/policy">Copyright &amp; contact</a></nav>'
        f'<main>{body}</main><footer>Independent demo website · '
        '<a href="/receipts">View received requests</a></footer></body></html>'
    )


def photo_page(index):
    title, caption, description = PAGES[index - 1]
    image = f"/media/{index:04d}.jpg"
    photograph = (
        f'<figure id="photograph"><img src="{image}" alt="Local fixture portrait">'
        f'<figcaption>{escape(caption)}</figcaption></figure>'
    )
    body = f'<h1>{escape(title)}</h1><p>{escape(description)}</p>{photograph}'
    body += (
        '<p id="removal-status" role="status">Photo is currently published.</p>'
        '<script>async function check(){try{const r=await fetch('
        f'"/image-status?path={image}",{{cache:"no-store"}});'
        'if(!r.ok)return;const s=await r.json();if(s.removed){'
        'document.getElementById("photograph").innerHTML="<h2>Photo removed</h2>";'
        'document.getElementById("photograph").classList.add("removed");'
        'document.getElementById("removal-status").textContent='
        '"The site received a removal request and disabled access to this photo.";'
        'clearInterval(timer)}}catch{}}const timer=setInterval(check,2000);check();</script>'
    )
    return document(title, body)


def distinct_photos(person, categories=("originals", "wild", "reference")):
    """Choose one different local photo per page, ignoring duplicate encodings."""
    selected = []
    seen = set()
    for category in categories:
        folder = person / category
        if not folder.is_dir():
            continue
        for path in photos(folder):
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                signature = (image.size, hashlib.sha256(image.tobytes()).hexdigest())
            if signature in seen:
                continue
            seen.add(signature)
            selected.append(path)
            if len(selected) == len(PAGES):
                return selected
    raise ValueError("Each staged page needs a different photo of the same fixture person")


def seed_three(person, output, base_port):
    originals = distinct_photos(person, categories=("originals",))
    seeder = Seeder(output, base_port)
    cards = []
    for index, (title, caption, description) in enumerate(PAGES, 1):
        payload = originals[index - 1].read_bytes()
        seeder.add("pixboard", payload, "Demo photographer", "exact", True,
                   authorized=index == 2)
        slug = f"{index:04d}"
        page = f"/post/{slug}.html"
        (output / "pixboard" / page.lstrip("/")).write_text(photo_page(index))
        cards.append(f'<article class="card"><h2>{escape(title)}</h2><p>{escape(caption)}</p>'
                     f'<a href="{page}">Open photo page →</a></article>')
    seeder.finish()
    site = output / "pixboard"
    (site / "index.html").write_text(document(
        "Portraits", '<h1>Portraits, in circulation.</h1>'
        '<p>Two publications. Two different rights situations.</p>'
        '<div class="grid">' + "".join(cards) + '</div>',
    ))
    (site / "policy.html").write_text(document(
        "Copyright and contact", '<h1>Copyright and removal requests</h1>'
        '<p>For copyright reports, contact our designated demo administrator: '
        '<a href="mailto:agent@pixboard.test">Copyright administrator: agent@pixboard.test</a>.</p>'
        '<p>Identify the original work, the page and image URLs, your contact information '
        'and the required good-faith and authority statements. Valid demo requests are '
        'processed by this website independently of CenSearch.</p>'
        '<p>This mailbox uses the local SMTP receiver.</p>',
    ))
    return [f"http://127.0.0.1:{base_port}/post/{index:04d}.html" for index in range(1, len(PAGES) + 1)]


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, required=True, help="one fixture person's folder")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-port", type=int, default=8811)
    args = parser.parse_args()
    for url in seed_three(args.photos, args.output, args.base_port):
        print(url)
