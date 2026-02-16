"""LLM-based product categorizer for Avito spare parts."""

import json
import logging
import os
from dataclasses import dataclass

from avito_autoload.categorizers.cache import CategoryCache
from avito_autoload.models.avito_row import InputRow

logger = logging.getLogger(__name__)

BATCH_SIZE = 30


@dataclass
class CategoryResult:
    goods_type: str = ""
    product_type: str = ""
    spare_part_type: str = ""
    sub_type: str = ""
    sub_type_field: str = ""


def _build_sections_description(categories_config: dict) -> str:
    """Build human-readable description of all category sections for the prompt."""
    sections = categories_config.get("sections", [])
    if not sections:
        # Fallback for old flat format
        spare_types = categories_config.get("spare_part_types", [])
        return f"GoodsType: Запчасти\n  ProductType: Для автомобилей\n    SparePartType: {json.dumps(spare_types, ensure_ascii=False)}"

    lines = []
    for section in sections:
        gt = section["goods_type"]
        if "product_types" in section:
            # Запчасти section with product_types
            for pt in section["product_types"]:
                pt_name = pt["name"]
                spts = pt.get("spare_part_types", [])
                lines.append(f'GoodsType="{gt}", ProductType="{pt_name}"')
                lines.append(f"  SparePartType: {json.dumps(spts, ensure_ascii=False)}")

                sub_types = pt.get("sub_types", {})
                for spt_name, sub_info in sub_types.items():
                    field = sub_info["field"]
                    values = sub_info["values"]
                    lines.append(f'  Если SparePartType="{spt_name}", укажи {field}: {json.dumps(values, ensure_ascii=False)}')
        else:
            # Generic section (Масла, Шины, etc.)
            cats = section.get("categories", [])
            lines.append(f'GoodsType="{gt}", категории: {json.dumps(cats, ensure_ascii=False)}')

    return "\n".join(lines)


def _build_prompt(items: list[dict], categories_config: dict) -> str:
    """Build the classification prompt for the LLM."""
    sections_desc = _build_sections_description(categories_config)

    items_text = "\n".join(
        f'{i+1}. article="{item["article"]}" name="{item["name"]}"'
        for i, item in enumerate(items)
    )

    return f"""Ты — классификатор товаров для Avito (раздел «Запчасти и аксессуары»).

Для каждого товара определи:
1. goods_type — вид товара
2. product_type — тип товара (только для GoodsType="Запчасти", иначе "")
3. spare_part_type — вид запчасти (только для GoodsType="Запчасти", иначе "")
4. sub_type — подтип запчасти (если есть поле с допустимыми значениями, иначе "")
5. sub_type_field — ТОЛЬКО одно из: "EngineSparePartType", "BodySparePartType", "TransmissionSparePartType", "TechnicSparePartType" или "" (пустая строка). НЕ используй "category" или другие значения.

Допустимые значения:
{sections_desc}

Правила:
- Если GoodsType НЕ "Запчасти" → product_type="", spare_part_type="", sub_type="", sub_type_field=""
- sub_type и sub_type_field ОБЯЗАТЕЛЬНЫ если для данного SparePartType указаны допустимые значения выше. Для ProductType="Для грузовиков и спецтехники" sub_type_field ВСЕГДА "TechnicSparePartType" — выбери ближайшее значение из списка
- SparePartType ОБЯЗАТЕЛЕН для GoodsType="Запчасти". Если не можешь определить точно — выбери ближайший по контексту (например: кожух пола → "Детали салона", защёлка буксирного крюка → "Рамы и детали рам", болт крепления рулевого механизма → "Подвеска и рулевое управление", заглушка → определи по контексту артикула/названия)
- Если не можешь определить goods_type — ставь goods_type = "".

Товары:
{items_text}

Ответь ТОЛЬКО валидным JSON-массивом. Каждый элемент:
{{"index": 1, "goods_type": "...", "product_type": "...", "spare_part_type": "...", "sub_type": "...", "sub_type_field": "..."}}"""


def _call_anthropic(prompt: str) -> str | None:
    """Call Anthropic Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping LLM categorization")
        return None

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        logger.exception("Anthropic API call failed")
        return None


def _parse_llm_response(response_text: str) -> list[dict]:
    """Parse LLM JSON response, handling markdown code blocks."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON")
        return []


def categorize_rows(
    rows: list[InputRow],
    categories_config: dict,
    cache: CategoryCache | None = None,
) -> dict[str, CategoryResult]:
    """Categorize input rows using LLM + cache.

    Returns mapping: article -> CategoryResult.
    """
    if cache is None:
        cache = CategoryCache()

    results: dict[str, CategoryResult] = {}
    uncached: list[dict] = []

    # Check cache first
    for row in rows:
        key = row.article or row.name
        if not key:
            continue
        cached = cache.get(key)
        if cached:
            results[key] = CategoryResult(
                goods_type=cached.get("goods_type", ""),
                product_type=cached.get("product_type", ""),
                spare_part_type=cached.get("spare_part_type", ""),
                sub_type=cached.get("sub_type", ""),
                sub_type_field=cached.get("sub_type_field", ""),
            )
        else:
            uncached.append({"article": row.article, "name": row.name, "key": key})

    if not uncached:
        logger.info("All %d items found in cache", len(results))
        return results

    logger.info("%d items cached, %d need LLM classification", len(results), len(uncached))

    # Process in batches
    for batch_start in range(0, len(uncached), BATCH_SIZE):
        batch = uncached[batch_start : batch_start + BATCH_SIZE]
        prompt = _build_prompt(batch, categories_config)
        response = _call_anthropic(prompt)

        if response is None:
            # No API key or error — leave empty
            for item in batch:
                results[item["key"]] = CategoryResult(spare_part_type="")
            continue

        parsed = _parse_llm_response(response)

        for entry in parsed:
            idx = entry.get("index", 0) - 1
            if 0 <= idx < len(batch):
                item = batch[idx]
                result = CategoryResult(
                    goods_type=entry.get("goods_type", ""),
                    product_type=entry.get("product_type", ""),
                    spare_part_type=entry.get("spare_part_type", ""),
                    sub_type=entry.get("sub_type", ""),
                    sub_type_field=entry.get("sub_type_field", ""),
                )
                results[item["key"]] = result
                cache.put(item["key"], {
                    "goods_type": result.goods_type,
                    "product_type": result.product_type,
                    "spare_part_type": result.spare_part_type,
                    "sub_type": result.sub_type,
                    "sub_type_field": result.sub_type_field,
                })

        # Fill missing entries from this batch
        for item in batch:
            if item["key"] not in results:
                results[item["key"]] = CategoryResult(spare_part_type="")

    cache.save()
    logger.info("Categorization complete: %d items", len(results))
    return results
