#!/usr/bin/env python3
'''
Program to rename, remove, or copy files and directories using your
editor. Will use git to action the rename and remove if run within a git
repository.
'''
# Author: Mark Blakeney, May 2019.
import argparse
import itertools
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Tuple, Sequence, Callable

from platformdirs import user_config_path

# Some constants
PROG = Path(sys.argv[0]).stem
CNFFILE = user_config_path() / f'{PROG}-flags.conf'
EDITOR = PROG.upper() + '_EDITOR'
SUFFIX = '.sh'
SEP = os.sep

# The temp dir we will use in the dir of each target move
TEMPDIR = '.tmp-' + PROG

# Define action verbs and ANSI escape sequences for action colors
# Refer https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
ACTIONS = {
    'remove': (('\033[31m', '\033[30;41m'),  # Red
               ('Removing', 'Remove', 'Removed')),
    'copy': (('\033[32m', '\033[30;42m'),  # Green
             ('Copying', 'Copy', 'Copied')),
    'rename': (('\033[33m', '\033[30;43m'),  # Yellow
               ('Renaming', 'Rename', 'Renamed')),
}

COLOR_reset = '\033[39;49m'

args = argparse.Namespace()
gitfiles = set()
counts = [0, 0]

EDITORS = {'Windows': 'notepad', 'Darwin': 'open -e', 'default': 'vim'}

def get_default_editor() -> str:
    'Return default editor for this system'
    from platform import system
    return EDITORS.get(system(), EDITORS['default'])

def editfile(filename: Path) -> None:
    'Run the editor command'
    # Use explicit user defined editor or choose system default
    editor = os.getenv(EDITOR) or os.getenv('EDITOR') or get_default_editor()
    editcmd = shlex.split(editor) + [str(filename)]

    # Run the editor ..
    if sys.stdin.isatty():
        res = subprocess.run(editcmd)
    else:
        with open('/dev/tty') as tty:
            res = subprocess.run(editcmd, stdin=tty)

    # Check if editor returned error
    if res.returncode != 0:
        sys.exit(f'ERROR: {editor} returned error {res.returncode}')

def log(action: str, msg: str, error: Optional[str] = None, *,
        prompt: bool = False) -> None:
    'Output message with appropriate color'
    counts[bool(error)] += 1

    colors, tense = ACTIONS[action]

    if error:
        out = sys.stderr
        msg = f'{tense[1]} {msg} ERROR: {error}'
    elif args.quiet and not prompt:
        return
    else:
        out = sys.stdout
        msg = f'{tense[0] if prompt else tense[2]} {msg}'

    if not args.no_color:
        msg = colors[bool(error and not args.no_invert_color)] \
                + msg + COLOR_reset

    print(msg, file=out)

def run(cmd: Sequence[str]) -> Tuple[str, str]:
    'Run given command and return (stdout, stderr) strings'
    stdout = ''
    stderr = ''
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True)
    except Exception as e:
        stderr = str(e)
    else:
        if res.stdout:
            stdout = res.stdout.strip()
        if res.stderr:
            stderr = res.stderr.strip()

    return stdout, stderr

def remove(path: Path, git: bool = False, trash: bool = False,
           recurse: bool = False) -> Optional[str]:
    'Delete given file/directory'
    if not recurse and not path.is_symlink() and path.is_dir() and \
            any(path.iterdir()):
        return 'Directory not empty'

    if git:
        cmd = 'git rm -f'.split()
        if recurse:
            cmd.append('-r')
        out, err = run(cmd + [str(path)])
        return f'git error: {err}' if err else None

    if trash:
        out, err = run(args.trash_program + [str(path)])
        return f'{shlex.join(args.trash_program)} error: {err}' if err else None

    if recurse and not path.is_symlink():
        try:
            shutil.rmtree(str(path))
        except Exception as e:
            return str(e)
    else:
        try:
            if not path.is_symlink() and path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        except Exception as e:
            return str(e)

def rename(pathsrc: Path, pathdest: Path, is_git: bool = False) -> str:
    'Rename given pathsrc to pathdest'
    if is_git:
        out, err = run('git mv -f'.split() + [str(pathsrc), str(pathdest)])
        if err:
            err = f'git mv error: {err}'
    else:
        try:
            shutil.move(str(pathsrc), str(pathdest))
        except Exception as e:
            # Remove any trailing colon and specific file since we may
            # be renaming a temp file.
            err = str(e).split(':')[0]
        else:
            err = ''

    return err

def create_prompt(options: str) -> str:
    'Create a string of options + keys for user to choose from'
    letters = []
    words = []
    for arg in options.split():
        subwords = []
        for subarg in arg.split('/'):
            letters.append(subarg[0])
            subwords.append(f'({subarg[0].upper()}){subarg[1:]}')
        words.append('/'.join(subwords))
    return ', '.join(words) + ': [' + '|'.join(letters) + ']? '

class Fpath:
    'Class to manage each instance of a file/dir'
    paths = []
    tempdirs = set()

    def __init__(self, path: Path):
        'Class constructor'
        self.path = path
        self.newpath = None
        self.temppath = None
        self.note = ''
        self.copies: List[Path] = []
        try:
            self.is_dir = path.is_dir() and not path.is_symlink()
        except Exception as e:
            sys.exit(f'ERROR: Can not read {path}: {e}')

        self.appdash = SEP if self.is_dir else ''
        self.diagrepr = str(self.path)
        self.is_git = self.diagrepr in gitfiles

        self.linerepr = self.diagrepr if self.path.is_absolute() \
                else f'.{SEP}{self.diagrepr}'
        if self.is_dir and not self.diagrepr.endswith(SEP):
            self.linerepr += SEP
            self.diagrepr += SEP

    @staticmethod
    def inc_path(path: Path) -> Path:
        'Find next unique file name'
        # Iterate forever, there can only be a finite number of existing
        # paths
        name = path.name
        for c in itertools.count():
            if not path.is_symlink() and not path.exists():
                break
            path = path.with_name(name + ('~' if c <= 0 else f'~{c}'))

        return path

    def copy(self, pathdest: Path) -> Optional[str]:
        'Copy given pathsrc to pathdest'
        if self.is_dir:
            func: Callable = shutil.copytree
        else:
            func = shutil.copy2

            # copytree() will create the parent dir[s], but copy2() will not
            try:
                pathdest.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return str(e)
        try:
            func(str(self.newpath), str(pathdest))  # type:ignore
        except Exception as e:
            return str(e)

    def rename_temp(self) -> Optional[str]:
        'Move this path to a temp place in advance of final move'
        if not self.newpath:
            return None
        tempdir = self.newpath.parent / TEMPDIR
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Remove any trailing colon and specific file since we are
            # renaming a temp file.
            return str(e).split(':')[0]

        self.tempdirs.add(tempdir)
        temppath = self.inc_path(tempdir / self.newpath.name)
        if not (err := rename(self.path, temppath, self.is_git)):
            self.temppath = temppath

        return err

    def restore_temp(self) -> Optional[str]:
        'Restore temp path to final destination'
        if not self.temppath or not self.newpath:
            return None
        self.newpath = self.inc_path(self.newpath)
        return rename(self.temppath, self.newpath, self.is_git)

    def sort_name(self) -> str:
        'Return name for sort'
        return str(self.path)

    def sort_time(self) -> float:
        'Return time for sort'
        try:
            ret = self.path.lstat().st_mtime
        except Exception:
            ret = 0

        return ret

    def sort_size(self) -> int:
        'Return size for sort'
        try:
            ret = self.path.lstat().st_size
        except Exception:
            ret = 0

        return ret

    def is_recursive(self) -> bool:
        'Return True if directory and we can view it and contains children'
        if not self.is_dir:
            return False
        try:
            return any(self.path.iterdir())
        except Exception:
            return False

    def log_pending_changes(self) -> None:
        'Log all pending changes for this path'
        if not self.newpath:
            log('remove', f'"{self.diagrepr}"{self.note}', prompt=True)
        elif self.newpath != self.path:
            log('rename', f'"{self.diagrepr}" to '
                f'"{self.newpath}{self.appdash}"', prompt=True)
        for c in self.copies:
            log('copy', f'"{self.diagrepr}" to '
                f'"{c}{self.appdash}"{self.note}', prompt=True)

    @classmethod
    def remove_temps(cls) -> None:
        'Remove all the temp dirs we created in rename_temp() above'
        for p in cls.tempdirs:
            remove(p, git=False, trash=False, recurse=True)

        cls.tempdirs.clear()

    @classmethod
    def append(cls, path: Path) -> None:
        'Add a single file/dir to the list of paths'
        # Filter out files/dirs if asked
        if args.files:
            if path.is_dir():
                return
        elif args.dirs:
            if not path.is_dir():
                return

        # Filter out links if asked
        if args.nolinks and path.is_symlink():
            return

        cls.paths.append(cls(path))

    @classmethod
    def add(cls, name: str, expand: bool) -> None:
        'Add file[s]/dir[s] to the list of paths'
        path = Path(name)
        if not path.exists():
            sys.exit(f'ERROR: {name} does not exist')

        if expand and path.is_dir():
            for child in sorted(path.iterdir()):
                if args.all or not child.name.startswith('.'):
                    cls.append(child)
        else:
            cls.append(path)

    @classmethod
    def writefile(cls, fpath: Path) -> None:
        'Write the file for user to edit'
        with fpath.open('w') as fp:
            # Ensure consistent width for line numbers
            num_width = len(str(len(cls.paths)))
            fp.writelines(f'{i:0{num_width}}  {p.linerepr}\n'
                        for i, p in enumerate(cls.paths, 1))

    @classmethod
    def readfile(cls, fpath: Path) -> None:
        'Read the list of files/dirs as edited by user'
        # Reset all the read path changes to null state
        for p in cls.paths:
            p.newpath = None
            p.copies.clear()

        # Now read file and record changes
        with fpath.open() as fp:
            for count, line in enumerate(fp, 1):
                # Skip blank or commented lines
                rawline = line.rstrip('\n\r')
                line = rawline.lstrip()
                if not line or line[0] == '#':
                    continue

                try:
                    n, pathstr = line.split(maxsplit=1)
                except Exception:
                    sys.exit(f'ERROR: line {count} invalid:\n{rawline}')
                try:
                    num = int(n)
                except Exception:
                    sys.exit(f'ERROR: line {count} number {n} invalid:'
                             f'\n{rawline}')

                if num <= 0 or num > len(cls.paths):
                    sys.exit(f'ERROR: line {count} number {num} '
                            f'out of range:\n{rawline}')

                path = cls.paths[num - 1]

                if len(pathstr) > 1:
                    pathstr = pathstr.rstrip(SEP)

                newpath = Path(pathstr)

                if path.newpath:
                    if newpath != path.path and newpath not in path.copies:
                        path.copies.append(newpath)
                else:
                    path.newpath = newpath

    @classmethod
    def get_path_changes(cls) -> List:
        'Get a list of change paths from the user'
        prompt = create_prompt('proceed/yes edit restart quit[default]') \
                if args.interactive else None

        with tempfile.TemporaryDirectory() as fdir:
            # Create a temp file for the user to edit then read the lines back
            fpath = Path(fdir, f'{PROG}{args.suffix}')
            restart = True
            while True:
                if restart:
                    restart = False
                    cls.writefile(fpath)

                # Invoke editor on list of paths
                editfile(fpath)

                # Read the changed paths
                cls.readfile(fpath)

                # Reduce paths to those that were removed or changed by the user
                paths = [p for p in cls.paths
                         if p.path != p.newpath or p.copies]

                if not paths:
                    return []

                # Lazy eval the next path value
                for p in paths:
                    p.note = ' recursively' if p.is_recursive() else ''

                if not prompt:
                    return paths

                # Prompt user with pending changes if required
                for p in paths:
                    p.log_pending_changes()

                while True:
                    try:
                        ans = input(prompt).strip().lower()
                    except KeyboardInterrupt:
                        print()
                        return []

                    if not ans or ans == 'q':
                        return []
                    elif ans in 'py':
                        return paths
                    elif ans == 'e':
                        break
                    elif ans == 'r':
                        restart = True
                        break
                    else:
                        print(f'Invalid answer "{ans}".')

def main() -> int:
    'Main code'
    global args
    # Process command line options
    opt = argparse.ArgumentParser(description=__doc__.strip(),
            epilog='Note you can set default starting options in '
            f'{CNFFILE}. The negation options (i.e. the --no-* options '
            'and their shortforms) allow you to temporarily override your '
            'defaults.')
    opt.add_argument('-i', '--interactive', action='store_true',
            help='prompt with summary of changes and allow re-edit before '
                     'proceeding')
    opt.add_argument('-I', '--no-interactive', dest='interactive',
                     action='store_false',
            help='negate the -i/--interactive option')
    opt.add_argument('-a', '--all', action='store_true',
            help='include all (including hidden) files')
    opt.add_argument('-A', '--no-all', dest='all', action='store_false',
            help='negate the -a/--all option')
    opt.add_argument('-r', '--recurse', action='store_true',
            help='recursively remove any files and directories in '
            'removed directories')
    opt.add_argument('-R', '--no-recurse', dest='recurse', action='store_false',
            help='negate the -r/--recurse option')
    opt.add_argument('-q', '--quiet', action='store_true',
            help='do not print successful rename/remove/copy actions')
    opt.add_argument('-Q', '--no-quiet', dest='quiet', action='store_false',
            help='negate the -q/--quiet option')
    opt.add_argument('-G', '--no-git', dest='git',
            action='store_const', const=0,
            help='do not use git if invoked within a git repository')
    opt.add_argument('-g', '--git', dest='git',
            action='store_const', const=1,
            help='negate the --no-git option and DO use automatic git')
    opt.add_argument('-t', '--trash', action='store_true',
            help='use trash program to do deletions')
    opt.add_argument('-T', '--no-trash', dest='trash', action='store_false',
            help='negate the -t/--trash option')
    opt.add_argument('--trash-program', default='trash-put',
            help='trash program to use, default="%(default)s"')
    opt.add_argument('-c', '--no-color', action='store_true',
            help='do not color rename/remove/copy messages')
    opt.add_argument('-C', '--no-invert-color', action='store_true',
            help='do not invert the color to highlight error messages')
    opt.add_argument('-d', '--dirnames', action='store_true',
            help='edit given directory names directly, not their contents')
    grp = opt.add_mutually_exclusive_group()
    grp.add_argument('-F', '--files', action='store_true',
            help='only show/edit files')
    grp.add_argument('-D', '--dirs', action='store_true',
            help='only show/edit directories')
    opt.add_argument('-L', '--nolinks', action='store_true',
            help='ignore all symlinks')
    opt.add_argument('-N', '--sort-name', dest='sort',
            action='store_const', const=1,
            help='sort paths in file by name, alphabetically')
    opt.add_argument('-M', '--sort-time', dest='sort',
            action='store_const', const=2,
            help='sort paths in file by time, oldest first')
    opt.add_argument('-S', '--sort-size', dest='sort',
            action='store_const', const=3,
            help='sort paths in file by size, smallest first')
    opt.add_argument('-E', '--sort-reverse', action='store_true',
            help='sort paths (by name/time/size) in reverse')
    opt.add_argument('-X', '--group-dirs-first', dest='group_dirs',
            action='store_const', const=1,
            help='group directories first (including when sorted)')
    opt.add_argument('-Y', '--group-dirs-last', dest='group_dirs',
            action='store_const', const=0,
            help='group directories last (including when sorted)')
    opt.add_argument('-Z', '--no-group-dirs', dest='group_dirs',
            action='store_const', const=-1,
            help='negate the options to group directories')
    opt.add_argument('--suffix', default=SUFFIX,
            help='specify suffix for temp editor file, default="%(default)s"')
    opt.add_argument('-V', '--version', action='store_true',
            help=f'show {PROG} version')
    opt.add_argument('args', nargs='*',
            help='file|dir, or "-" for stdin')

    # Merge in default args from user config file. Then parse the
    # command line.
    if CNFFILE.exists():
        with CNFFILE.open() as fp:
            lines = [re.sub(r'#.*$', '', line).strip() for line in fp]
        cnflines = ' '.join(lines).strip()
    else:
        cnflines = ''

    args = opt.parse_args(shlex.split(cnflines) + sys.argv[1:])

    if args.version:
        from importlib.metadata import version
        try:
            ver = version(PROG)
        except Exception:
            ver = 'unknown'

        print(ver)
        return 0

    if args.trash:
        if not args.trash_program:
            opt.error('must specify trash program with --trash-program option')

        args.trash_program = args.trash_program.split()

    # Check if we are in a git repo
    if args.git != 0:
        out, giterr = run(('git', 'ls-files'))
        if giterr and args.git:
            print(f'Git invocation error: {giterr}', file=sys.stderr)
        if out:
            gitfiles.update(out.splitlines())

        if args.git and not gitfiles:
            opt.error('must be within a git repo to use -g/--git option')

    # Set input list to a combination of arguments and stdin
    filelist = args.args
    if sys.stdin.isatty():
        if not filelist:
            filelist.append('.')
    elif '-' not in filelist:
        filelist.insert(0, '-')

    # Iterate over all (unique) inputs to get a list of files/dirs
    for name in OrderedDict.fromkeys(filelist):
        if name == '-':
            for line in sys.stdin:
                name = line.rstrip('\n\r')
                if name != '.':
                    Fpath.add(line.rstrip('\n\r'), False)
        else:
            Fpath.add(name, not args.dirnames)

    # Sanity check that we have something to edit
    if not Fpath.paths:
        desc = 'files' if args.files else \
                'directories' if args.dirs else 'files or directories'
        print(f'No {desc}.')
        return 0

    if args.sort == 1:
        Fpath.paths.sort(key=Fpath.sort_name, reverse=args.sort_reverse)
    elif args.sort == 2:
        Fpath.paths.sort(key=Fpath.sort_time, reverse=args.sort_reverse)
    elif args.sort == 3:
        Fpath.paths.sort(key=Fpath.sort_size, reverse=args.sort_reverse)

    if args.group_dirs is not None and args.group_dirs >= 0:
        ldirs: List[Fpath] = []
        lfiles: List[Fpath] = []
        for path in Fpath.paths:
            (ldirs if path.is_dir else lfiles).append(path)
        Fpath.paths = ldirs + lfiles if args.group_dirs else lfiles + ldirs

    paths = Fpath.get_path_changes()
    if not paths:
        return 0

    err: Optional[str]

    # Pass 1: Rename all moved files & dirs to temps, delete all removed
    # files.
    for p in paths:
        if p.newpath:
            if p.newpath != p.path:
                if err := p.rename_temp():
                    log('rename',
                        f'"{p.diagrepr}" to "{p.newpath}{p.appdash}"', err)
        elif not p.is_dir:
            err = remove(p.path, p.is_git, args.trash)
            log('remove', f'"{p.diagrepr}"', err)

    # Pass 2: Delete all removed dirs, if empty or recursive delete.
    for p in paths:
        if p.is_dir and not p.newpath:
            if remove(p.path, p.is_git, args.trash, args.recurse) is None:
                # Have removed, so flag as finished for final dirs pass below
                p.is_dir = False
                log('remove', f'"{p.diagrepr}"{p.note}')

    # Pass 3. Rename all temp files and dirs to final target, and make
    # copies.
    for p in paths:
        if (err := p.restore_temp()) is not None:
            log('rename', f'"{p.diagrepr}" to "{p.newpath}{p.appdash}"', err)

        for c in p.copies:
            err = p.copy(c)
            log('copy', f'"{p.diagrepr}" to "{c}{p.appdash}"{p.note}', err)

    # Remove all the temporary dirs we created
    Fpath.remove_temps()

    # Pass 4. Delete all remaining dirs
    for p in paths:
        if p.is_dir and not p.newpath:
            err = remove(p.path, p.is_git, args.trash, args.recurse)
            log('remove', f'"{p.diagrepr}"{p.note}', err)

    # Return status code 0 = all good, 1 = some bad, 2 = all bad.
    return (1 if counts[0] > 0 else 2) if counts[1] > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
