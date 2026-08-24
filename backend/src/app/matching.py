from __future__ import annotations

from app.models import JobPosting, UserPreferences


def is_recommended(job: JobPosting, preferences: UserPreferences) -> bool:
    if not preferences.locations and not preferences.keywords:
        return False

    # A job with no location extracted at all (common on career pages that don't
    # expose it as a distinct field) doesn't get disqualified by a location
    # preference — it just falls back to keyword-only matching.
    location_ok = (
        not preferences.locations
        or job.location is None
        or any(loc.lower() in job.location.lower() for loc in preferences.locations)
    )
    keyword_ok = not preferences.keywords or any(
        kw.lower() in job.title.lower() for kw in preferences.keywords
    )
    return location_ok and keyword_ok
