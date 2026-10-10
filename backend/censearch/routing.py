"""Pure, versioned route rules. Only user answers establish personal facts."""

QUESTIONS = {
    "identity_confirmed": "Is this you?",
    "owns_photo": "Do you own this exact photo?",
    "authorized_use": "Did you agree to this use?",
    "impersonates_me": "Is the page pretending to be you?",
    "intimate": "Is it an intimate image?",
    "privacy_request": "Do you want it removed for privacy?",
}
EXTRA_QUESTIONS = {
    "legitimate_use": "Is this a legitimate use you want to leave alone?",
    "identifiable": "Are you identifiable in the intimate image?",
    "good_faith": "Do you believe in good faith that this use lacks permission or legal authorization?",
    "accurate": "Is the information you supplied accurate?",
    "authority_under_perjury": "Under penalty of perjury, are you authorized to act for the copyright owner?",
}


def decide(answers, evidence):
    """Return a route, stable rule ID and the exact relevant input snapshot."""

    def yes(key):
        return answers.get(key) is True

    no_consent = answers.get("authorized_use") is False
    if yes("authorized_use") or yes("legitimate_use"):
        route, rule = "leave_alone", "authorized_or_legitimate_use"
    elif not yes("identity_confirmed"):
        route, rule = "hold_for_review", "identity_not_confirmed"
    elif yes("intimate") and yes("identifiable") and no_consent:
        route, rule = "intimate_image_report", "attested_nonconsensual_intimate_depiction"
    elif yes("impersonates_me") and no_consent:
        route, rule = "impersonation_report", "attested_impersonation"
    elif (
        yes("owns_photo")
        and no_consent
        and evidence.get("photo_relation") == "same_photo"
        and evidence.get("copy_relation") in ("exact", "derived")
        and evidence.get("original_id")
    ):
        route, rule = "copyright_notice", "owned_verified_same_photo"
    elif (
        yes("owns_photo")
        and no_consent
        and (evidence.get("copy_relation") == "uncertain" or evidence.get("photo_relation") == "uncertain")
    ):
        route, rule = "hold_for_review", "unresolved_copy"
    elif yes("privacy_request") and no_consent:
        route, rule = "privacy_request", "attested_privacy_request"
    else:
        route, rule = "leave_alone", "no_attested_removal_basis"
    return {
        "route": route,
        "rule_id": rule,
        "version": "rules-v2",
        "inputs": {"answers": dict(answers), "evidence": dict(evidence)},
    }
