from __future__ import annotations
from typing import Any, TypeAlias

from dataclasses import dataclass
from enum import Enum
from PIL import Image
import numpy as np
from numpy.typing import NDArray

# Main tab images
LandImage: TypeAlias = Image.Image
BoundaryImage: TypeAlias = Image.Image
DensityImage: TypeAlias = Image.Image
TerrainImage: TypeAlias = Image.Image
TerritoryImage: TypeAlias = Image.Image
ProvinceImage: TypeAlias = Image.Image

# Intermediate data structures
BooleanMaskMap: TypeAlias = NDArray[np.bool_]
RegionIdToPixelCounts: TypeAlias = dict[int, int]
RegionPixelMap: TypeAlias = NDArray[np.int32]
ColorPixelMap: TypeAlias = NDArray[np.uint8]
JitterSeedsArray: TypeAlias = NDArray[np.float32] # not a map, but an array actually

ColorTuple: TypeAlias = tuple[int, int, int]
IntCoordinate: TypeAlias = tuple[int, int]

class RegionLevel(Enum):
    TERRITORY = "territory"
    PROVINCE = "province"

class RegionType(Enum):
    LAND = "land"
    OCEAN = "ocean"
    LAKE = "lake"

@dataclass
class RegionMetadata:
    # For both territories & provinces
    region_level: RegionLevel
    R: int
    G: int
    B: int
    x: float
    y: float
    _pmap_index: int
    territory_id: str | None # used both as territory id & province's parent id

    # Only for provinces
    province_id: str | None
    province_type: RegionType | None
    province_terrain: str | None

    # Only for territories
    territory_type: RegionType | None
    province_ids: list[str] | None

    TERRITORY_JSON_KEYS: tuple[str, ...] = ("territory_type", "R", "G", "B", "x", "y")

    def serialize_territory_json(self) -> dict[str, Any]:
        """
        Serialize the territory metadata to a JSON-compatible dictionary.
        Keys: territory_type, R, G, B, x, y
        """
        return {
            "territory_type": self.territory_type.value if self.territory_type else None,
            "R": self.R,
            "G": self.G,
            "B": self.B,
            "x": round(float(self.x), 2),
            "y": round(float(self.y), 2),
        }

    PROVINCE_JSON_KEYS_WITHOUT_TERRAIN: tuple[str, ...] = ("province_type", "R", "G", "B", "x", "y")
    PROVINCE_JSON_KEYS_WITH_TERRAIN: tuple[str, ...] = (*PROVINCE_JSON_KEYS_WITHOUT_TERRAIN, "province_terrain")

    def serialize_province_json(self, include_terrain: bool) -> dict[str, Any]:
        """
        Serialize the province metadata to a JSON-compatible dictionary.
        Keys: province_type, R, G, B, x, y, province_terrain (if include_terrain is True)
        """
        data = {
            "province_type": self.province_type.value if self.province_type else None,
            "R": self.R,
            "G": self.G,
            "B": self.B,
            "x": round(float(self.x), 2),
            "y": round(float(self.y), 2),
            "province_terrain": self.province_terrain,
        }
        if include_terrain:
            data["province_terrain"] = self.province_terrain
        return data

    def serialize_full_json(self) -> dict[str, Any]:
        """
        Serialize the full metadata to a JSON-compatible dictionary for project saves.
        Includes all properties, both for territories and provinces.
        """
        return {
            "region_level": self.region_level.value,
            "R": self.R,
            "G": self.G,
            "B": self.B,
            "x": round(float(self.x), 2),
            "y": round(float(self.y), 2),
            "_pmap_index": self._pmap_index,
            "territory_id": self.territory_id,
            "province_id": self.province_id,
            "province_type": self.province_type.value if self.province_type else None,
            "province_terrain": self.province_terrain,
            "territory_type": self.territory_type.value if self.territory_type else None,
            "province_ids": self.province_ids,
        }

    @classmethod
    def deserialize_from_full_json[CT](cls: CT, data: dict[str, Any]) -> CT:
        """
        Deserialize the full metadata from a JSON-compatible dictionary.
        Expects all keys as produced by serialize_full_json.
        Types are not manually validated for standard keys.

        Raises:
            ValueError: If deserialization fails due to missing or invalid keys.
        """
        try: # new key, therefore safeguard for old saves
            region_level = RegionLevel(data.get("region_level"))
        except ValueError:
            if data.get("province_id") is not None: # seems to be a province
                region_level = RegionLevel.PROVINCE
            else:
                region_level = RegionLevel.TERRITORY

        # Too much work to validate all keys exist and are the right type :)
        # TODO: Add validation for required keys and types if needed

        try:
            return cls(
                region_level=region_level,
                R=int(data["R"]),
                G=int(data["G"]),
                B=int(data["B"]),
                x=float(data["x"]),
                y=float(data["y"]),
                _pmap_index=int(data["_pmap_index"]),
                territory_id=data.get("territory_id", None),
                province_id=data.get("province_id", None),
                province_type=RegionType(data["province_type"]) if data.get("province_type") else None,
                province_terrain=data.get("province_terrain", None),
                territory_type=RegionType(data["territory_type"]) if data.get("territory_type") else None,
                province_ids=data.get("province_ids", None),
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Failed to deserialize territory or province from full JSON data: {e}") from e

@dataclass
class Masks:
    boundary_mask: BooleanMaskMap
    land_mask: BooleanMaskMap
    sea_mask: BooleanMaskMap
    lake_mask: BooleanMaskMap
    land_fill: BooleanMaskMap
    land_border: BooleanMaskMap
    sea_fill: BooleanMaskMap
    sea_border: BooleanMaskMap
    map_h: int
    map_w: int

    def serialize_to_json(self) -> dict[str, Any]:
        return {
            "boundary_mask": self.boundary_mask,
            "land_mask": self.land_mask,
            "sea_mask": self.sea_mask,
            "lake_mask": self.lake_mask,
            "land_fill": self.land_fill,
            "land_border": self.land_border,
            "sea_fill": self.sea_fill,
            "sea_border": self.sea_border,
            "map_h": self.map_h,
            "map_w": self.map_w,
        }

    @classmethod
    def deserialize_from_json[CT](cls: CT, data: dict[str, Any]) -> CT:
        return cls(
            boundary_mask=data["boundary_mask"],
            land_mask=data["land_mask"],
            sea_mask=data["sea_mask"],
            lake_mask=data["lake_mask"],
            land_fill=data["land_fill"],
            land_border=data["land_border"],
            sea_fill=data["sea_fill"],
            sea_border=data["sea_border"],
            map_h=data["map_h"],
            map_w=data["map_w"],
        )
