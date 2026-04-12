from PyQt6.QtWidgets import QFileDialog
from PIL import Image
import json
import csv
import yaml
import xml.etree.ElementTree as ET
from xml.dom import minidom


def export_image(parent_layout, image, text):
    if image:
        try:
            path = _pick_file_image(parent_layout, text)
            if not path:
                return
            
            # Remove the alpha channel for JPEG image export
            ext = path.lower().rsplit('.', 1)[-1]
            if ext in ("jpg", "jpeg"):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background

            image.save(path)

        except Exception as error:
            print(f"Error saving image: {error}")


def export_territory_definitions(main_layout):
    territory_data = getattr(main_layout, "territory_data", None)
    if not territory_data:
        print("No territory data to export.")
        return

    path, fmt = _pick_file_data(main_layout, "Export Territory Definitions")
    if not path:
        return

    if fmt in ("json", "yaml", "xml"):
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "territory_type": d["territory_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(float(d["x"]), 2),
                "y": round(float(d["y"]), 2),
            }

        if fmt == "json":
            _write_json(path, data)
        elif fmt == "yaml":
            _write_yaml(path, data)
        elif fmt == "xml":
            root = ET.Element("territories")

            for territory_id, info in data.items():
                territory_element = ET.SubElement(root, "territory")
                territory_element.set("id", str(territory_id))
                
                for key, value in info.items():
                    element = ET.SubElement(territory_element, key)
                    element.text = str(value)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

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

    path, fmt = _pick_file_data(main_layout, "Export Territory History")
    if not path:
        return

    if fmt in ("json", "yaml", "xml"):
        data = {}
        for d in territory_data:
            data[d["territory_id"]] = {
                "provinces": d.get("province_ids", []),
            }
        if fmt == "json":
            _write_json(path, data)
        elif fmt == "yaml":
            _write_yaml(path, data)
        elif fmt == "xml":
            root = ET.Element("territories")

            for territory_id, info in data.items():
                territory_element = ET.SubElement(root, "territory")
                territory_element.set("id", str(territory_id))
                
                provinces_element = ET.SubElement(territory_element, "provinces")

                for province_id in info.get("provinces", []):
                    province_element = ET.SubElement(provinces_element, "province")
                    province_element.text = str(province_id)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

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

    path, fmt = _pick_file_data(main_layout, "Export Province Definitions")
    if not path:
        return

    has_terrain = any("province_terrain" in d for d in province_data)

    if fmt in ("json", "yaml", "xml"):
        data = {}
        for d in province_data:
            entry = {
                "province_type": d["province_type"],
                "R": d["R"], "G": d["G"], "B": d["B"],
                "x": round(float(d["x"]), 2),
                "y": round(float(d["y"]), 2),
            }
            if has_terrain:
                entry["province_terrain"] = d.get("province_terrain", "unknown")
            data[d["province_id"]] = entry
        if fmt == "json":
            _write_json(path, data)
        elif fmt == "yaml":
            _write_yaml(path, data)
        elif fmt == "xml":
            root = ET.Element("provinces")

            for province_id, info in data.items():
                province_element = ET.SubElement(root, "province")
                province_element.set("id", str(province_id))

                for key, value in info.items():
                    element = ET.SubElement(province_element, key)
                    element.text = str(value)

            rough_xml = ET.tostring(root, encoding="unicode")
            pretty_xml = minidom.parseString(rough_xml).toprettyxml(indent="    ")

            with open(path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)

    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            header = ["id", "province_type", "R", "G", "B", "x", "y"]
            if has_terrain:
                header.append("province_terrain")
            w.writerow(header)
            for d in province_data:
                row = [d["province_id"], d["province_type"],
                       d["R"], d["G"], d["B"],
                       round(d["x"], 2), round(d["y"], 2)]
                if has_terrain:
                    row.append(d.get("province_terrain", "unknown"))
                w.writerow(row)


def _pick_file_image(parent, title):
    """Open save dialog with image format filters. Returns path (with valid file extension) or None"""
    filters = (
        "PNG Files (*.png);;" \
        "JPEG Files (*.jpg *.jpeg);;" \
        "BMP Files (*.bmp);;" \
        "GIF Files (*.gif);;"
        "TIFF Files (*.tiff *.tif);;"
        "WebP Files (*.webp);;" \
        "All Files (*.*)"
    )
    
    path, selected_filter = QFileDialog.getSaveFileName(parent, title, "", filters)
    if not path:
        return None
    
    if not path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp")):
        if "png" in selected_filter.lower():
            path += ".png"
        elif "jpeg" in selected_filter.lower(): # or .jpg
            path += ".jpg"
        elif "bmp" in selected_filter.lower():
            path += ".bmp"
        elif "gif" in selected_filter.lower():
            path += ".gif"
        elif "tiff" in selected_filter.lower(): # or .tif
            path += ".tiff"
        elif "webp" in selected_filter.lower():
            path += ".webp"
        else: # default format
            path += ".png"

    return path


def _pick_file_data(parent, title):
    """Open save dialog with data format filters. Returns (path, format) or (None, None)."""
    filters = (
        "JSON Files (*.json);;" \
        "CSV Files (*.csv);;" \
        "YAML Files (*.yaml);;" \
        "XML Files (*.xml)"
    )
    
    path, selected_filter = QFileDialog.getSaveFileName(parent, title, "", filters)
    if not path:
        return None, None

    # Determine format from extension, fall back to selected filter
    if path.lower().endswith(".json"):
        fmt = "json"
    elif path.lower().endswith(".csv"):
        fmt = "csv"
    elif path.lower().endswith(".yaml"):
        fmt = "yaml"
    elif path.lower().endswith(".xml"):
        fmt = "xml"
    elif "json" in selected_filter.lower():
        fmt = "json"
        path += ".json"
    elif "yaml" in selected_filter.lower():
        fmt = "yaml"
        path += ".yaml"
    elif "xml" in selected_filter.lower():
        fmt = "xml"
        path += ".xml"
    else:
        fmt = "csv"
        path += ".csv"

    return path, fmt


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
