"""Fetch category tree and field definitions from Avito API."""

import json
import logging
from pathlib import Path

import httpx

from avito_autoload.avito_api.auth import AvitoAuth

logger = logging.getLogger(__name__)

BASE_URL = "https://api.avito.ru"
TREE_ENDPOINT = "/autoload/v1/user-docs/tree"
FIELDS_ENDPOINT = "/autoload/v1/user-docs/node/{slug}/fields"

# Local cache for API responses
DEFAULT_CACHE_DIR = Path("cache")


class AvitoCategoryFetcher:
    """Fetches and caches Avito category tree and field definitions."""

    def __init__(self, auth: AvitoAuth, cache_dir: Path = DEFAULT_CACHE_DIR):
        self.auth = auth
        self.cache_dir = cache_dir
        self._client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    def _request(self, endpoint: str) -> dict | list:
        """Make authenticated GET request, retry once on 403 (expired token)."""
        headers = self.auth.auth_headers()
        response = self._client.get(endpoint, headers=headers)

        # Avito returns 403 (not 401) for expired tokens
        if response.status_code == 403:
            logger.warning("Got 403, refreshing token and retrying")
            self.auth._access_token = ""  # Force refresh
            headers = self.auth.auth_headers()
            response = self._client.get(endpoint, headers=headers)

        response.raise_for_status()
        return response.json()

    def fetch_tree(self) -> list[dict]:
        """Fetch the full category tree from Avito API.

        Returns list of top-level category nodes, each with nested children.
        """
        logger.info("Fetching Avito category tree")
        data = self._request(TREE_ENDPOINT)
        if isinstance(data, dict):
            return data.get("categories", data.get("data", data.get("result", [])))
        return data

    def fetch_fields(self, node_slug: str) -> list[dict]:
        """Fetch field definitions for a specific category node.

        Args:
            node_slug: Category node slug (e.g. 'zapchasti-i-aksessuary').

        Returns list of field definitions with name, type, required, options.
        """
        endpoint = FIELDS_ENDPOINT.format(slug=node_slug)
        logger.info("Fetching fields for category: %s", node_slug)
        data = self._request(endpoint)
        if isinstance(data, dict):
            return data.get("fields", data.get("data", []))
        return data

    def fetch_and_cache_tree(self) -> list[dict]:
        """Fetch tree and save to local cache file."""
        tree = self.fetch_tree()
        cache_file = self.cache_dir / "avito_tree.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)
        logger.info("Category tree cached to %s", cache_file)
        return tree

    def fetch_and_cache_fields(self, node_slug: str) -> list[dict]:
        """Fetch fields for a node and save to local cache file."""
        fields = self.fetch_fields(node_slug)
        cache_file = self.cache_dir / f"avito_fields_{node_slug}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(fields, f, ensure_ascii=False, indent=2)
        logger.info("Fields for '%s' cached to %s", node_slug, cache_file)
        return fields

    def load_cached_tree(self) -> list[dict] | None:
        """Load tree from local cache if available."""
        cache_file = self.cache_dir / "avito_tree.json"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        return None

    def load_cached_fields(self, node_slug: str) -> list[dict] | None:
        """Load fields from local cache if available."""
        cache_file = self.cache_dir / f"avito_fields_{node_slug}.json"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def find_node_by_name(tree: list[dict], name: str) -> dict | None:
    """Recursively find a node in the category tree by name."""
    for node in tree:
        if node.get("name") == name:
            return node
        # API uses "nested" for children, but support "children" too
        children = node.get("nested", node.get("children", []))
        if children:
            found = find_node_by_name(children, name)
            if found:
                return found
    return None


def extract_field_options(fields: list[dict], field_name: str) -> list[str]:
    """Extract allowed option values for a specific field.

    Supports both API format (tag + content[0].values) and simple format
    (name + options) for backward compatibility with tests.
    """
    for field in fields:
        # API format: field identified by "tag"
        if field.get("tag") == field_name:
            content = field.get("content", [])
            if content and isinstance(content, list):
                values = content[0].get("values", [])
                if values:
                    return [v.get("value", "") for v in values if isinstance(v, dict)]
            # Fallback to options key
            options = field.get("options", [])
            if isinstance(options, list):
                return [
                    opt if isinstance(opt, str) else opt.get("label", opt.get("value", ""))
                    for opt in options
                ]
        # Simple format: field identified by "name" or "id"
        if field.get("name") == field_name or field.get("id") == field_name:
            options = field.get("options", [])
            if isinstance(options, list):
                return [
                    opt if isinstance(opt, str) else opt.get("label", opt.get("value", ""))
                    for opt in options
                ]
    return []


def _collect_leaves(node: dict) -> list[dict]:
    """Collect all leaf nodes from a category subtree."""
    nested = node.get("nested", node.get("children", []))
    if not nested:
        return [node]
    leaves = []
    for child in nested:
        leaves.extend(_collect_leaves(child))
    return leaves


def _get_children(node: dict) -> list[dict]:
    """Get children of a node (supports both 'nested' and 'children' keys)."""
    return node.get("nested", node.get("children", []))


def _build_spare_parts_section(
    fetcher: AvitoCategoryFetcher,
    zapchasti_node: dict,
) -> dict:
    """Build the 'Запчасти' section with product_types and sub-type fields."""
    # Known sub-type field mappings (SparePartType → API field name)
    sub_type_fields = {
        "Двигатель": "EngineSparePartType",
        "Кузов": "BodySparePartType",
        "Трансмиссия и привод": "TransmissionSparePartType",
    }

    product_types = []
    for pt_node in _get_children(zapchasti_node):
        pt_name = pt_node.get("name", "")
        pt_slug = pt_node.get("slug", "")
        leaves = _collect_leaves(pt_node)
        spare_part_types = [leaf["name"] for leaf in leaves if leaf.get("name")]

        pt_entry: dict = {
            "name": pt_name,
            "slug": pt_slug,
            "spare_part_types": spare_part_types,
        }

        # Fetch sub-type fields for known categories
        sub_types: dict[str, dict] = {}

        # For "Для грузовиков и спецтехники": every leaf has TechnicSparePartType
        is_technic = pt_name == "Для грузовиков и спецтехники"

        for spt_name in spare_part_types:
            # Determine which field to fetch
            if is_technic:
                field_name = "TechnicSparePartType"
            elif spt_name in sub_type_fields:
                field_name = sub_type_fields[spt_name]
            else:
                continue

            # Find slug for this spare part type
            spt_leaf = next(
                (l for l in leaves if l.get("name") == spt_name), None
            )
            if not spt_leaf:
                continue
            slug = spt_leaf.get("slug", "")
            if not slug:
                continue
            try:
                fields = fetcher.fetch_and_cache_fields(slug)
                values = extract_field_options(fields, field_name)
                if values:
                    sub_types[spt_name] = {"field": field_name, "values": values}
            except Exception:
                logger.warning("Failed to fetch fields for %s (%s)", spt_name, slug)

        if sub_types:
            pt_entry["sub_types"] = sub_types

        product_types.append(pt_entry)
        logger.info(
            "  %s: %d categories, %d sub-types",
            pt_name, len(spare_part_types), len(sub_types),
        )

    return {
        "goods_type": "Запчасти",
        "product_types": product_types,
    }


def _build_generic_section(node: dict) -> dict:
    """Build a section for a non-'Запчасти' GoodsType (Масла, Шины, etc.)."""
    name = node.get("name", "")
    children = _get_children(node)

    if not children:
        # Leaf node (e.g. GPS-навигаторы, Экипировка, Инструменты)
        return {
            "goods_type": name,
            "categories": [name],
            "slugs": {name: node.get("slug", "")},
        }

    leaves = _collect_leaves(node)
    categories = [leaf["name"] for leaf in leaves if leaf.get("name")]
    slugs = {
        leaf["name"]: leaf.get("slug", "")
        for leaf in leaves
        if leaf.get("name")
    }

    return {
        "goods_type": name,
        "categories": categories,
        "slugs": slugs,
    }


def build_categories_from_api(
    fetcher: AvitoCategoryFetcher,
    category_slug: str = "",
) -> dict:
    """Fetch category tree and fields, build avito_categories.json structure.

    Collects ALL sections under 'Запчасти и аксессуары':
    Масла, Шины, Аксессуары, Запчасти, and others.

    For 'Запчасти' section, additionally fetches sub-type fields
    (EngineSparePartType, TransmissionSparePartType, etc.).

    Returns dict with root_category and sections list.
    """
    tree = fetcher.fetch_and_cache_tree()

    # Navigate: Транспорт → Запчасти и аксессуары
    path = ["Транспорт", "Запчасти и аксессуары"]
    current_nodes = tree
    root_node = None
    for step in path:
        root_node = find_node_by_name(current_nodes, step)
        if not root_node:
            logger.warning("Could not find '%s' in category tree path", step)
            return {"root_category": "", "sections": []}
        current_nodes = _get_children(root_node)

    sections = []
    goods_type_nodes = _get_children(root_node)
    logger.info("Found %d GoodsType sections", len(goods_type_nodes))

    for gt_node in goods_type_nodes:
        gt_name = gt_node.get("name", "")
        if gt_name == "Запчасти":
            section = _build_spare_parts_section(fetcher, gt_node)
        else:
            section = _build_generic_section(gt_node)
        sections.append(section)
        logger.info("Section '%s': %s", gt_name, section.get("goods_type"))

    return {
        "root_category": "Запчасти и аксессуары",
        "sections": sections,
    }
