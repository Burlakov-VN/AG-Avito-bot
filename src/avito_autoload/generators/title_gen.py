"""Generate Title field for Avito rows."""


def generate_title(
    article: str,
    name: str,
    *,
    suffix: str = "Новое",
) -> str:
    """Generate title from article and product name.

    Article is prepended to name. If article is already present in name,
    it is not duplicated. Suffix (e.g. "Новое") is appended if it fits
    within Avito's 50-char title limit.
    """
    article = article.strip()
    name = name.strip()

    if not article:
        base = name
    elif not name:
        base = article
    elif article.lower() in name.lower():
        # Article already part of the name — don't duplicate
        base = name
    else:
        base = f"{article} {name}"

    if not base:
        return ""

    # Append suffix if it fits (Avito title limit ~50 chars)
    if suffix:
        with_suffix = f"{base} {suffix}"
        if len(with_suffix) <= 50:
            return with_suffix

    # Truncate if too long
    if len(base) > 50:
        return base[:47] + "..."
    return base
