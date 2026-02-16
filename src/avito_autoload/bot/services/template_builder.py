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

    return f"""Ты — маркетолог-копирайтер для Авито. На основе анализа ЦА и конкурентов, создай шаблон для описания товаров.

НИША: «{niche}»

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

Создай:
1. Шаблон описания (структура блоков текста, которые будут генерироваться для КАЖДОГО товара)
2. Блок компании (фиксированный текст, добавляемый к каждому описанию)
3. 5 вариантов заголовков-крючков

Ответь СТРОГО в формате JSON:
{{
  "description_structure": [
    {{"block_name": "Заголовок-крючок", "description": "Что должно быть в блоке", "example": "Пример текста"}},
    {{"block_name": "О товаре", "description": "...", "example": "..."}},
    ...
  ],
  "headline_variants": [
    "\u2757\ufe0fВАРИАНТ 1\u2757\ufe0f",
    "\u26a1\ufe0fВАРИАНТ 2\u26a1\ufe0f",
    "\U0001F525ВАРИАНТ 3\U0001F525",
    "\u2757\ufe0fВАРИАНТ 4\u2757\ufe0f",
    "\u26a1\ufe0fВАРИАНТ 5\u26a1\ufe0f"
  ],
  "company_block": "Полный текст блока о компании с доставкой, оплатой и CTA. Используй эмодзи. Разделители: _____________",
  "description_prompt": "Полный промпт для LLM, который будет генерировать описания товаров. Включи всю структуру, правила, примеры. Промпт будет принимать список товаров с артикулами и ценами.",
  "summary": "Краткое описание шаблона для пользователя (2-3 предложения)"
}}

Ответь ТОЛЬКО валидным JSON."""


async def build_template(
    niche: str,
    ca_data: dict,
    competitor_data: dict,
) -> dict:
    """Generate description template via LLM.

    Returns dict with: description_structure, headline_variants,
    company_block, description_prompt, summary.
    """
    prompt = _build_template_prompt(niche, ca_data, competitor_data)
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
    """Return a reasonable default template."""
    return {
        "description_structure": [
            {"block_name": "Заголовок-крючок", "description": "Яркий УТП с эмодзи", "example": "\u2757\ufe0fВ НАЛИЧИИ НА СКЛАДЕ \u2014 ОТПРАВИМ СЕГОДНЯ\u2757\ufe0f"},
            {"block_name": "О товаре", "description": "Назначение, функция, важность", "example": ""},
            {"block_name": "Преимущества", "description": "3-4 пункта с эмодзи", "example": ""},
            {"block_name": "Артикул", "description": "Артикул + состояние", "example": ""},
        ],
        "headline_variants": [
            "\u2757\ufe0fВ НАЛИЧИИ НА СКЛАДЕ \u2014 ОТПРАВИМ СЕГОДНЯ\u2757\ufe0f",
            "\u26a1\ufe0fНУЖЕН ТОВАР СРОЧНО? ОН УЖЕ НА СКЛАДЕ\u26a1\ufe0f",
            "\U0001F525НОВЫЙ ТОВАР ПО ЦЕНЕ НИЖЕ ДИЛЕРСКОЙ\U0001F525",
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
