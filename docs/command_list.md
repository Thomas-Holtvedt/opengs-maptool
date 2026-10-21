# Console Command Reference

> **Generated documentation:** This file is generated from command registrations. Update the command definitions and rerun `uv run python dev_scripts/generate_command_docs.py`; do not edit this generated file directly.

Append `-h` or `--help` to any command to display its built-in help in the console.

## Boundary

### `boundary.image.import`

Imports the boundary image from a file.

**Usage**

```text
boundary.image.import <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to the boundary image file to import.

---

## Console

### `console.commands.list`

Display a simplified list of commands.

**Usage**

```text
console.commands.list
```

**Arguments**

None.

---

### `console.history.clear`

Clears the console message history.

**Usage**

```text
console.history.clear
```

**Arguments**

None.

---

### `console.history.list`

Displays the history of console commands entered by the user.

**Usage**

```text
console.history.list
```

**Arguments**

None.

---

## Density

### `density.exclude_ocean_provinces`

Sets whether density applies to ocean provinces.

**Usage**

```text
density.exclude_ocean_provinces <activate>
```

**Arguments**

#### `<activate>`

- Type: `bool`
- Required positional argument
- Description: Whether to exclude ocean provinces from the effect of density.

---

### `density.exclude_ocean_territories`

Sets whether density applies to ocean territories.

**Usage**

```text
density.exclude_ocean_territories <activate>
```

**Arguments**

#### `<activate>`

- Type: `bool`
- Required positional argument
- Description: Whether to exclude ocean territories from the effect of density.

---

### `density.image.equator_distribute`

Generates equator-based density distribution.

**Usage**

```text
density.image.equator_distribute
```

**Arguments**

None.

---

### `density.image.import`

Imports the density image from a file.

**Usage**

```text
density.image.import <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to the density image file to import.

---

### `density.image.normalize`

Normalizes density image.

**Usage**

```text
density.image.normalize
```

**Arguments**

None.

---

### `density.image.remove`

Removes the current density image.

**Usage**

```text
density.image.remove
```

**Arguments**

None.

---

## Land

### `land.color_settings.set`

Changes the colors expected in the land image for land, oceans and lakes.

**Usage**

```text
land.color_settings.set <land_type> <new_color>
```

**Arguments**

#### `<land_type>`

- Type: `str`
- Required positional argument
- Accepted values: `land`, `ocean`, `lake`
- Description: The land type to change the color for.

#### `<new_color>`

- Type: `str`
- Required positional argument
- Description: The new color in #RRGGBB format.

---

### `land.image.import`

Imports a land image into the project.

**Usage**

```text
land.image.import <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to the land image file to import.

---

## Link

### `link.discord`

Displays the link to the OpenGS Discord server.

**Usage**

```text
link.discord
```

**Arguments**

None.

---

### `link.github`

Displays the link to the editor's GitHub repository.

**Usage**

```text
link.github
```

**Arguments**

None.

---

### `link.help`

Displays the link for the command documentation.

**Usage**

```text
link.help
```

**Arguments**

None.

**Aliases**

`?`, `h`, `help`

---

## Project

### `project.author.set`

Sets the author in metadata of the current project.

**Usage**

```text
project.author.set <author>
```

**Arguments**

#### `<author>`

- Type: `str`
- Required positional argument
- Description: The new author for the project.

---

### `project.description.set`

Sets the description in metadata of the current project.

**Usage**

```text
project.description.set <description>
```

**Arguments**

#### `<description>`

- Type: `str`
- Required positional argument
- Description: The new description for the project.

---

### `project.name.set`

Sets the name in metadata of the current project.

**Usage**

```text
project.name.set <name>
```

**Arguments**

#### `<name>`

- Type: `str`
- Required positional argument
- Description: The new name for the project.

---

### `project.new`

Creates a new project.

**Usage**

```text
project.new [--force | --no-force]
```

**Arguments**

#### `--force` / `--no-force`

- Type: `bool`
- Optional; default: `false`
- Description: Ignore unsaved changes if enabled and create a new project.

---

### `project.open`

Opens an existing project file.

**Usage**

```text
project.open <path> [--force | --no-force]
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to the project file to open.

#### `--force` / `--no-force`

- Type: `bool`
- Optional; default: `false`
- Description: Ignore unsaved changes if enabled and open the project file.

**Examples**

```text
project.open "my-project.gsmap"
project.open "my-project.gsmap" --force
```

---

### `project.save`

Saves the current project to a target path if supplied or the already set path.

**Usage**

```text
project.save [--path PATH]
```

**Arguments**

#### `--path`

- Type: `str`
- Optional; default: ``
- Description: The path to save the project file to.

---

## Province

### `province.definitions.export`

Exports province definitions. Accepted formats: JSON, CSV, YAML, XML.

**Usage**

```text
province.definitions.export <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to export the province definitions to. Format is automatically detected

---

### `province.density_strength.set`

Sets province density strength.

**Usage**

```text
province.density_strength.set <factor>
```

**Arguments**

#### `<factor>`

- Type: `float`
- Required positional argument
- Description: The density strength to set for provinces.

---

### `province.image.export`

Exports the province image.

**Usage**

```text
province.image.export <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to export the province image to.

---

### `province.image.generate`

Generates the province map.

**Usage**

```text
province.image.generate
```

**Arguments**

None.

---

### `province.jagged_land.set`

Sets how strongly jagged the land borders of provinces should be.

**Usage**

```text
province.jagged_land.set <strength>
```

**Arguments**

#### `<strength>`

- Type: `float`
- Required positional argument
- Description: The jaggedness amplitude to set for provinces.

---

### `province.jagged_oceanic.set`

Sets how strongly jagged the oceanic borders of provinces should be.

**Usage**

```text
province.jagged_oceanic.set <strength>
```

**Arguments**

#### `<strength>`

- Type: `float`
- Required positional argument
- Description: The jaggedness amplitude to set for provinces.

---

### `province.land_density.set`

Sets land province density.

**Usage**

```text
province.land_density.set <value>
```

**Arguments**

#### `<value>`

- Type: `int`
- Required positional argument
- Description: The land density to set for territories.

---

### `province.oceanic_density.set`

Sets oceanic province density.

**Usage**

```text
province.oceanic_density.set <value>
```

**Arguments**

#### `<value>`

- Type: `int`
- Required positional argument
- Description: The oceanic density to set for territories.

---

## Terrain

### `terrain.image.import`

Imports the terrain image from a file.

**Usage**

```text
terrain.image.import <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to the terrain image file to import.

---

## Territory

### `territory.definitions.export`

Exports territory definitions. Accepted formats: JSON, CSV, YAML, XML.

**Usage**

```text
territory.definitions.export <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to export the territory definitions to. Format is automatically detected

---

### `territory.density_strength.set`

Sets territory density strength.

**Usage**

```text
territory.density_strength.set <factor>
```

**Arguments**

#### `<factor>`

- Type: `float`
- Required positional argument
- Description: The density strength to set for territories.

---

### `territory.history.export`

Exports territory history. Accepted formats: JSON, CSV, YAML, XML.

**Usage**

```text
territory.history.export <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to export the territory history to. Format is automatically detected

---

### `territory.image.export`

Exports the territory image.

**Usage**

```text
territory.image.export <path>
```

**Arguments**

#### `<path>`

- Type: `str`
- Required positional argument
- Description: The path to export the territory image to.

---

### `territory.image.generate`

Generates the territory map.

**Usage**

```text
territory.image.generate
```

**Arguments**

None.

---

### `territory.jagged_land.set`

Sets how strongly jagged the land borders of territories should be.

**Usage**

```text
territory.jagged_land.set <strength>
```

**Arguments**

#### `<strength>`

- Type: `float`
- Required positional argument
- Description: The jaggedness amplitude to set for territories.

---

### `territory.jagged_oceanic.set`

Sets how strongly jagged the oceanic borders of territories should be.

**Usage**

```text
territory.jagged_oceanic.set <strength>
```

**Arguments**

#### `<strength>`

- Type: `float`
- Required positional argument
- Description: The jaggedness amplitude to set for territories.

---

### `territory.land_density.set`

Sets land territory density.

**Usage**

```text
territory.land_density.set <value>
```

**Arguments**

#### `<value>`

- Type: `int`
- Required positional argument
- Description: The land density to set for territories.

---

### `territory.oceanic_density.set`

Sets oceanic territory density.

**Usage**

```text
territory.oceanic_density.set <value>
```

**Arguments**

#### `<value>`

- Type: `int`
- Required positional argument
- Description: The oceanic density to set for territories.

---

## Wait

### `wait.tasks.completed`

Waits until all background tasks are completed.

**Usage**

```text
wait.tasks.completed
```

**Arguments**

None.

---
