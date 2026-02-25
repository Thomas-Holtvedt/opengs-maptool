import json
import csv
from pathlib import Path
from typing import Any


def export_to_json(data: dict | list, file_path: Path | str) -> None:
    """Export data to JSON format.
    
    Args:
        data: Dictionary or list to export (must be JSON-serializable)
        file_path: Path where the JSON file will be saved
    """
    file_path = Path(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def export_to_csv(data: list[dict[str, Any]], file_path: Path | str) -> None:
    """Export list of dictionaries to CSV format.
    
    Args:
        data: List of dictionaries where each dict represents a row
        file_path: Path where the CSV file will be saved
        
    Raises:
        ValueError: If data is empty or not a list of dicts
        TypeError: If data contains non-serializable values
    """
    if not data:
        raise ValueError("Cannot export empty data to CSV")
    
    if not isinstance(data, list):
        raise TypeError(f"Expected list[dict], got {type(data).__name__}")
    
    # Get fieldnames from first row
    fieldnames = list(data[0].keys())
    
    with open(Path(file_path), 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
