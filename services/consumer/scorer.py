def score_page(page_data):
    """Simple heuristic scoring for a crawled page. Returns 0.0-1.0."""
    score = 0.0

    title = page_data.get("title", "")
    meta_desc = page_data.get("meta_description", "")
    domain = page_data.get("domain", "")

    # has a title at all
    if title:
        score += 0.3

    # has a meta description
    if meta_desc:
        score += 0.3

    # longer titles tend to be more descriptive
    if len(title) > 20:
        score += 0.2

    # common TLDs get a small bonus
    if domain.endswith(".com") or domain.endswith(".org"):
        score += 0.2

    return round(score, 2)
