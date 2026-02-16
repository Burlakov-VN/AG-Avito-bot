"""Async wrapper for the autoload pipeline — runs without typer dependency."""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from avito_autoload.config.settings import load_json_config
from avito_autoload.exporters.xlsx_exporter import export_to_xlsx
from avito_autoload.generators.date_gen import generate_date_begin
from avito_autoload.generators.id_gen import generate_id, generate_listing_id
from avito_autoload.generators.price_gen import calculate_price
from avito_autoload.generators.title_gen import generate_title
from avito_autoload.models.avito_row import AvitoRow, InputRow
from avito_autoload.parsers.xlsx_parser import parse_xlsx
from avito_autoload.validators.validator import validate_rows

logger = logging.getLogger(__name__)


def _run_pipeline_sync(
    pricelist_path: Path,
    output_path: Path,
    categories_config: dict,
    config_dir: Path,
    template_config: dict | None = None,
    project_code: str = "BT",
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Run pipeline synchronously (called via asyncio.to_thread).

    Returns dict with result statistics.
    """
    # Load standard configs
    columns_config = load_json_config(config_dir, "avito_columns.json")
    cities_config = load_json_config(config_dir, "cities.json")
    price_rules = load_json_config(config_dir, "price_rules.json")
    date_rules = load_json_config(config_dir, "date_rules.json")
    defaults = columns_config.get("defaults", {})

    all_cities = cities_config.get("cities", [])
    if not all_cities:
        return {"error": "Нет городов в конфиге"}

    # Parse input
    input_rows = parse_xlsx(pricelist_path)
    if not input_rows:
        return {"error": "Нет данных во входном файле"}

    # Split compound articles
    expanded: list[InputRow] = []
    for row in input_rows:
        if "/" in row.article:
            parts = [p.strip() for p in row.article.split("/") if p.strip()]
            for part in parts:
                expanded.append(row.model_copy(update={"article": part}))
        else:
            expanded.append(row)
    input_rows = expanded

    # Categorize
    from avito_autoload.categorizers.cache import CategoryCache
    from avito_autoload.categorizers.llm_categorizer import categorize_rows

    cache = CategoryCache()
    raw_results = categorize_rows(input_rows, categories_config, cache)
    category_map = {k: v for k, v in raw_results.items()}

    # Build TechnicSparePartType lookup
    technic_spt_lookup: dict[str, list[str]] = {}
    for section in categories_config.get("sections", []):
        for pt in section.get("product_types", []):
            if pt["name"] == "Для грузовиков и спецтехники":
                for spt_name, sub_info in pt.get("sub_types", {}).items():
                    if sub_info.get("field") == "TechnicSparePartType":
                        technic_spt_lookup[spt_name] = sub_info.get("values", [])

    # Generate descriptions
    from avito_autoload.describer.cache import DescriptionCache
    from avito_autoload.describer.llm_describer import generate_descriptions

    desc_cache = DescriptionCache()

    # Use custom template if provided
    custom_company_block = None
    custom_prompt_template = None
    if template_config:
        custom_company_block = template_config.get("company_block") or None
        custom_prompt_template = template_config.get("description_prompt") or None

    desc_map = generate_descriptions(
        input_rows,
        category_map,
        desc_cache,
        company_block=custom_company_block,
        description_prompt_template=custom_prompt_template,
    )

    if progress_callback:
        progress_callback(len(desc_map), len(input_rows))

    # Build AvitoRow list
    avito_rows: list[AvitoRow] = []
    total_rows = len(input_rows) * len(all_cities)
    base_category = categories_config.get("root_category", "")

    global_idx = 0
    for city_info in all_cities:
        city_prefix = city_info["prefix"]
        city_addresses = city_info.get("addresses", [])
        address = city_addresses[0] if city_addresses else ""

        for seq, input_row in enumerate(input_rows, start=1):
            title = generate_title(input_row.article, input_row.name)
            price = calculate_price(input_row.price, price_rules)
            listing_id = generate_listing_id(project_code, city_prefix, seq)
            row_id = generate_id(project_code, city_prefix, seq)
            date_begin = generate_date_begin(date_rules, index=global_idx, total=total_rows)

            cat_key = input_row.article or input_row.name
            cat_result = category_map.get(cat_key)

            goods_type = ""
            product_type = ""
            spare_part_type = ""
            engine_spt = ""
            body_spt = ""
            trans_spt = ""
            technic_spt = ""

            if cat_result:
                goods_type = cat_result.goods_type
                product_type = cat_result.product_type
                spare_part_type = cat_result.spare_part_type
                if cat_result.sub_type_field == "EngineSparePartType":
                    engine_spt = cat_result.sub_type
                elif cat_result.sub_type_field == "BodySparePartType":
                    body_spt = cat_result.sub_type
                elif cat_result.sub_type_field == "TransmissionSparePartType":
                    trans_spt = cat_result.sub_type
                elif cat_result.sub_type_field == "TechnicSparePartType":
                    technic_spt = cat_result.sub_type

                if product_type == "Для грузовиков и спецтехники" and not technic_spt:
                    values = technic_spt_lookup.get(spare_part_type, [])
                    if len(values) == 1:
                        technic_spt = values[0]

            description = desc_map.get(cat_key, "")

            avito_row = AvitoRow(
                id=row_id,
                listing_id=listing_id,
                title=title,
                description=description,
                price=price,
                date_begin=date_begin,
                address=address,
                category=base_category,
                goods_type=goods_type,
                product_type=product_type,
                spare_part_type=spare_part_type,
                engine_spare_part_type=engine_spt,
                body_spare_part_type=body_spt,
                transmission_spare_part_type=trans_spt,
                technic_spare_part_type=technic_spt,
                ad_type=defaults.get("AdType", "Товар приобретён на продажу"),
                condition=defaults.get("Condition", "Новое"),
                availability=defaults.get("Availability", "В наличии"),
                delivery=defaults.get("Delivery", "Да"),
                contact_method=defaults.get("ContactMethod", "По телефону и в сообщениях"),
                internet_calls=defaults.get("InternetCalls", "Да"),
                price_type=defaults.get("PriceType", "Точная"),
                contact_phone=defaults.get("ContactPhone", ""),
            )
            avito_rows.append(avito_row)
            global_idx += 1

    # Validate
    issues = validate_rows(avito_rows, columns_config)
    critical_count = sum(1 for i in issues if i["level"] == "critical")
    warning_count = sum(1 for i in issues if i["level"] == "warning")

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_to_xlsx(avito_rows, output_path, columns_config)

    categorized = sum(1 for v in category_map.values() if v.spare_part_type)

    return {
        "total_items": len(input_rows),
        "total_rows": len(avito_rows),
        "cities": len(all_cities),
        "descriptions": len(desc_map),
        "categorized": categorized,
        "total_categorized": len(category_map),
        "critical_issues": critical_count,
        "warning_issues": warning_count,
        "output_path": str(output_path),
    }


async def run_pipeline_async(
    pricelist_path: Path,
    output_path: Path,
    categories_config: dict,
    config_dir: Path,
    template_config: dict | None = None,
    project_code: str = "BT",
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Run the full pipeline asynchronously."""
    return await asyncio.to_thread(
        _run_pipeline_sync,
        pricelist_path,
        output_path,
        categories_config,
        config_dir,
        template_config,
        project_code,
        progress_callback,
    )


def format_pipeline_result(result: dict) -> str:
    """Format pipeline result as a Telegram message."""
    if "error" in result:
        return f"\u26a0\ufe0f Ошибка: {result['error']}"

    return (
        "\U0001F389 Файл автозагрузки готов!\n"
        "\n"
        "\U0001F4CA Итого:\n"
        f"\u2022 Товаров: {result['total_items']}\n"
        f"\u2022 Строк в файле: {result['total_rows']} (\u00d7{result['cities']} городов)\n"
        f"\u2022 Описания: {result['descriptions']} сгенерированы\n"
        f"\u2022 Категории: {result['categorized']}/{result['total_categorized']} определены\n"
        "\n"
        "\U0001F4E5 Скачай файл и загрузи в личном кабинете Авито:\n"
        "Авито \u2192 Профессиональные инструменты \u2192 Автозагрузка"
    )
