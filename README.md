# Bethesda's Sublime Text extension for Fallout 4
http://www.creationkit.com/fallout4/index.php?title=Sublime_Text

A package for working with Papyrus files, used in Fallout 4 for scripting game
behavior.

For information about using Papyrus, check the [creation kit wiki](http://www.creationkit.com/fallout4/index.php?title=Category:Papyrus).


This package can handle compiling source files (.psc), disassembling bytecode
(.pex), and converting assembly (.pas) into bytecode.

If you're using an unorthodox installation (i.e. your Fallout 4 files are
moved out of the Steam directory), you'll want to set up an INI file so
Sublime can know where your compiler is, where the compiled files should go,
etc.

To create the default version of this file, select "PapyrusF4 INI: Create
default INI file" from the command palette (brought up with Ctrl-Shift-P).

(Note that to disassemble .pex files or convert .pas files, they must be in
the output folder specified by the ini, where they will be by default)

All files in this package are under copyright and the license documented in
the accompanying [LICENSE](LICENSE) file.
