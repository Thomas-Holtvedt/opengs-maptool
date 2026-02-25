import csv
import dataclasses
import json
from pathlib import Path
from typing import Any

from opengs_maptool.logic.utils import RegionMetadata


class RegionSerializer(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, RegionMetadata):
            return obj.to_json_dict()
        return super().default(obj)


class RegionDeserializer(json.JSONDecoder):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj: dict) -> RegionMetadata | dict:
        try:
            return RegionMetadata.from_json_dict(obj)
        except TypeError:
            return obj


def export_to_json(data: list[RegionMetadata] | Any, file_path: Path | str, **kwargs) -> None:
    """
    Export region data or any JSON-serializable data.

    Args:
        data: List of RegionMetadata objects to export
        file_path: Path where the JSON file will be saved
    """
    file_path = Path(file_path)
    file_path.write_text(json.dumps(data, cls=RegionSerializer, indent=2, **kwargs))


def export_to_csv(data: list[RegionMetadata], file_path: Path | str) -> None:
    """
    Export region data to CSV format.

    Args:
        data: List of RegionMetadata objects where each object represents a region
        file_path: Path where the CSV file will be saved

    Raises:
        ValueError: If data is empty or not a list of RegionMetadata
        TypeError: If data contains non-serializable values
    """
    if not data:
        raise ValueError("Cannot export empty data to CSV")
    
    if not isinstance(data, list):
        raise TypeError(f"Expected list[RegionMetadata], got {type(data).__name__}")
    
    raw_data = [region.to_csv_dict() for region in data]
    fieldnames = list(raw_data[0].keys())
    with open(Path(file_path), 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(raw_data)


def import_from_json(file_path: Path | str) -> list[RegionMetadata] | Any:
    """
    Import region data from a JSON file.

    Args:
        file_path: Path to the JSON file to import
    """
    file_path = Path(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f, cls=RegionDeserializer)


def import_from_csv(file_path: Path | str) -> list[RegionMetadata]:
    """
    Import region data from a CSV file and return a list of RegionMetadata objects.

    Args:
        file_path: Path to the CSV file to import
    """
    file_path = Path(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [RegionMetadata.from_csv_dict(row) for row in reader]