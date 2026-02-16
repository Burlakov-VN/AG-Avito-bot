"""Pydantic model for a single Avito autoload row."""

from pydantic import BaseModel


class AvitoRow(BaseModel):
    """Одна строка файла автозагрузки Avito."""

    id: str
    listing_id: str
    category: str = ""
    goods_type: str = ""
    product_type: str = ""
    spare_part_type: str = ""
    engine_spare_part_type: str = ""
    body_spare_part_type: str = ""
    transmission_spare_part_type: str = ""
    technic_spare_part_type: str = ""
    ad_type: str = "Товар приобретён на продажу"
    title: str
    description: str = ""
    price: int
    price_type: str = "Точная"
    image_urls: str = ""
    video_url: str = ""
    condition: str = "Новое"
    availability: str = "В наличии"
    delivery: str = "Да"
    date_begin: str = ""
    contact_phone: str = ""
    manager_name: str = ""
    contact_method: str = "По телефону и в сообщениях"
    internet_calls: str = "Да"
    address: str = ""


class InputRow(BaseModel):
    """Одна строка входного прайс-файла."""

    code: str
    article: str = ""
    name: str = ""
    quantity: int = 0
    cost: float = 0.0
    price: float = 0.0
