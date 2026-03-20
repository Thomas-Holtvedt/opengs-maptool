def main_gui() -> int:
    import sys
    from PyQt6.QtWidgets import QApplication
    from opengs_maptool.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

def main_terminal() -> None:
    from pathlib import Path
    from opengs_maptool.logic.main_program import MainProgram
    import opengs_maptool.config as config

    example_input_dir = Path(__file__).parent / "examples/input/"
    example_output_dir = Path(__file__).parent / "examples/output/"
    main_terminal = MainProgram()
    main_terminal.load_land_image(example_input_dir / "land.png")
    main_terminal.load_boundary_image(example_input_dir / "bound.png")
    main_terminal.load_density_image(example_input_dir / "density.png")
    main_terminal.load_terrain_image(example_input_dir / "terrain.png")

    # Set minimum density for territories using config values
    main_terminal.set_territory_params(
        land_density=config.LAND_TERRITORIES_MIN,
        ocean_density=config.OCEAN_TERRITORIES_MIN,
        density_strength=config.DENSITY_STRENGTH_DEFAULT / 10.0, # Intentionally 10x
        jagged_land_borders=False,
        jagged_ocean_borders=False
    )
    main_terminal.generate_territories()
    main_terminal.export_territory_image(example_output_dir / "territories.png")
    main_terminal.export_territory_definitions(example_output_dir / "territory_definitions.csv", "csv")
    main_terminal.export_territory_definitions(example_output_dir / "territory_definitions.json", "json")

    # Set minimum density for provinces using config values
    main_terminal.set_province_params(
        land_density=config.LAND_PROVINCES_DEFAULT,
        ocean_density=config.OCEAN_PROVINCES_DEFAULT,
        density_strength=config.DENSITY_STRENGTH_DEFAULT / 10.0, # Intentionally 10x
        jagged_land_borders=False,
        jagged_ocean_borders=False
    )
    main_terminal.generate_provinces()
    main_terminal.export_territory_history(example_output_dir / "territory_history.csv", "csv")
    main_terminal.export_territory_history(example_output_dir / "territory_history.json", "json")
    main_terminal.export_province_image(example_output_dir / "provinces.png")
    main_terminal.export_province_definitions(example_output_dir / "province_definitions.csv", "csv")
    main_terminal.export_province_definitions(example_output_dir / "province_definitions.json", "json")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="OpenGS Map Tool - A tool for creating province maps and related files"
    )
    parser.add_argument(
        "--mode",
        choices=["gui", "main_terminal"],
        default="gui",
        help="Which mode to run: 'gui' (default) for graphical interface, 'main_terminal' for batch/example mode."
    )
    args = parser.parse_args()

    if args.mode == "gui":
        raise SystemExit(main_gui())
    elif args.mode == "main_terminal":
        main_terminal()
