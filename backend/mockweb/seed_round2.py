"""Independent six-scenario manifest. The product never imports this module."""

from mockweb.seed import Seeder, photos


def seed_round2(person, output, base_port):
    seeder = Seeder(output, base_port)
    original = photos(person / "originals")[0].read_bytes()
    wild = photos(person / "wild")[0].read_bytes()
    cases = [
        ("pixboard", original, True, "copyright_notice", "removed", ["site"]),
        ("friendlink", wild, False, "impersonation_report", "removed", ["site"]),
        ("localnews", wild, False, "leave_alone", "still_present", []),
        ("shadygallery", original, True, "copyright_notice", "removed", ["site", "host"]),
        ("shadygallery", original, True, "copyright_notice", "still_present", ["site", "host", "search"]),
        ("editorial", original, True, "privacy_request", "still_present", ["site"]),
    ]
    for site, payload, same, route, outcome, rungs in cases:
        seeder.add(site, payload, "demo-person", "scenario", same, authorized=site == "localnews")
        seeder.manifest[-1].update(
            expected_route=route,
            expected_outcome=outcome,
            expected_rungs=rungs,
            expected_delisted=rungs[-1:] == ["search"],
            expected_refusal=site == "editorial",
        )
    seeder.finish()
    return {"scenarios": len(cases), "manifest": str(output / "ground_truth.json")}
