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


_HEADER_ALIASES: dict[str, str] = {
    "код": "Код",
    "артикул": "Артикул",
    "наименование": "Наименование",
    "название": "Наименование",
    "номенклатура": "Наименование",
    "цена": "Цена",
    "цена за штуку": "Цена",
    "цена за ед": "Цена",
    "стоимость": "Цена",
}

_KNOWN_HEADERS = set(_HEADER_ALIASES.keys())


def text_to_temp_xlsx(text: str, output_dir: Path) -> Path:
    """Parse user's text pricelist into a temporary XLSX file.

    Handles four formats:
    1. Tab-separated table (copy from Excel)
    2. Vertical table (each cell on a separate line, common in Telegram)
    3. Space-separated table with recognized header line (Telegram strips tabs)
    4. Plain text (each line = product name)

    Returns path to the created XLSX file.
    """
    from openpyxl import Workbook

    lines = [l for l in text.strip().split("\n") if l.strip()]
    if not lines:
        raise ValueError("Пустой текст прайс-листа")

    wb = Workbook()
    ws = wb.active

    if "\t" in lines[0]:
        # Format 1: Tab-separated
        _write_tab_separated(ws, lines)
    else:
        # Check for vertical table: first N lines are known headers
        header_count = 0
        for line in lines:
            if line.strip().lower() in _KNOWN_HEADERS:
                header_count += 1
            else:
                break

        if header_count >= 2:
            # Format 2: Vertical table
            _write_vertical_table(ws, lines, header_count)
        elif _is_space_separated_table(lines[0]):
            # Format 3: Space-separated table with header line
            _write_space_separated(ws, lines)
        else:
            # Format 4: Plain text — each line is a product name
            ws.append(["Код", "Наименование"])
            for i, line in enumerate(lines, 1):
                ws.append([str(i), line.strip()])

    xlsx_path = output_dir / "pricelist_from_text.xlsx"
    output_dir.mkdir(parents=True, exist_ok=True)
    wb.save(xlsx_path)
    wb.close()

    data_rows = max(ws.max_row - 1, 0) if ws.max_row else 0
    logger.info("Created temp XLSX from text: %d rows -> %s", data_rows, xlsx_path)
    return xlsx_path


def _write_tab_separated(ws: Any, lines: list[str]) -> None:
    """Write tab-separated data to worksheet."""
    raw_headers = [c.strip() for c in lines[0].split("\t")]
    normalized = [_HEADER_ALIASES.get(h.strip().lower(), h) for h in raw_headers]

    if "Код" not in normalized:
        normalized.insert(0, "Код")
        ws.append(normalized)
        for i, line in enumerate(lines[1:], 1):
            cells = [c.strip() for c in line.split("\t")]
            ws.append([str(i)] + cells)
    else:
        ws.append(normalized)
        for line in lines[1:]:
            cells = [c.strip() for c in line.split("\t")]
            ws.append(cells)


def _write_vertical_table(
    ws: Any, lines: list[str], header_count: int,
) -> None:
    """Write vertical table (each cell on separate line) to worksheet."""
    raw_headers = [lines[i].strip() for i in range(header_count)]
    normalized = [_HEADER_ALIASES.get(h.lower(), h) for h in raw_headers]

    if "Код" not in normalized:
        normalized.insert(0, "Код")
        ws.append(normalized)
        data_lines = lines[header_count:]
        row_idx = 1
        # Group data lines by (header_count - 1) since Код is auto-generated
        group_size = header_count
        for start in range(0, len(data_lines), group_size):
            group = data_lines[start : start + group_size]
            if not group or not group[0].strip():
                continue
            ws.append([str(row_idx)] + [v.strip() for v in group])
            row_idx += 1
    else:
        ws.append(normalized)
        data_lines = lines[header_count:]
        for start in range(0, len(data_lines), header_count):
            group = data_lines[start : start + header_count]
            if not group or not group[0].strip():
                continue
            ws.append([v.strip() for v in group])


import re

# Price at end of line: "60 830,00" or "76021.50" or "18 617,50"
_PRICE_RE = re.compile(r"(\d[\d\s]*[,\.]\d{2})\s*$")
# Simpler: just integer price at end "12345"
_PRICE_INT_RE = re.compile(r"(\d[\d\s]+)\s*$")


def _is_space_separated_table(first_line: str) -> bool:
    """Check if the first line looks like a space-separated header row."""
    words = first_line.strip().lower()
    # Count how many known headers are found in this line
    found = 0
    for header in _KNOWN_HEADERS:
        if header in words:
            found += 1
    return found >= 2


def _write_space_separated(ws: Any, lines: list[str]) -> None:
    """Write space-separated table (Telegram-pasted from Excel).

    First line is a header row like "Код Артикул Наименование Цена за штуку".
    Data lines like "50007026 7170290 Стекло 7170290 60 830,00".

    Strategy: extract price from end (regex), code from start (first number),
    article (second token), and name from the middle.
    """
    # Detect which headers are present
    header_line = lines[0].strip().lower()
    has_code = any(h in header_line for h in ["код"])
    has_article = any(h in header_line for h in ["артикул"])
    has_name = any(h in header_line for h in ["наименование", "название", "номенклатура"])
    has_price = any(h in header_line for h in ["цена", "стоимость"])

    # Build output headers
    out_headers = ["Код"]
    if has_article:
        out_headers.append("Артикул")
    out_headers.append("Наименование")
    if has_price:
        out_headers.append("Цена")
    ws.append(out_headers)

    auto_code = 1
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        # Step 1: extract price from the end
        price_str = ""
        remaining = line
        m = _PRICE_RE.search(remaining)
        if m and has_price:
            price_str = m.group(1).strip()
            remaining = remaining[: m.start()].strip()
        elif has_price:
            # Try integer price
            m2 = _PRICE_INT_RE.search(remaining)
            if m2:
                candidate = m2.group(1).replace(" ", "")
                # Only treat as price if it looks numeric and >2 digits
                if candidate.isdigit() and len(candidate) >= 3:
                    price_str = m2.group(1).strip()
                    remaining = remaining[: m2.start()].strip()

        # Step 2: split remaining into tokens
        tokens = remaining.split()
        if not tokens:
            continue

        code = ""
        article = ""
        name_parts = []

        idx = 0
        # Extract code (first purely numeric token)
        if has_code and idx < len(tokens) and tokens[idx].isdigit():
            code = tokens[idx]
            idx += 1
        else:
            code = str(auto_code)
            auto_code += 1

        # Extract article (next token, usually alphanumeric ID)
        if has_article and idx < len(tokens):
            article = tokens[idx]
            idx += 1

        # Rest = name
        name_parts = tokens[idx:]
        name = " ".join(name_parts) if name_parts else article or code

        # Build row
        row = [code]
        if has_article:
            row.append(article)
        row.append(name)
        if has_price:
            row.append(price_str)
        ws.append(row)


def _parse_user_addresses(text: str) -> list[dict]:
    """Parse user-provided addresses into city entries for pipeline.

    Accepts multiline text like:
        Челябинск, ул. Линейная, 98
        Казань, ул. Пушкина, 10
    """
    entries = []
    for i, line in enumerate(text.strip().split("\n"), 1):
        addr = line.strip()
        if not addr:
            continue
        # Extract city name for prefix
        city = addr.split(",")[0].strip()
        prefix = f"A{i}"
        entries.append({
            "name": city,
            "prefix": prefix,
            "addresses": [addr],
        })
    return entries


def _parse_user_managers(text: str) -> list[str]:
    """Parse user-provided manager names.

    Accepts formats:
        Дмитрий
        Адрес1 — Дмитрий
        Адрес1 - Дмитрий
    """
    managers = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Try to extract name after dash
        for sep in [" — ", " - ", "—", "-"]:
            if sep in line:
                name = line.split(sep)[-1].strip()
                if name:
                    managers.append(name)
                    break
        else:
            # Whole line is the manager name
            managers.append(line)
    return managers


def _run_pipeline_sync(
    pricelist_path: Path,
    output_path: Path,
    categories_config: dict,
    config_dir: Path,
    template_config: dict | None = None,
    project_code: str = "BT",
    progress_callback: Callable[[int, int], None] | None = None,
    *,
    user_phone: str | None = None,
    user_addresses: str | None = None,
    user_managers: str | None = None,
    user_title_info: str | None = None,
) -> dict[str, Any]:
    """Run pipeline synchronously (called via asyncio.to_thread).

    Args:
        user_phone: Contact phone from user (overrides config default).
        user_addresses: Multiline addresses from user (overrides cities.json).
        user_managers: Multiline manager names from user.
        user_title_info: Title format preferences from user.

    Returns dict with result statistics.
    """
    # Load standard configs
    columns_config = load_json_config(config_dir, "avito_columns.json")
    price_rules = load_json_config(config_dir, "price_rules.json")
    date_rules = load_json_config(config_dir, "date_rules.json")
    defaults = columns_config.get("defaults", {})

    # Determine addresses: user-provided or from config
    if user_addresses:
        all_cities = _parse_user_addresses(user_addresses)
    else:
        cities_config = load_json_config(config_dir, "cities.json")
        all_cities = cities_config.get("cities", [])

    if not all_cities:
        return {"error": "Нет адресов — укажите хотя бы один адрес"}

    # Parse manager names
    manager_list = _parse_user_managers(user_managers) if user_managers else []

    # Contact phone: user-provided or from config
    contact_phone = user_phone or defaults.get("ContactPhone", "")

    # Parse input
    input_rows = parse_xlsx(pricelist_path)
    if not input_rows:
        return {"error": "Нет данных во входном файле"}

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

    # Use company block from template if provided (but always use built-in prompt)
    custom_company_block = None
    if template_config:
        custom_company_block = template_config.get("company_block") or None

    # Generate descriptions + titles via LLM (always use built-in prompt from llm_describer)
    title_map: dict[str, str] = {}
    desc_map = generate_descriptions(
        input_rows,
        category_map,
        desc_cache,
        company_block=custom_company_block,
        title_info=user_title_info or "",
        title_map=title_map,
    )

    if progress_callback:
        progress_callback(len(desc_map), len(input_rows))

    # Build AvitoRow list
    avito_rows: list[AvitoRow] = []
    total_rows = len(input_rows) * len(all_cities)
    base_category = categories_config.get("root_category", "")

    global_idx = 0
    for city_idx, city_info in enumerate(all_cities):
        city_prefix = city_info["prefix"]
        city_addresses = city_info.get("addresses", [])
        address = city_addresses[0] if city_addresses else ""
        # Manager: match by index or use first/empty
        manager = ""
        if manager_list:
            manager = manager_list[city_idx] if city_idx < len(manager_list) else manager_list[-1]

        for seq, input_row in enumerate(input_rows, start=1):
            # Use LLM-generated title if available, fallback to rule-based
            cat_key = input_row.article or input_row.name
            llm_title = title_map.get(cat_key, "")
            title = llm_title if llm_title else generate_title(input_row.article, input_row.name)
            raw_price = input_row.price if input_row.price > 0 else input_row.cost
            price = calculate_price(raw_price, price_rules)
            listing_id = generate_listing_id(project_code, city_prefix, seq)
            row_id = generate_id(project_code, city_prefix, seq)
            date_begin = generate_date_begin(
                date_rules, index=global_idx, total=total_rows,
            )

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
                source_code=input_row.code,
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
                contact_phone=contact_phone,
                manager_name=manager,
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
    *,
    user_phone: str | None = None,
    user_addresses: str | None = None,
    user_managers: str | None = None,
    user_title_info: str | None = None,
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
        user_phone=user_phone,
        user_addresses=user_addresses,
        user_managers=user_managers,
        user_title_info=user_title_info,
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
