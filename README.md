## EDIR - Rename, Remove, and Copy Files and Directories Using Your Editor
[![PyPi](https://img.shields.io/pypi/v/edir)](https://pypi.org/project/edir/)
[![AUR](https://img.shields.io/aur/version/edir)](https://aur.archlinux.org/packages/edir/)

[edir](http://github.com/bulletmark/edir) is a command line utility to
rename, remove, and copy filenames and directories using your text
editor. Run it in the current directory and `edir` will open your editor
on a list of files and directories in that directory. Each item in the
directory will appear on its own numbered line. These numbers are how
`edir` keeps track of what items are changed. Delete lines to remove
files/directories, edit lines to rename files/directories, or duplicate
line numbers to copy files/directories. You can also switch pairs of
numbers to swap files or directories. If run from within a
[Git](https://git-scm.com/) repository, `edir` will [use
Git](#renames-and-deletes-in-a-git-repository) to rename or remove
tracked files/directories. You can use a [trash program](#using-trash)
to remove files.

The latest version and documentation is available at
https://github.com/bulletmark/edir.

## Advantages Compared to Vidir

[edir](http://github.com/bulletmark/edir) unashamedly mimics the
functionality of the [vidir](https://linux.die.net/man/1/vidir) utility
from [moreutils](https://joeyh.name/code/moreutils/) but aims to improve it in
the following ways:

1. `edir` automatically uses `git mv` instead of `mv` and `git rm`
    instead of `rm` for tracked files when invoked within a
    [Git](https://git-scm.com/) repository. There is also a `-G/--no-git`
    option to suppress this default action. See the description in the
    section below about [git options](#renames-and-deletes-in-a-git-repository).

2. `vidir` presents file and directories equivalently but `edir` adds a
   trailing slash `/` to visually discriminate directories. E.g. if `afile` and
   `bfile` are files, `adir` and `bdir` are directories, then `vidir`
   presents these in your editor as follows.

   ```
   1	./a
   2	./b
   3	./c
   4	./d
   ```

   But `edir` presents these as:

   ```
   1	./a
   2	./b
   3	./c/
   4	./d/
   ```

   Note the trailing slash is only for presentation in your editor. You
   are not required to ensure it is present after editing. E.g. editing
   line 3 above to `./e` (or even just to `e`) would still rename the
   directory `c` to `e`.

   Note also, that both `edir` and `vidir` show the leading `./` on each
   entry so that any leading spaces are clearly seen, and can be edited.

3. `edir` adds the ability to copy files or directories one or more
   times when you duplicate a numbered line. `vidir` does not have copy
   functionality.

4. `edir` allows you to remove a file/directory by deleting the line, as
   `vidir` does, but you can also remove it by pre-pending a `#` to
   "comment it out" or by substituting an entirely blank line.

5. By default, `edir` prints remove, rename, and copy messages whereas
   `vidir` prints messages only when the `-v/--verbose` switch is added.
   You can add `-q/--quiet` to `edir` to suppress these messages.

6. `edir` outputs messages in color. Remove messages are red, rename
   messages are yellow, and copy messages are green. You can choose to
   disable colored output.

7. When `vidir` is run with the `-v/--verbose` switch then it reports
   the renaming of original to intermediate temporary to final files if
   files are swapped etc. That is rather an implementation detail so
   `edir` only reports the original to final renames which is all the
   user really cares about.

8. To remove a large recursive tree you must pipe the directory tree to
   `vidir` and then explicitly remove all children files and directories
   before deleting a parent directory. You can do this also in `edir` of
   course (and arguably it is probably the safest approach) but there
   are times when you really want to let `edir` remove recursively so
   `edir` adds a `-r/--recurse` switch to allow this. BE CAREFUL USING
   THIS!

9. `vidir` always shows all files and directories in a directory,
   including hidden files and directories (i.e. those starting with a
   `.`). Usually a user does not want to be bothered with these so
   `edir` by default does not show them. They can be included by adding
   the `-a/--all` switch.

10. `edir` does not require the user to specify the `-` if something has
    been piped to standard input. E.g. you need only type `find | edir`
    as opposed to `find | edir -`. Note that `vidir` requires the second
    form.

11. `edir` adds a [`-i/--interactive` option](#previewing-changes) to
    show pending changes and prompt the user before actioning them. You
    can also choose to re-edit the changes.

12. `edir` adds a `-F/--files` option to only show files, or `-D/--dirs`
    to only show directories.

13. `edir` adds a `-L/--nolinks` option to ignore symbolic links.

14. `edir` adds a `-d/--dirnames` option to edit specified directory
    names directly, not their contents. I.e. this is like `ls -d mydir`
    compared to `ls mydir`.

15. `edir` adds a [`-t/--trash` option](#using-trash) to remove to your
    [Trash](https://specifications.freedesktop.org/trash-spec/trashspec-1.0.html).
    By default this option invokes
    [`trash-put`](https://www.mankier.com/1/trash-put) from the
    [trash-cli](https://github.com/andreafrancia/trash-cli) package to
    do deletions but you can specify any alternative trash program, see
    [section below](#using-trash).

16. `edir` adds `-N/--sort-name, -M/--sort-time, -S/--sort-size` options
    to sort the paths when listed in your editor. There is also a
    `-E/--sort-reverse` option to reverse the order.

17. `edir` adds `-X/--group-dirs-first` and `-Y/--group-dirs-last`
    options to display directories grouped together, either first or
    last. These can be combined with the above sorting options.

18. `edir` shows a message "No files or directories" if there is nothing
    to edit, rather than opening an empty file as `vidir` does.

19. `edir` filters out any duplicate paths you may inadvertently specify
    on it's command line.

20. `edir` always invokes a consistent duplicate renaming scheme. E.g. if
    you rename `b`, `c`, `d` all to the same pre-existing name `a` then
    `edir` will rename `b` to `a~`, `c` to `a~1`, `d` to `a~2`.
    Depending on order of operations, `vidir` is not always consistent
    about this, E.g. sometimes it creates a `a~1` with no `a~` (this may
    be a bug in `vidir` that nobody has ever bothered to
    report/address?).

21. `edir` creates the temporary editing file with a `.sh` suffix so
    your EDITOR may syntax highlight the entries. Optionally, you can
    change this default suffix.

22. `edir` provides an optional environment value to add custom options
    to the invocation of your editor. See [section
    below](#edir_editor-environment-variable).

23. `edir` provides an optional configuration file to set default `edir`
    command line options. See [section below](#command-default-options).

24. Contrary to what it's name implies, `vidir` actually respects your
    `$EDITOR` variable and runs your preferred editor like `edir` does
    but `edir` has been given a generic name to make this more apparent.
    If `$EDITOR` is not set then `edir` uses a default editor
    appropriate to your system.

25. `vidir` returns status code 0 if all files successful, or 1 if any
     error. `edir` returns 0 if all files successful, 1 if some had
     error, or 2 if all had error.

26. `vidir` returns an error when attempting to rename across different
    file systems, which `edir` allows.

27. `edir` always ensures editor line numbers have the same width (e.g.
    `1` to `6` for 6 files, or `01` to `12` for 12 files, etc) so that
    file names always line up justified. This facilitates block editing
    of file names, e.g. using vim's [visual block
    mode](https://linuxhint.com/vim-visual-block-mode/). `vidir` doesn't
    do this so file names can be jagged wrt each other which makes block
    editing awkward.

28. `edir` is very strict about the format of the lines you edit and
    immediately exits with an error message (before changing anything)
    if you format one of the lines incorrectly. All lines in the edited
    list:

    1. Must start with a number and that number must be in range.
    2. Must have at least one white space/tab after the number,
    3. Must have a remaining valid path name.
    4. Can start with a `#` or be completely blank to be considered the
       same as deleted.

    Note the final edited order of lines does not matter, only the first
    number value is used to match the newly edited line to the original
    line so an easy way to swap two file names is just to swap their
    numbers.

29. `edir` always actions files consistently. The sequence of
     operations applied is:

    1. Deleted files are removed and all renamed files and directories
       are renamed to temporaries. The temporaries are made on the same
       file-system as the target.

    2. Empty deleted directories are removed.

    3. Renamed temporary files and directories are renamed to their
       target name. Any required copies are created.

    4. Remaining deleted directories are removed.

    In simple terms, remember that files are processed before
    directories so you can rename files into a different directory and
    then delete the original directory, all in one edit. However in
    practice it is far **less confusing and less risky** if you perform
    complicated renames and moves in distinct steps.

## Renames and Deletes in a GIT Repository

When working within a [Git](https://git-scm.com/) repository, you nearly
always want to use `git mv` instead of `mv` and `git rm` instead of `rm`
for files and directories so `edir` recognises this and does it
automatically. Note that only tracked files/dirs are moved or renamed
using Git. Untracked files/dirs within the repository are removed or
renamed in the normal way.

If for some reason you don't want automatic git action then you can use
the `-G/--no-git` option temporarily, or set it a default option. See
the section below on how to set [default
options](#command-default-options). If you set `--no-git` as the
default, then you can use `-g/-git` on the command line to turn that
default option off temporarily and re-enable git functionality.

## Using Trash

Given how easy `edir` facilitates deleting files, some users may prefer
to remove them to system
[Trash](https://specifications.freedesktop.org/trash-spec/trashspec-1.0.html)
from where they can be later listed and/or recovered. Specifying
`-t/--trash` does this by executing the
[`trash-put`](https://www.mankier.com/1/trash-put) command, from the
[`trash-cli`](https://github.com/andreafrancia/trash-cli) package, to
remove files rather than removing them natively.

You may want to set `-t/--trash` as a default option. If you do so then
you can use `-T` on the command line to turn that default option off
temporarily.

You can specify an alternative trash program, e.g.
[`trash-d`](https://github.com/rushsteve1/trash-d), or
[`gio trash`](https://man.archlinux.org/man/gio.1#COMMANDS), or
[`gtrash put`](https://github.com/umlx5h/gtrash),
by setting the `--trash-program` option. Most likely you
want to set this as a [default option](#command-default-options).

## Previewing Changes

Many users would like to see a preview of changes after they finish
editing but before they are actioned by `edir`, i.e. to confirm exactly
which files/dirs will be deleted, renamed, or copied. Add the
`-i/--interactive` option and edir will present a list of changes and
prompt you to continue, or allow you to re-edit the path list etc.
Consider setting `--interactive` as a [default
option](#command-default-options) so you are always prompted.

After a preview of pending changes is shown a prompt is presented for
the user to enter a single key:

`(P)roceed/(Y)es, (E)dit, (R)estart, (Q)uit[default]: [p|y|e|r|q]?`

where:

|Option       |Key       |Action|
|---          |---       |---|
|`Proceed/Yes`|`p` or `y`|Proceed with the path changes.|
|`Edit`       |`e`       |Edit the path list again, as it is was last edited.|
|`Restart`    |`r`       |Restart editing the path list again, as it originally began.|
|`Quit`       |`q`       |Quit immediately without making any changes. This is the default if no key is entered.|

## Installation or Upgrade

Arch users can install [edir from the AUR](https://aur.archlinux.org/packages/edir/).

Python 3.8 or later is required. Note [edir is on
PyPI](https://pypi.org/project/edir/) so just ensure that
[`pipx`](https://pypa.github.io/pipx/) is installed then type the
following:

```
$ pipx install edir
```

To upgrade:

```
$ pipx upgrade edir
```

[Git](https://git-scm.com/) must be installed if you want to use the git
options. A trash program such as
[trash-cli](https://github.com/andreafrancia/trash-cli) package is
required if you want `-t/--trash` functionality.

### EDIR_EDITOR Environment Variable

`edir` selects your editor from the first environment value found of:
`$EDIR_EDITOR` or `$EDITOR`, then guesses a fallback default editor
appropriate to your system if neither of these are set.

You can also set `EDIR_EDITOR` explicitly to an editor + arguments
string if you want `edir` to call your editor with specific arguments.

## Command Default Options

You can add default options to a personal configuration file
`~/.config/edir-flags.conf`. If that file exists then each line of
options will be concatenated and automatically prepended to your `edir`
command line arguments. Comments in the file (i.e. starting with a `#`)
are ignored. Type `edir -h` to see all [supported
options](#command-line-options).

The options `--interactive`, `--all`, `--recurse`, `--quiet`,
`--no-git`, `--trash`, `--suffix`, `--no-color`, `--no-invert-color`,
`--group-dirs-first/last`, `--trash-program` are sensible candidates to
consider setting as default. If you set these then "on-the-fly" negation
options `-I`, `-A`, `-R`, `-Q`, `-g`, `-T`, `-Z` are also provided to
temporarily override and disable default options on the command line.

## Examples

Rename and/or remove any files and directories in the current directory:

```
$ edir
```

Rename and/or remove any jpeg files in current dir:

```
$ edir *.jpg
```

Rename and/or remove any files under current directory and subdirectories:

```
$ find | edir -F
```

Use [`fd`](https://github.com/sharkdp/fd) to view and `git mv/rm`
repository files only, in the current directory only:

```
$ fd -d1 -tf | edir -g
```

## Command Line Options

Type `edir -h` to view the usage summary:

```
usage: edir [-h] [-i] [-I] [-a] [-A] [-r] [-R] [-q] [-Q] [-G] [-g] [-t]
               [-T] [--trash-program TRASH_PROGRAM] [-c] [-C] [-d] [-F | -D]
               [-L] [-N] [-M] [-S] [-E] [-X] [-Y] [-Z] [--suffix SUFFIX] [-V]
               [args ...]

Program to rename, remove, or copy files and directories using your editor.
Will use git to action the rename and remove if run within a git repository.

positional arguments:
  args                  file|dir, or "-" for stdin

options:
  -h, --help            show this help message and exit
  -i, --interactive     prompt with summary of changes and allow re-edit
                        before proceeding
  -I, --no-interactive  negate the -i/--interactive option
  -a, --all             include all (including hidden) files
  -A, --no-all          negate the -a/--all option
  -r, --recurse         recursively remove any files and directories in
                        removed directories
  -R, --no-recurse      negate the -r/--recurse option
  -q, --quiet           do not print successful rename/remove/copy actions
  -Q, --no-quiet        negate the -q/--quiet option
  -G, --no-git          do not use git if invoked within a git repository
  -g, --git             negate the --no-git option and DO use automatic git
  -t, --trash           use trash program to do deletions
  -T, --no-trash        negate the -t/--trash option
  --trash-program TRASH_PROGRAM
                        trash program to use, default="trash-put"
  -c, --no-color        do not color rename/remove/copy messages
  -C, --no-invert-color
                        do not invert the color to highlight error messages
  -d, --dirnames        edit given directory names directly, not their
                        contents
  -F, --files           only show/edit files
  -D, --dirs            only show/edit directories
  -L, --nolinks         ignore all symlinks
  -N, --sort-name       sort paths in file by name, alphabetically
  -M, --sort-time       sort paths in file by time, oldest first
  -S, --sort-size       sort paths in file by size, smallest first
  -E, --sort-reverse    sort paths (by name/time/size) in reverse
  -X, --group-dirs-first
                        group directories first (including when sorted)
  -Y, --group-dirs-last
                        group directories last (including when sorted)
  -Z, --no-group-dirs   negate the options to group directories
  --suffix SUFFIX       specify suffix for temp editor file, default=".sh"
  -V, --version         show edir version

Note you can set default starting options in $HOME/.config/edir-
flags.conf. The negation options (i.e. the --no-* options and their
shortforms) allow you to temporarily override your defaults.
```

## Embed in Ranger File Manager

In many ways `edir` (and `vidir`) is better than the
[ranger](https://ranger.github.io/)
[bulkrename](https://github.com/ranger/ranger/wiki/Official-user-guide#bulk-renaming)
command which does not handle name swaps and clashes etc. To add `edir`
as a command within [ranger](https://ranger.github.io/), add or create
the following in `~/.config/ranger/commands.py`. Then run it from within
[ranger](https://ranger.github.io/) by typing `:edir`.

```python
from ranger.api.commands import Command

class edir(Command):
    '''
    :edir [file|dir]

    Run edir on the selected file or dir.
    Default argument is current dir.
    '''
    def execute(self):
        self.fm.run('edir -q ' + self.rest(1))
    def tab(self, tabnum):
        return self._tab_directory_content()
```

## License

Copyright (C) 2019 Mark Blakeney. This program is distributed under the
terms of the GNU General Public License.
This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or any later
version.
This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License at <http://www.gnu.org/licenses/> for more details.

<!-- vim: se ai syn=markdown: -->
