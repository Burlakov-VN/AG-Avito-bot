"""Generate ListingId and Id for Avito rows."""


def generate_listing_id(project_code: str, city_prefix: str, seq: int) -> str:
    """Generate ListingId in format: {ProjectCode}_{CityPrefix}_{Seq:06d}.

    Example: KG_IMChel_000001
    """
    return f"{project_code}_{city_prefix}_{seq:06d}"


def generate_id(project_code: str, city_prefix: str, seq: int) -> str:
    """Generate unique row Id (same format as ListingId)."""
    return generate_listing_id(project_code, city_prefix, seq)
