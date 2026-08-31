from io import BytesIO
import json
from typing import Any
import numpy as np
from opengs_maptool.models.project import Project
import opengs_maptool.config as config
import opengs_maptool.logic.datastructure as ds
from PIL import Image
import zipfile

class ProjectService:
    """Create, load, and save Project instances using the GSMAP/ZIP format."""

    def create(self) -> Project:
        """
        Create a new empty project.
        """
        project = Project()
        return project


    def load(self, path: str) -> Project:
        """
        Load a project saved to disk (GSMAP file or ZIP)

        @param path: The file path
        """
        with zipfile.ZipFile(path, "r") as zip:
            details = json.loads(zip.read("project.json"))

            # Load project's main details
            project = Project(
                name=details['name'],
                editor_version=details['editor_version'],
                description=details.get('description'),
                author=details.get('author')
            )
            project.file_path = path

            # Load map images
            project.land_image = self._load_image_from_zip(zip, "land.png")
            project.boundary_image = self._load_image_from_zip(zip, "boundary.png")
            project.density_image = self._load_image_from_zip(zip, "density.png")
            project.terrain_image = self._load_image_from_zip(zip, "terrain.png")
            project.territory_image = self._load_image_from_zip(zip, "territory.png")
            project.province_image = self._load_image_from_zip(zip, "province.png")

            # Load data
            territory_data_json = self._load_data_from_zip(zip, "territory_data.json")
            province_data_json = self._load_data_from_zip(zip, "province_data.json")
            
            if territory_data_json is not None:
                project.territory_data = [ds.RegionMetadata.deserialize_from_full_json(m) for m in territory_data_json]
            else:
                project.territory_data = None
            
            if province_data_json is not None:
                project.province_data = [ds.RegionMetadata.deserialize_from_full_json(m) for m in province_data_json]
            else:
                project.province_data = None

            # Load metadata
            project.territory_pmap = self._load_territory_pmap_from_zip(zip)
            project.cached_masks = self._load_cached_masks_from_zip(zip)

            # Load settings (if exists)
            if zipfile.Path(zip, "settings.json").exists():
                settings = json.loads(zip.read("settings.json"))

                if settings.get("ocean_color"):
                    project.ocean_color = tuple(settings.get("ocean_color"))

                if settings.get("lake_color"):
                    project.lake_color = tuple(settings.get("lake_color"))

            return project


    def save(self, project: Project, path: str) -> None:
        """
        Save a project to disk (GSMAP file or ZIP)

        @param path: The file path
        """
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zip:
            project.file_path = path

            # Save the project's main details
            details = {
                "name": project.name,
                "editor_version": project.editor_version,
                "description": project.description,
                "author": project.author
            }

            zip.writestr("project.json", json.dumps(details, indent=4))

            # Save map images
            self._save_image_in_zip(zip, project.land_image, "land.png")
            self._save_image_in_zip(zip, project.boundary_image, "boundary.png")
            self._save_image_in_zip(zip, project.density_image, "density.png")
            self._save_image_in_zip(zip, project.terrain_image, "terrain.png")
            self._save_image_in_zip(zip, project.territory_image, "territory.png")
            self._save_image_in_zip(zip, project.province_image, "province.png")

            # Save map data
            if project.territory_data is not None:
                territory_data_json = [m.serialize_full_json() for m in project.territory_data]
                self._save_data_in_zip(zip, territory_data_json, "territory_data.json")          

            
            if project.province_data is not None:
                province_data_json = [m.serialize_full_json() for m in project.province_data]
                self._save_data_in_zip(zip, province_data_json, "province_data.json")

            # Save metadata
            self._save_territory_pmap_in_zip(zip, project.territory_pmap)
            self._save_cached_masks_in_zip(zip, project.cached_masks)

                np.savez(buffer, **project.cached_masks)
                zip.writestr("metadata/cached_masks.npz", buffer.getvalue())

            # Save settings
            settings = {
                "ocean_color": project.ocean_color,
                "lake_color": project.lake_color
            }

            zip.writestr("settings.json", json.dumps(settings, indent=4))
            
            # Update dirty indicator
            project.modified = False


    def _load_image_from_zip(self, zip: zipfile.ZipFile, filename: str) -> Image:
        """
        Private method for loading an image contained in a GSMAP or ZIP file

        @param zip: The GSMAP or ZIP file
        @param filename: The image name (example: land.png)
        """
        try:
            image_data = zip.read("images/" + filename)

        except KeyError:
            return None

        return Image.open(
            BytesIO(image_data)
        ).copy()


    def _load_data_from_zip(self, zip: zipfile.ZipFile, filename: str) -> list[dict[str, Any]] | None:
        """
        Private method for loading a JSON file contained in a GSMAP or ZIP file

        @param zip: The GSMAP or ZIP file
        @param filename: The JSON file name (example: territory_data.json)
        """
        try:
            json_data = zip.read("data/" + filename)

        except KeyError:
            return None

        return json.load(
            BytesIO(json_data)
        )


    def _load_territory_pmap_from_zip(self, zip: zipfile.ZipFile) -> ds.RegionPixelMap | None:
        """
        Private method to load 'territory_pmap.npy' file contained in a GSMAP or ZIP file

        @param zip: The GSMAP or ZIP file
        """
        try:
            territory_pmap_data = zip.read("metadata/territory_pmap.npy")

        except KeyError:
            return None

        return np.load(BytesIO(territory_pmap_data))


    def _load_cached_masks_from_zip(self, zip: zipfile.ZipFile) -> ds.Masks | None:
        """
        Private method to load 'cached_masks.npz' file contained in a GSMAP or ZIP file

        @param zip: The GSMAP or ZIP file
        """
        try:
            cached_masks_data = zip.read("metadata/cached_masks.npz")
            extracted_cached_masks = np.load(BytesIO(cached_masks_data))

        except KeyError:
            return None

        return ds.Masks.deserialize_from_json(
            {key: extracted_cached_masks[key] for key in extracted_cached_masks.files}
        )


    def _save_image_in_zip(self, zip: zipfile.ZipFile, image: Image.Image, filename: str) -> None:
        """
        Private method for saving an image to a GSMAP or ZIP file.

        @param zip: The GSMAP or ZIP file
        @param image: The image
        @param filename: The image name (example: density.png)
        """
        if image == None:
            return

        buffer = BytesIO()

        image.save(buffer, format="PNG")
        zip.writestr("images/" + filename, buffer.getvalue())


    def _save_data_in_zip(self, zip: zipfile.ZipFile, data: list[dict[str, Any]], filename: str) -> None:
        """
        Private method for saving data (list of dictionary) in JSON format to a GSMAP or ZIP file.

        @param zip: The GSMAP or ZIP file
        @param image: The data
        @param filename: The file name (example: province_data.json)
        """
        zip.writestr("data/" + filename, json.dumps(data, indent=4))


    def _save_territory_pmap_in_zip(self, zip: zipfile.ZipFile, territory_pmap: ds.RegionPixelMap | None) -> None:
        """
        Private method for saving 'territory_pmap.npy' file to a GSMAP or ZIP file.

        @param zip: The GSMAP or ZIP file
        @param territory_pmap: The territory pmap
        """
        if territory_pmap is not None:
            buffer = BytesIO()

            np.save(buffer, territory_pmap)
            zip.writestr("metadata/territory_pmap.npy", buffer.getvalue())


    def _save_cached_masks_in_zip(self, zip: zipfile.ZipFile, cached_masks: ds.Masks | None) -> None:
        """
        Private method for saving 'cached_masks.npz' file to a GSMAP or ZIP file.

        @param zip: The GSMAP or ZIP file
        @param cached_masks: The cached masks
        """
        if cached_masks is not None:
            buffer = BytesIO()

            np.savez(buffer, **cached_masks.serialize_to_json())
            zip.writestr("metadata/cached_masks.npz", buffer.getvalue())
