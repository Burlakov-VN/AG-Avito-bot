"""Validate Avito autoload rows and generate reports."""

import csv
import json
import logging
from pathlib import Path

from avito_autoload.models.avito_row import AvitoRow

logger = logging.getLogger(__name__)


def validate_rows(rows: list[AvitoRow], columns_config: dict) -> list[dict]:
    """Validate rows against Avito requirements.

    Returns list of issues: {row_index, field, level, message}.
    Levels: critical, warning, info.
    """
    required = set(columns_config.get("required", []))
    field_to_col = {
        "id": "Id",
        "listing_id": "ListingId",
        "category": "Category",
        "ad_type": "AdType",
        "title": "Title",
        "price": "Price",
        "contact_phone": "ContactPhone",
        "address": "Address",
    }

    issues: list[dict] = []
    seen_listing_ids: set[str] = set()

    for idx, row in enumerate(rows):
        row_data = row.model_dump()

        # Check required fields
        for field, col_name in field_to_col.items():
            if col_name in required:
                value = row_data.get(field, "")
                if not value or (isinstance(value, str) and not value.strip()):
                    issues.append({
                        "row_index": idx,
                        "field": col_name,
                        "level": "critical",
                        "message": f"Required field '{col_name}' is empty",
                    })

        # Title length check (Avito max 50 chars)
        if len(row.title) > 50:
            issues.append({
                "row_index": idx,
                "field": "Title",
                "level": "info",
                "message": f"Title exceeds 50 chars ({len(row.title)})",
            })

        # Price sanity
        if row.price <= 0:
            issues.append({
                "row_index": idx,
                "field": "Price",
                "level": "critical",
                "message": f"Price must be positive, got {row.price}",
            })

        # Duplicate ListingId
        if row.listing_id in seen_listing_ids:
            issues.append({
                "row_index": idx,
                "field": "ListingId",
                "level": "critical",
                "message": f"Duplicate ListingId: {row.listing_id}",
            })
        seen_listing_ids.add(row.listing_id)

        # Conditional required fields based on category hierarchy
        if row.goods_type == "Запчасти":
            if not row.product_type:
                issues.append({
                    "row_index": idx,
                    "field": "ProductType",
                    "level": "warning",
                    "message": "ProductType required when GoodsType='Запчасти'",
                })
            if not row.spare_part_type:
                issues.append({
                    "row_index": idx,
                    "field": "SparePartType",
                    "level": "warning",
                    "message": "SparePartType required when GoodsType='Запчасти'",
                })

            # Sub-type fields for "Для автомобилей"
            if row.product_type == "Для автомобилей":
                if row.spare_part_type == "Двигатель" and not row.engine_spare_part_type:
                    issues.append({
                        "row_index": idx,
                        "field": "EngineSparePartType",
                        "level": "warning",
                        "message": "EngineSparePartType required when SparePartType='Двигатель'",
                    })
                if row.spare_part_type == "Трансмиссия и привод" and not row.transmission_spare_part_type:
                    issues.append({
                        "row_index": idx,
                        "field": "TransmissionSparePartType",
                        "level": "warning",
                        "message": "TransmissionSparePartType required when SparePartType='Трансмиссия и привод'",
                    })

            # Sub-type fields for "Для грузовиков и спецтехники"
            if row.product_type == "Для грузовиков и спецтехники":
                if not row.technic_spare_part_type:
                    issues.append({
                        "row_index": idx,
                        "field": "TechnicSparePartType",
                        "level": "warning",
                        "message": "TechnicSparePartType required when ProductType='Для грузовиков и спецтехники'",
                    })

    logger.info("Validation: %d issues found in %d rows", len(issues), len(rows))
    return issues


def export_report_json(issues: list[dict], output_path: Path) -> Path:
    """Write validation report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)
    logger.info("Validation report (JSON): %s", output_path)
    return output_path


def export_report_csv(issues: list[dict], output_path: Path) -> Path:
    """Write validation report as CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["row_index", "field", "level", "message"]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)
    logger.info("Validation report (CSV): %s", output_path)
    return output_path
