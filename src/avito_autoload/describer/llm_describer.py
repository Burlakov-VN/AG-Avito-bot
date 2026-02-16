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

# Fixed company block appended to every description
COMPANY_BLOCK = """
_____________

🏢 О НАС

Компания «Китай-город» — специализированный поставщик запчастей для грузовиков и спецтехники. Работаем напрямую с заводами — без посредников и наценок.

✔️ 150 000+ позиций в наличии на складе
✔️ Специализация: Shacman, Howo, FAW, Foton, Dongfeng, КАМАЗ, Урал, МАЗ
✔️ Только НОВЫЕ запчасти с гарантией
✔️ Цены ниже дилерских — работаем напрямую с производителями
✔️ Быстрый подбор по артикулу, VIN или названию
✔️ Склады в Казани и Челябинске
✔️ Работаем с юр. лицами (НДС) и физ. лицами
✔️ Скидки оптовым клиентам и автосервисам

_____________

🚚 ДОСТАВКА И САМОВЫВОЗ

• Самовывоз из Казани или Челябинска
• Бесплатная доставка до транспортной компании
• Отправка в день заказа — товар уже на складе!
• ТК на выбор: СДЭК, ПЭК, Деловые Линии, Энергия, КИТ и др.
• Доставка по всей России и СНГ

💼 Оплата: наличные, перевод на карту, расчётный счёт

_____________

📞 Звоните прямо сейчас или пишите в чат Avito!
Быстрый подбор, консультация, оперативная отгрузка!

🔹 Не нашли нужную деталь? Позвоните — подберём аналог!

❤️ Добавьте в избранное, чтобы не потерять
✍🏻 Подпишитесь на профиль, нажав ПОДПИСАТЬСЯ внизу 👇👇👇👇
""".strip()


def _build_description_prompt(
    items: list[dict],
    category_map: dict[str, CategoryResult],
) -> str:
    """Build prompt for generating product-specific description blocks."""
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

    return f"""Ты — опытный маркетолог-копирайтер для Авито. Специализация: запчасти для грузовиков и спецтехники.

КОНТЕКСТ:
Компания «Китай-город» продаёт НОВЫЕ запчасти для грузовиков и спецтехники. Специализация — китайские марки (Shacman, Howo, FAW, Foton, Dongfeng), а также КАМАЗ, Урал, МАЗ и др. 150 000+ позиций В НАЛИЧИИ. Склады в Казани и Челябинске.

ЦЕЛЕВАЯ АУДИТОРИЯ И ИХ БОЛИ:
- Частники-водители: грузовик стоит = деньги теряются, каждый день простоя — убыток 5-15 тыс. руб. Ищут деталь СРОЧНО, а конкуренты говорят "под заказ 2-4 недели"
- Автосервисы: клиент ждёт, репутация на кону, нужна деталь быстро и с гарантией
- Оптовики: важна цена и стабильные поставки

ЗАДАЧА:
Для каждого товара напиши ВЕРХНЮЮ ЧАСТЬ описания (блок про сам товар). Нижнюю часть (о компании, доставка, CTA) мы добавляем АВТОМАТИЧЕСКИ — НЕ пиши её.

СТРУКТУРА ВЕРХНЕЙ ЧАСТИ (строго по пунктам):

1. ЗАГОЛОВОК-КРЮЧОК (1-2 строки):
   - Используй разные варианты! Примеры:
     ❗️В НАЛИЧИИ НА СКЛАДЕ — ОТПРАВИМ СЕГОДНЯ❗️
     ⚡️НУЖНА ЗАПЧАСТЬ СРОЧНО? ОНА УЖЕ НА СКЛАДЕ⚡️
     🔥 НОВАЯ ЗАПЧАСТЬ ПО ЦЕНЕ НИЖЕ ДИЛЕРСКОЙ 🔥
     ❗️МАШИНА СТОИТ? ДЕТАЛЬ В НАЛИЧИИ — РЕШИМ ПРОБЛЕМУ❗️
     ⚡️150 000 ЗАПЧАСТЕЙ В НАЛИЧИИ — НЕ НУЖНО ЖДАТЬ ЗАКАЗ⚡️
   - ВАЖНО: чередуй варианты! Не используй один и тот же для всех товаров в батче

2. Разделитель: _____________

3. БЛОК «О ТОВАРЕ» (📌):
   - Что это за деталь (2-3 предложения)
   - Какую функцию выполняет в автомобиле
   - Почему важна (к чему приводит износ/поломка)
   - Если деталь простая (болт, гайка, втулка) — опиши её роль в узле

4. БЛОК «ПРИМЕНЯЕМОСТЬ» (✅):
   - Укажи конкретные марки и модели через ✅
   - Определи по артикулу или названию (префиксы: 2360/2206 = УАЗ, 4320/375 = Урал, 5557 = Урал, 43206 = Урал, 740 = КАМАЗ, DZ = Shacman, WG = Howo, VG = Howo)
   - Если не можешь определить точно — напиши "✅ Уточняйте применяемость — подберём по VIN или артикулу"

5. БЛОК «ПОЧЕМУ СТОИТ КУПИТЬ У НАС» (🔹):
   - 3-4 пункта через 🔹, привязанных к КОНКРЕТНОМУ товару:
     🔹 В наличии на складе — отправка в день заказа
     🔹 Новая деталь с гарантией (не б/у, не восстановленная)
     🔹 Цена ниже дилерской — работаем напрямую
     🔹 Подберём аналоги, если артикул отличается
   - Варьируй формулировки, адаптируй под конкретную деталь

6. СТРОКА с артикулом и состоянием:
   🔸 Артикул: [артикул из данных]
   🔸 Состояние: Новое

ПРАВИЛА:
- Пиши по-русски, деловой но дружелюбный стиль
- Используй эмодзи: ❗️ ⚡️ 🔥 📌 ✅ 🔹 🔸 🛡️
- НЕ пиши про компанию, доставку, CTA, контакты — это добавляется автоматически!
- Длина: 150-300 слов на товар (это важно для SEO на Авито!)
- Каждое описание должно быть УНИКАЛЬНЫМ — не копируй одну структуру слово в слово
- Если не можешь определить назначение по названию — опиши общее назначение для данной категории запчастей

Товары:
{items_text}
Ответь ТОЛЬКО валидным JSON-массивом. Используй \\n для переносов строк внутри description:
[{{"index": 1, "description": "..."}}]"""


def generate_descriptions(
    rows: list[InputRow],
    category_map: dict[str, CategoryResult],
    cache: DescriptionCache | None = None,
    company_block: str | None = None,
    description_prompt_template: str | None = None,
) -> dict[str, str]:
    """Generate descriptions for input rows using LLM + cache.

    Args:
        rows: Input rows to generate descriptions for.
        category_map: Category results from LLM categorizer.
        cache: Description cache instance.
        company_block: Custom company block text (default: COMPANY_BLOCK).
        description_prompt_template: Custom LLM prompt for descriptions.
            If provided, used instead of _build_description_prompt().
            Must contain {items_text} placeholder.

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
            items_text = ""
            for i, item in enumerate(batch):
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
            prompt = description_prompt_template.replace("{items_text}", items_text)
        else:
            prompt = _build_description_prompt(batch, category_map)

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

        # Fill missing entries
        for item in batch:
            if item["key"] not in results:
                results[item["key"]] = effective_company_block
                cache.put(item["key"], effective_company_block)

    cache.save()
    logger.info("Description generation complete: %d items", len(results))
    return results
