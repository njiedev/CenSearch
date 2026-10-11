"""Three public pages for a local, explicitly fictional removal demonstration."""

from html import escape

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
    ("Archive submission under review", "Rights unresolved",
     "This portrait arrived with conflicting ownership claims. One contributor says they "
     "licensed it; another disputes that account. The original contract is missing and "
     "neither claim has been verified. The archive is investigating who holds the rights "
     "and whether permission covers this publication."),
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
"""


def document(title, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(title)} · Portrait Exchange</title><style>{STYLE}</style></head><body>'
        '<div class="banner">Local demo · dataset photos · fictional rights and permissions. '
        'No actual copyright claim is being made.</div>'
        '<nav><a href="/">Portrait Exchange</a><a href="/policy">Copyright &amp; contact</a></nav>'
        f'<main>{body}</main><footer>Independent demo website · '
        '<a href="/receipts">View received requests</a></footer></body></html>'
    )


def seed_three(person, output, base_port, resend_test=False):
    seeder = Seeder(output, base_port)
    payload = photos(person / "originals")[0].read_bytes()
    cards = []
    for index, (title, caption, description) in enumerate(PAGES, 1):
        seeder.add("pixboard", payload, "Demo photographer", "exact", True,
                   authorized=index == 2)
        slug = f"{index:04d}"
        image = f"/media/{slug}.jpg"
        page = f"/post/{slug}.html"
        body = (
            f'<h1>{escape(title)}</h1><p>{escape(description)}</p>'
            f'<figure id="photograph"><img src="{image}" alt="Local fixture portrait">'
            f'<figcaption>{escape(caption)}</figcaption></figure>'
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
        (output / "pixboard" / page.lstrip("/")).write_text(document(title, body))
        cards.append(f'<article class="card"><h2>{escape(title)}</h2><p>{escape(caption)}</p>'
                     f'<a href="{page}">Open photo page →</a></article>')
    seeder.finish()
    site = output / "pixboard"
    (site / "index.html").write_text(document(
        "Three portraits", '<h1>Portraits, in circulation.</h1>'
        '<p>Three publications. Three different rights situations.</p>'
        '<div class="grid">' + "".join(cards) + '</div>',
    ))
    (site / "policy.html").write_text(document(
        "Copyright and contact", '<h1>Copyright and removal requests</h1>'
        '<p>For copyright reports, contact our designated demo administrator: '
        '<a href="mailto:agent@pixboard.test">Copyright administrator: agent@pixboard.test</a>.</p>'
        '<p>Identify the original work, the page and image URLs, your contact information '
        'and the required good-faith and authority statements. Valid demo requests are '
        'processed by this website independently of CenSearch.</p>'
        + ('<p>This demo contact forwards through Resend to its test recipient '
         'delivered+censearch-demo@resend.dev. Delivery events are simulated; '
         'the website will not remove the image automatically.</p>' if resend_test else
         '<p>This mailbox uses the local SMTP receiver. It is not a Resend mailbox.</p>'),
    ))
    return [f"http://127.0.0.1:{base_port}/post/{index:04d}.html" for index in range(1, 4)]
