"""Fixed request language. No model imports or inferred attestations.

Copyright elements: https://www.copyright.gov/title17/92chap5.html#512
Intimate-image reports use platform-policy language, without a coverage assertion.
"""

import hashlib
import json

TEMPLATES = {
    "copyright_notice": (
        "I have a good faith belief that the use complained of is not authorized by the copyright owner, "
        "its agent, or the law.\n"
        "The information in this notice is accurate. Under penalty of perjury, I am authorized to act "
        "on behalf of the owner of the exclusive right allegedly infringed.\n"
        "Please remove or disable access to the identified material under 17 U.S.C. 512(c)(3)."
    ),
    "impersonation_report": (
        "I confirm this page impersonates me without my authorization. "
        "Please review it under your impersonation policy."
    ),
    "intimate_image_report": (
        "I am the identifiable individual in the intimate depiction. I have a good faith belief "
        "it was published without my consent. Please remove it under your intimate-image policy."
    ),
    "privacy_request": (
        "I am the depicted person and request removal for privacy reasons. This is a voluntary request "
        "and does not assert copyright ownership or a statutory removal duty."
    ),
}
RUNG_TEXT = {
    "site": "",
    "host": "The site has not resolved this request. Please review this abuse report as the service provider.",
    "search": "Please review delisting of this page. Delisting does not remove the source material.",
}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render(route, facts, contact, evidence, page_url, image_url, rung, date):
    if route not in TEMPLATES or rung not in RUNG_TEXT:
        raise ValueError("This route or rung has no notice template")
    required_facts = ["identity_confirmed", "accurate"]
    required_contact = ["name", "email", "signature"]
    if facts.get("authorized_use") is not False:
        raise ValueError("The person must explicitly attest that they did not agree to this use")
    if route == "copyright_notice":
        required_facts += ["owns_photo", "good_faith", "authority_under_perjury"]
        required_contact += ["address", "phone"]
        if (
            evidence.get("photo_relation") != "same_photo"
            or evidence.get("copy_relation") not in ("exact", "derived")
            or not evidence.get("original_sha256")
        ):
            raise ValueError("Copyright requires a verified copy of an identified original")
        if not str(facts.get("work_description") or "").strip():
            raise ValueError("Copyright requires the person's description of the protected work")
    elif route == "impersonation_report":
        required_facts += ["impersonates_me"]
    elif route == "intimate_image_report":
        required_facts += ["intimate", "identifiable", "good_faith"]
    else:
        required_facts += ["privacy_request"]
    missing = [key for key in required_facts if facts.get(key) is not True]
    missing += [key for key in required_contact if not contact.get(key, "").strip()]
    if missing:
        raise ValueError("Required attestations/contact fields missing: " + ", ".join(missing))
    lines = [f"Removal request: {route}", f"Date: {date}", f"Page: {page_url}", f"Image: {image_url}"]
    if route == "copyright_notice":
        lines += [
            f"Copyrighted work: {facts['work_description']}",
            f"Protected original SHA256: {evidence['original_sha256']}",
        ]
    lines += [
        TEMPLATES[route],
        RUNG_TEXT[rung],
        f"Person's explanation: {facts.get('explanation') or ''}",
        f"Name: {contact['name']}",
        f"Email: {contact['email']}",
        f"Address: {contact.get('address', '')}",
        f"Phone: {contact.get('phone', '')}",
        f"Electronic signature: {contact['signature']}",
    ]
    return "\n".join(line for line in lines if line)
