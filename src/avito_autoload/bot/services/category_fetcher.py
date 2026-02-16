"""Dynamic category fetching for any Avito niche."""

import asyncio
import json
import logging
from pathlib import Path

from avito_autoload.categorizers.llm_categorizer import _call_anthropic

logger = logging.getLogger(__name__)


def _determine_root_category(niche: str) -> str:
    """Use LLM to determine the Avito root category for a niche."""
    prompt = f"""Определи корневую категорию Авито (самую верхнюю категорию из дерева категорий) для следующей ниши:

Ниша: «{niche}»

Возможные корневые категории Авито:
- Транспорт
- Недвижимость
- Работа
- Услуги
- Личные вещи
- Для дома и дачи
- Бытовая электроника
- Хобби и отдых
- Животные
- Для бизнеса

Также определи путь к подкатегории (через " → ").

Ответь СТРОГО в JSON:
{{"root_category": "Транспорт", "category_path": ["Транспорт", "Запчасти и аксессуары"], "category_name": "Запчасти и аксессуары"}}

Ответь ТОЛЬКО валидным JSON."""

    response = _call_anthropic(prompt)
    if response is None:
        return ""

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return data.get("category_name", "")
    except json.JSONDecodeError:
        return ""


async def fetch_categories_for_niche(
    niche: str,
    output_dir: Path,
) -> dict:
    """Fetch Avito categories for a given niche.

    Uses Avito API to get the category tree, then builds
    avito_categories.json for the relevant branch.

    Returns the categories config dict.
    """
    from avito_autoload.avito_api.auth import AvitoAuth
    from avito_autoload.avito_api.categories import (
        AvitoCategoryFetcher,
        build_categories_from_api,
    )

    auth = AvitoAuth()
    if not auth.is_configured:
        logger.warning("Avito API credentials not configured")
        return {"root_category": "", "sections": []}

    # Determine root category
    root_name = await asyncio.to_thread(_determine_root_category, niche)
    logger.info("Determined root category for '%s': %s", niche, root_name)

    # Fetch categories from API
    with AvitoCategoryFetcher(auth) as fetcher:
        categories = await asyncio.to_thread(build_categories_from_api, fetcher)

    # Save to project dir
    output_path = output_dir / "avito_categories.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    logger.info("Categories saved to %s", output_path)
    return categories


def format_categories_summary(categories: dict) -> str:
    """Format categorization results as a Telegram message."""
    sections = categories.get("sections", [])
    root = categories.get("root_category", "")

    total_cats = sum(
        len(s.get("categories", []))
        + sum(len(pt.get("spare_part_types", [])) for pt in s.get("product_types", []))
        for s in sections
    )

    lines = [
        "\u2705 Этап 3/4: Категоризация завершена",
        "",
        f"\U0001F4C2 Корневая категория: {root}",
        f"\U0001F4CA Секций (GoodsType): {len(sections)}",
        f"\U0001F4CA Всего категорий: {total_cats}",
        "",
        "Распределение по секциям:",
    ]

    for section in sections:
        gt = section.get("goods_type", "")
        cats = section.get("categories", [])
        pts = section.get("product_types", [])
        count = len(cats) + sum(len(pt.get("spare_part_types", [])) for pt in pts)
        lines.append(f"\u2022 {gt}: {count} категорий")

    return "\n".join(lines)
