"""History derived from stored runs and the person's current case bands/exclusions."""

from sqlalchemy import select
from censearch.agent.web import loopback
from censearch.db import Case, CrawlRun, Scan
from censearch.whitelist import domains_for, matches
from urllib.parse import urlsplit


def history(session, person_id):
    domains = domains_for(session, person_id)
    cases_by_run = {}
    for case, run_id in session.execute(
        select(Case, Scan.run_id).join(Scan).where(Case.person_id == person_id)
    ):
        cases_by_run.setdefault(run_id, []).append(case)
    result = []
    for run in session.scalars(
        select(CrawlRun).order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc())
    ):
        public = run.config.get("public_search", False)
        request = run.config.get("request", {})
        cases = cases_by_run.get(run.id, [])
        if public:
            if request.get("person_id") != person_id:
                continue
            if request.get("mode") == "face_search":
                label = "FaceCheck · score above 90"
            elif request.get("mode") == "supplied_urls":
                label = f"{len(request.get('supplied_urls', []))} supplied URLs"
            else:
                label = request.get("full_name") or ", ".join(request.get("handles", []))
                label = label[:120] or "Public web search"
            discovery = run.config.get("discovery", {})
            pages = sum(bool(page.get("fetched_at")) for page in discovery.get("pages", []))
        else:
            if not cases:
                continue
            seeds = run.config.get("seeds", [])
            label = (
                "Mock web crawl"
                if seeds and all(loopback(urlsplit(url).hostname) for url in seeds)
                else f"{len(seeds)} supplied URLs"
            )
            pages = run.metrics.get("pages", 0)
        status = run.status
        if status in ("completed_with_errors", "completed_with_limits"):
            status = "completed"
        elif status not in ("queued", "running", "completed", "failed", "cancelled"):
            status = "failed"
        result.append(
            {
                "run_id": run.id,
                "kind": "public_search" if public else "crawl",
                "status": status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "label": label,
                "pages_fetched": pages,
                "images_checked": run.metrics.get("analysed", 0),
                "match_count": sum(case.band == "match" for case in cases),
                "possible_count": sum(case.band == "possible" for case in cases),
                "whitelisted_count": sum(matches(case.page_url, domains) for case in cases),
            }
        )
    return result
