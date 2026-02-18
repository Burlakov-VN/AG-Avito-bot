"""LLM-based product description generator for Avito listings."""

import json
import logging

from avito_autoload.categorizers.llm_categorizer import (
    CategoryResult,
    _call_anthropic,
    _parse_llm_response,
)
from avito_autoload.describer.cache import DescriptionCache
from avito_autoload.models.avito_row import InputRow

logger = logging.getLogger(__name__)

BATCH_SIZE = 5

# Default company block — empty. Real company_block comes from template_config.
COMPANY_BLOCK = ""


def _build_items_text(
    items: list[dict],
    category_map: dict[str, CategoryResult],
) -> str:
    """Build items text block for the prompt."""
    items_text = ""
    for i, item in enumerate(items):
        cat = category_map.get(item["key"])
        cat_info = ""
        if cat and cat.spare_part_type:
            parts = [f'spare_part_type="{cat.spare_part_type}"']
            if cat.product_type:
                parts.append(f'product_type="{cat.product_type}"')
            cat_info = ", ".join(parts)

        items_text += (
            f'{i + 1}. article="{item["article"]}" '
            f'name="{item["name"]}" '
            f'price={item["price"]}'
        )
        if cat_info:
            items_text += f" ({cat_info})"
        items_text += "\n"
    return items_text


def _build_description_prompt(
    items: list[dict],
    category_map: dict[str, CategoryResult],
    title_info: str = "",
) -> str:
    """Build a universal prompt for generating titles + descriptions.

    Follows the 8-block reference structure:
    Blocks 1 (УТП), 2 (призыв), 4 (о товаре), 5 (преимущества) — generated per product.
    Blocks 3, 6, 7, 8 — company_block, added automatically after generation.
    """
    items_text = _build_items_text(items, category_map)

    title_rules = """
ПРАВИЛА ЗАГОЛОВКА (поле "title"):
- Средняя длина 50 символов, максимум 100 символов
- Формат: [Название товара] [артикул/модель] [применяемость если известна]
- Пиши СУХО и ИНФОРМАТИВНО — как в каталоге запчастей
- ЗАПРЕЩЕНО: эмодзи, капслок, восклицательные знаки, маркетинговые лозунги
- ЗАПРЕЩЕНО: "сердце двигателя", "надежность в каждой детали", "стабильная работа" и т.п.
- Примеры ХОРОШИХ заголовков: "Вал коленчатый Cummins С4934862 КамАЗ Евро-3/4", "Шайба 43202180Q КамАЗ. В наличии"
- Примеры ПЛОХИХ заголовков: "🔧 КОЛЕНВАЛ — СЕРДЦЕ ДВИГАТЕЛЯ!", "⚡ ШАЙБА — НАДЕЖНОСТЬ!"
"""
    if title_info and title_info.lower() != "авто":
        title_rules += f"\nДОПОЛНИТЕЛЬНЫЕ УКАЗАНИЯ ОТ ВЛАДЕЛЬЦА:\n{title_info}\n"

    return f"""Ты — опытный маркетолог-копирайтер для Авито.

ЗАДАЧА:
Для каждого товара создай:
1. ЗАГОЛОВОК объявления (поле "title") — для поля Title в Авито
2. ИНДИВИДУАЛЬНУЮ ЧАСТЬ описания (поле "description") — для поля Description
Блок о компании, условия покупки, доставка и финальный CTA добавляются к описанию АВТОМАТИЧЕСКИ — НЕ пиши их.
{title_rules}
СТРУКТУРА ОПИСАНИЯ (строго по пунктам):

1. НАЛИЧИЕ И ЦЕНА (1-2 строки):
   - Напиши что товар в наличии и укажи цену из данных
   - Пример: "✅ В наличии на складе. Цена: 60 830 ₽"
   - Если цена = 0, напиши просто "✅ В наличии. Уточняйте цену у менеджера"

2. ПРИЗЫВ К ДЕЙСТВИЮ (1 строка):
   - Короткий призыв: "Звоните или пишите — ответим быстро!"

3. Разделитель: _____________

4. БЛОК «О ТОВАРЕ» (📌):
   - Что это за товар (2-3 предложения)
   - Для чего предназначен, какую задачу решает
   - Ключевые характеристики и особенности

5. БЛОК «ПРЕИМУЩЕСТВА» (✅):
   - 3-5 пунктов через ✅, привязанных к товару

6. СТРОКА с артикулом и состоянием:
   🔸 Артикул: [артикул]
   🔸 Состояние: Новое

ПРАВИЛА:
- Пиши по-русски, деловой стиль без лишней креативности
- ЗАПРЕЩЕНО: капслок, восклицательные знаки подряд, рекламные лозунги
- ЗАПРЕЩЕНО: "сердце двигателя", "надежность в каждой детали" и подобные штампы
- НЕ пиши про компанию, доставку, оплату — добавляется автоматически!
- Длина описания: 150-300 слов (важно для SEO)
- Каждое описание должно быть УНИКАЛЬНЫМ

Товары:
{items_text}
Ответь ТОЛЬКО валидным JSON-массивом. Используй \\n для переносов строк внутри description:
[{{"index": 1, "title": "Заголовок для Авито до 100 символов", "description": "Текст описания..."}}]"""


def generate_descriptions(
    rows: list[InputRow],
    category_map: dict[str, CategoryResult],
    cache: DescriptionCache | None = None,
    company_block: str | None = None,
    description_prompt_template: str | None = None,
    *,
    title_info: str = "",
    title_map: dict[str, str] | None = None,
) -> dict[str, str]:
    """Generate descriptions (and titles) for input rows using LLM + cache.

    Args:
        rows: Input rows to generate descriptions for.
        category_map: Category results from LLM categorizer.
        cache: Description cache instance.
        company_block: Custom company block text (default: COMPANY_BLOCK).
        description_prompt_template: Custom LLM prompt for descriptions.
            If provided, used instead of _build_description_prompt().
            Must contain {items_text} placeholder.
        title_info: User's title format preferences.
        title_map: If provided, populated with key -> LLM-generated title.

    Returns mapping: key -> full description (product block + company block).
    """
    if cache is None:
        cache = DescriptionCache()

    effective_company_block = company_block if company_block is not None else COMPANY_BLOCK

    results: dict[str, str] = {}
    uncached: list[dict] = []

    # Check cache first
    for row in rows:
        key = row.article or row.name
        if not key:
            continue
        cached = cache.get(key)
        if cached is not None:
            results[key] = cached
        else:
            uncached.append({
                "article": row.article,
                "name": row.name,
                "key": key,
                "price": int(row.price) if row.price else 0,
            })

    if not uncached:
        logger.info("All %d descriptions found in cache", len(results))
        return results

    logger.info(
        "%d descriptions cached, %d need LLM generation",
        len(results),
        len(uncached),
    )

    # Process in batches
    for batch_start in range(0, len(uncached), BATCH_SIZE):
        batch = uncached[batch_start : batch_start + BATCH_SIZE]

        if description_prompt_template:
            # Build items_text for custom template
            items_text = _build_items_text(batch, category_map)
            prompt = description_prompt_template.replace("{items_text}", items_text)
        else:
            prompt = _build_description_prompt(batch, category_map, title_info)

        response = _call_anthropic(prompt)

        if response is None:
            for item in batch:
                full = effective_company_block
                results[item["key"]] = full
                cache.put(item["key"], full)
            continue

        parsed = _parse_llm_response(response)

        for entry in parsed:
            idx = entry.get("index", 0) - 1
            if 0 <= idx < len(batch):
                item = batch[idx]
                product_block = entry.get("description", "").strip()
                full = f"{product_block}\n\n{effective_company_block}" if product_block else effective_company_block
                results[item["key"]] = full
                cache.put(item["key"], full)

                # Extract title if present
                if title_map is not None:
                    llm_title = entry.get("title", "").strip()
                    if llm_title:
                        title_map[item["key"]] = llm_title

        # Fill missing entries
        for item in batch:
            if item["key"] not in results:
                results[item["key"]] = effective_company_block
                cache.put(item["key"], effective_company_block)

    cache.save()
    logger.info("Description generation complete: %d items", len(results))
    return results
