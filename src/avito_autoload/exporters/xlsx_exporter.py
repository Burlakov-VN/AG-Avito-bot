"""Export AvitoRow list to Avito autoload xlsx template."""

import logging
from pathlib import Path

from openpyxl import Workbook

from avito_autoload.models.avito_row import AvitoRow

logger = logging.getLogger(__name__)

# AvitoRow field -> Avito column header
FIELD_TO_COLUMN: dict[str, str] = {
    "id": "Id",
    "listing_id": "ListingId",
    "category": "Category",
    "goods_type": "GoodsType",
    "product_type": "ProductType",
    "spare_part_type": "SparePartType",
    "engine_spare_part_type": "EngineSparePartType",
    "body_spare_part_type": "BodySparePartType",
    "transmission_spare_part_type": "TransmissionSparePartType",
    "technic_spare_part_type": "TechnicSparePartType",
    "ad_type": "AdType",
    "title": "Title",
    "description": "Description",
    "price": "Price",
    "price_type": "PriceType",
    "image_urls": "ImageUrls",
    "video_url": "VideoURL",
    "condition": "Condition",
    "availability": "Availability",
    "delivery": "Delivery",
    "date_begin": "DateBegin",
    "contact_phone": "ContactPhone",
    "manager_name": "ManagerName",
    "contact_method": "ContactMethod",
    "internet_calls": "InternetCalls",
    "address": "Address",
}


def export_to_xlsx(rows: list[AvitoRow], output_path: Path, columns_config: dict) -> Path:
    """Write rows to xlsx file matching Avito template format.

    Returns path to the created file.
    """
    columns = columns_config.get("columns", list(FIELD_TO_COLUMN.values()))

    # Build reverse mapping: column name -> field name
    col_to_field = {v: k for k, v in FIELD_TO_COLUMN.items()}

    wb = Workbook()
    ws = wb.active
    ws.title = "Autoload"

    # Header row
    ws.append(columns)

    # Data rows
    for row in rows:
        row_data = row.model_dump()
        values = []
        for col_name in columns:
            field = col_to_field.get(col_name)
            if field and field in row_data:
                values.append(row_data[field])
            else:
                values.append("")
        ws.append(values)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    wb.close()

    logger.info("Exported %d rows to %s", len(rows), output_path)
    return output_path
