"""Generate Title field for Avito rows."""


def generate_title(article: str, name: str) -> str:
    """Generate title from article and product name.

    Article is prepended to name. If article is already present in name,
    it is not duplicated.
    """
    article = article.strip()
    name = name.strip()

    if not article:
        return name
    if not name:
        return article

    # If article is already part of the name, don't duplicate
    if article.lower() in name.lower():
        return name

    return f"{article} {name}"
