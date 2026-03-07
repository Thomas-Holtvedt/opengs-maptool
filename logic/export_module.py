import json
from PyQt6.QtWidgets import QFileDialog
import csv


def export_image(parent_layout, image, text):
    if image:
        try:
            path, _ = QFileDialog.getSaveFileName(
                parent_layout, text, "", "PNG Files (*.png)")
            if not path:
                return
            if not path.lower().endswith(".png"):
                path += ".png"
            image.save(path)

        except Exception as error:
            print(f"Error saving image: {error}")


def export_territory_definitions(main_layout):
    territory_data = getattr(main_layout, "territory_data", None)
    if not territory_data:
        print("No territory data to export.")
        return

    path, fmt = _pick_file(main_layout, "Export Territory Definitions")
    if not path:
        return

    if fmt == "json":
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "territory_type": d["territory_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(d["x"], 2), "y": round(d["y"], 2),
            }
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["id", "territory_type", "R", "G", "B", "x", "y"])
            for d in territory_data:
                w.writerow([d["territory_id"], d["territory_type"],
                            d["R"], d["G"], d["B"],
                            round(d["x"], 2), round(d["y"], 2)])


def export_territory_history(main_layout):
    territory_data = getattr(main_layout, "territory_data", None)
    if not territory_data:
        print("No territory data to export.")
        return

    path, fmt = _pick_file(main_layout, "Export Territory History")
    if not path:
        return

    if fmt == "json":
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "provinces": d.get("province_ids", []),
            }
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["id", "provinces"])
            for d in territory_data:
                provinces = ",".join(d.get("province_ids", []))
                w.writerow([d["territory_id"], provinces])


def export_province_definitions(main_layout):
    province_data = getattr(main_layout, "province_data", None)
    if not province_data:
        print("No province data to export.")
        return

    path, fmt = _pick_file(main_layout, "Export Province Definitions")
    if not path:
        return

    if fmt == "json":
        data = {}
        for d in province_data:
            data[d["province_id"]] = {
                "province_type": d["province_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(d["x"], 2), "y": round(d["y"], 2),
            }
        _write_json(path, data)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["id", "province_type", "R", "G", "B", "x", "y"])
            for d in province_data:
                w.writerow([d["province_id"], d["province_type"],
                            d["R"], d["G"], d["B"],
                            round(d["x"], 2), round(d["y"], 2)])



def _pick_file(parent, title):
    """Open save dialog with JSON/CSV filter. Returns (path, format) or (None, None)."""
    path, selected_filter = QFileDialog.getSaveFileName(
        parent, title, "", "JSON Files (*.json);;CSV Files (*.csv)")
    if not path:
        return None, None

    # Determine format from extension, fall back to selected filter
    if path.lower().endswith(".json"):
        fmt = "json"
    elif path.lower().endswith(".csv"):
        fmt = "csv"
    elif "json" in selected_filter.lower():
        fmt = "json"
        path += ".json"
    else:
        fmt = "csv"
        path += ".csv"

    return path, fmt


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
