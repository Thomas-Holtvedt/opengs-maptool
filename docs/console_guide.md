# The Console

The console is a tool located in the right-hand panel. It allows you to execute various commands to retrieve information or perform actions.
This document explains the console, [the used command syntax](#command-syntax) and has [a list of commands](#list-of-commands).
Using the two buttons located below the console, you can export or import a console's history into the editor.

> Please keep in mind that this feature is experimental and still in its early stages.
<br>
> Additionally, in the future, the console will contain logs of all actions performed in the editor.

## Command Syntax

The console command structure follows standard command-line and [Python `argparse` patterns](https://docs.python.org/3/howto/argparse.html). A command consists of a unique dot-separated command identifier, followed by **positional arguments** and/or **optional flags**:

```text
command.name <required_positional_arguments> [--optional_flag] [--optional_setting value]
```

### 1. Required Positional Arguments

Required inputs have no dashes and must be provided in the exact order specified by the command:

```text
project.open "my-project.gsmap"
land.image.import "C:\Maps\land_layer.png"
```

* **Quoting:** If an argument value contains spaces, backslashes or other special characters (such as file paths), it is safter and sometimes necessary to enclose it in double quotes (`"..."`). Single quotes are **not** supported (`'...'`).

### 2. Optional Arguments (Flags & Settings)

Options modify the behavior of a command. They are identified by double dashes (`--`) and can be placed anywhere after the command identifier:

* **Boolean Switches (Flags):** Options like `--force` act as on/off switches. You do not need to provide a value; passing the flag turns it on.
* **Value Settings:** Options that require data are provided using either a space or an equals sign.

#### Example
A **hypothetical** command declared as `example.export <path> [--format FORMAT] [--force]` could be used like this:
```text
project.new --force
project.open "my-project.opengs" --force
example.export "output/map.png" --format png --scale 2
example.export "output/map.png" --scale=2 --format=png
```

---

## Interactive Console Features

### Command History
Use the up and down arrow keys to navigate or rerun previous commands.

### Dynamic Help Menus

Every command has a built-in help manual. Appending `-h` or `--help` to any command will display its formal syntax and detailed argument descriptions directly in your console:

```text
project.open --help
```

### Smart Command Suggestions

If you mistype a command name, the console automatically scans for a close matching command or alias and suggest the correct syntax:

```text
> projct.open "map.gsmap"
Unknown command 'projct.open'. Did you mean 'project.open'?
```




# List of Commands
**For a list of commands see [command_list.md](command_list.md).**
