"""Description template builder — generates dynamic prompt and company block."""

import asyncio
import json
import logging

from avito_autoload.categorizers.llm_categorizer import _call_anthropic

logger = logging.getLogger(__name__)


def _build_template_prompt(
    niche: str,
    ca_data: dict,
    competitor_data: dict,
    company_info: str = "",
) -> str:
    """Build prompt to generate a description template."""
    segments = ca_data.get("segments", [])
    pain_points = ca_data.get("pain_points", [])
    top_usp = ca_data.get("top_usp", [])
    tone = ca_data.get("tone", "")
    best_practices = competitor_data.get("best_practices", [])
    emojis = competitor_data.get("emojis", [])
    optimal_length = competitor_data.get("optimal_length_words", [150, 300])
    key_phrases = competitor_data.get("key_phrases", [])

    company_section = ""
    if company_info:
        company_section = f"""
ИНФОРМАЦИЯ О КОМПАНИИ (от владельца):
{company_info}

ВАЖНО: Используй эту информацию при создании блока о компании (company_block) и промпта для описаний (description_prompt). Не выдумывай факты — опирайся на данные выше.
"""

    return f"""Ты — маркетолог-копирайтер для Авито. На основе анализа ЦА и конкурентов, создай шаблон для описания товаров.

НИША: «{niche}»
{company_section}
АНАЛИЗ ЦА:
- Сегменты: {json.dumps(segments, ensure_ascii=False)}
- Боли: {json.dumps(pain_points, ensure_ascii=False)}
- Топ УТП: {json.dumps(top_usp, ensure_ascii=False)}
- Тон: {tone}

АНАЛИЗ КОНКУРЕНТОВ:
- Лучшие практики: {json.dumps(best_practices, ensure_ascii=False)}
- Эмодзи: {json.dumps(emojis, ensure_ascii=False)}
- Оптимальная длина: {optimal_length[0]}-{optimal_length[1]} слов
- Ключевые фразы: {json.dumps(key_phrases, ensure_ascii=False)}

ЭТАЛОННАЯ СТРУКТУРА ОПИСАНИЯ (8 блоков — адаптируй под нишу):

1. Главное УТП или акция — яркий крючок в самом начале, привлекающий внимание. С эмодзи.
2. Призыв к действию — короткий призыв (позвоните/напишите/закажите). Создаёт ощущение срочности.
3. Краткая информация о продавце — кто вы, чем занимаетесь (2-3 предложения).
4. Блок про товар/услугу — подробное описание конкретного товара или услуги: что это, для чего, характеристики.
5. Блок с преимуществами — 3-5 пунктов: почему стоит купить именно у вас (с эмодзи-маркерами ✅ 🔹).
6. Блок «условия покупки» — доставка, оплата, самовывоз, гарантия.
7. Дополнительные услуги — что ещё можете предложить (консультация, подбор, монтаж и т.д.).
8. Призыв к действию — финальный CTA: звоните, пишите, добавляйте в избранное.

ВАЖНО: Блоки 1-2 и 4-5 генерируются ИНДИВИДУАЛЬНО для каждого товара. Блоки 3, 6, 7, 8 — это ФИКСИРОВАННЫЙ блок компании (company_block), одинаковый для всех товаров.

ПРИМЕР ПОЛНОГО ОПИСАНИЯ (металлопрокат — для понимания структуры):

--- ИНДИВИДУАЛЬНАЯ ЧАСТЬ (генерируется для каждого товара) ---
✅ Мы онлайн! Лучшая цена на арматуру 12 мм          ← блок 1: УТП/акция
🚩 Нашли дешевле? Снизим цену!                        ← блок 1
Прямые поставки | Доставка в день заказа              ← блок 2: призыв
_____________
Характеристики:                                       ← блок 4: о товаре
• Диаметр: 12
• Марка стали: А500С
• ГОСТ: 5781-82 / 52544-2006
Почему берут у нас:                                   ← блок 5: преимущества
✔ Прямые поставки с завода — честная цена
✔ Сталь по ГОСТ — не ломается при изгибе
✔ Тройной контроль взвешивания — без недовеса

--- ФИКСИРОВАННЫЙ БЛОК КОМПАНИИ (company_block) ---
_____________
Мы — ГК «МеталлПроект», металлобаза в СПб.           ← блок 3: о продавце
Доставка по СПб и ЛО. Возможна в день заказа.        ← блок 6: условия
Доп. услуги: резка, сварка, фиксаторы                ← блок 7: доп. услуги
📞 Звоните — всегда на связи!                         ← блок 8: финальный CTA

Создай:
1. Шаблон описания (структура блоков текста, которые будут генерироваться для КАЖДОГО товара — блоки 1, 2, 4, 5 из эталона)
2. Блок компании (фиксированный текст — блоки 3, 6, 7, 8 из эталона: информация о компании, условия, доп. услуги, финальный CTA). Используй эмодзи и разделители _____________
3. 5 вариантов заголовков-крючков для блока 1
4. Промпт для LLM, который будет генерировать индивидуальные описания для каждого товара

Ответь СТРОГО в формате JSON:
{{
  "description_structure": [
    {{"block_name": "Заголовок-крючок (УТП/акция)", "description": "Что должно быть в блоке", "example": "Пример текста"}},
    {{"block_name": "Призыв к действию", "description": "...", "example": "..."}},
    {{"block_name": "О товаре/услуге", "description": "...", "example": "..."}},
    {{"block_name": "Преимущества", "description": "...", "example": "..."}}
  ],
  "headline_variants": [
    "\u2757\ufe0fВАРИАНТ 1\u2757\ufe0f",
    "\u26a1\ufe0fВАРИАНТ 2\u26a1\ufe0f",
    "\U0001F525ВАРИАНТ 3\U0001F525",
    "\u2757\ufe0fВАРИАНТ 4\u2757\ufe0f",
    "\u26a1\ufe0fВАРИАНТ 5\u26a1\ufe0f"
  ],
  "company_block": "Полный текст фиксированного блока компании (информация о компании + условия покупки + доп. услуги + финальный CTA). Используй эмодзи. Разделители: _____________",
  "description_prompt": "Полный промпт для LLM, который будет генерировать ЗАГОЛОВОК (title) и ИНДИВИДУАЛЬНУЮ часть описания (description) для каждого товара. Промпт принимает список товаров через {{items_text}}. Должен возвращать JSON-массив [{{'index': 1, 'title': 'Заголовок для Авито до 100 символов', 'description': '...'}}]. НЕ должен генерировать блок компании. Правила title: 50-100 символов, название + ключевая характеристика + выгода, без эмодзи.",
  "full_template": "Полный текст шаблона в формате Markdown для отправки пользователю как PDF",
  "summary": "Краткое описание шаблона для пользователя (2-3 предложения)"
}}

Ответь ТОЛЬКО валидным JSON."""


async def build_template(
    niche: str,
    ca_data: dict,
    competitor_data: dict,
    company_info: str = "",
) -> dict:
    """Generate description template via LLM.

    Returns dict with: description_structure, headline_variants,
    company_block, description_prompt, summary.
    """
    prompt = _build_template_prompt(niche, ca_data, competitor_data, company_info)
    response = await asyncio.to_thread(_call_anthropic, prompt)

    if response is None:
        return _default_template(niche)

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
        # Validate required fields
        if not result.get("company_block") or not result.get("description_prompt"):
            logger.warning("Template missing required fields, using defaults")
            return _default_template(niche)
        return result
    except json.JSONDecodeError:
        logger.warning("Failed to parse template JSON")
        return _default_template(niche)


def _default_template(niche: str) -> dict:
    """Return a reasonable default template following the 8-block structure."""
    return {
        "description_structure": [
            {"block_name": "Заголовок-крючок (УТП/акция)", "description": "Яркий УТП или акция с эмодзи — привлекает внимание", "example": "\u2757\ufe0fВ НАЛИЧИИ \u2014 ОТПРАВИМ СЕГОДНЯ\u2757\ufe0f"},
            {"block_name": "Призыв к действию", "description": "Короткий призыв: позвоните/напишите", "example": "\u260e\ufe0f Позвоните или напишите прямо сейчас!"},
            {"block_name": "О товаре/услуге", "description": "Подробное описание: что это, для чего, характеристики", "example": ""},
            {"block_name": "Преимущества", "description": "3-5 пунктов через \u2705 или \U0001F539: почему стоит купить у нас", "example": ""},
        ],
        "headline_variants": [
            "\u2757\ufe0fВ НАЛИЧИИ \u2014 ОТПРАВИМ СЕГОДНЯ\u2757\ufe0f",
            "\u26a1\ufe0fНУЖНО СРОЧНО? ТОВАР УЖЕ НА СКЛАДЕ\u26a1\ufe0f",
            "\U0001F525ЦЕНА НИЖЕ РЫНОЧНОЙ \u2014 РАБОТАЕМ НАПРЯМУЮ\U0001F525",
            "\u2757\ufe0fОГРОМНЫЙ ВЫБОР В НАЛИЧИИ\u2757\ufe0f",
            "\u26a1\ufe0fБЫСТРАЯ ОТПРАВКА ПО ВСЕЙ РОССИИ\u26a1\ufe0f",
        ],
        "company_block": "",
        "description_prompt": "",
        "summary": f"Стандартный шаблон для ниши \u00ab{niche}\u00bb",
    }


def format_template_summary(template: dict, sample_description: str = "") -> str:
    """Format template as a Telegram message."""
    structure = template.get("description_structure", [])
    headlines = template.get("headline_variants", [])
    summary = template.get("summary", "")

    lines = [
        "\u2705 Этап 2/4: Шаблон описаний готов",
        "",
        "\U0001F4DD Структура описания:",
        "",
    ]

    for i, block in enumerate(structure, 1):
        lines.append(f"{i}. {block.get('block_name', '')}")

    if headlines:
        lines.extend(["", "\U0001F525 Варианты заголовков:"])
        for h in headlines[:5]:
            lines.append(f"\u2022 {h}")

    if summary:
        lines.extend(["", f"\U0001F4CA {summary}"])

    if sample_description:
        lines.extend([
            "",
            "\u2014\u2014\u2014",
            "\U0001F4D6 Пример описания:",
            "",
            sample_description[:2000],
            "\u2014\u2014\u2014",
        ])

    return "\n".join(lines)
