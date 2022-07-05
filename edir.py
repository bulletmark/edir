#!/usr/bin/env python3
'''
Program to rename, remove, or copy files and directories using your
editor. Will use git to action the rename and remove if run within a git
repository.
'''
# Author: Mark Blakeney, May 2019.

import sys
import os
import argparse
import subprocess
import tempfile
import itertools
import shlex
import pathlib
from collections import OrderedDict
from shutil import rmtree, copy2, copytree

# Some constants
PROG = pathlib.Path(sys.argv[0]).stem
CNFFILE = f'~/.config/{PROG}-flags.conf'
EDITOR = PROG.upper() + '_EDITOR'
SUFFIX = '.sh'

# The temp dir we will use in the dir of each target move
TEMPDIR = '.tmp-' + PROG

COLORS = {
    'remove': 'red',
    'rename': 'yellow',
    'copy': 'green',
}

args = None
gitfiles = set()
console = None
console_error = None

def log(func, msg, *, error=False):
    'Output given message with appropriate color'
    if console:
        color = COLORS[func]
        if error:
            console_error.print(msg, style=color, highlight=False)
        else:
            console.print(msg, style=color, highlight=False)
    else:
        print(msg, file=(sys.stderr if error else sys.stdout))

def run(cmd):
    'Run given command and return stdout, stderr'
    stdout = ''
    stderr = ''
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True,
                stderr=subprocess.PIPE, universal_newlines=True)
    except Exception as e:
        stderr = str(e)
    else:
        if res.stdout:
            stdout = res.stdout.strip()
        if res.stderr:
            stderr = res.stderr.strip()

    return stdout, stderr

def remove(path, git=False, trash=False, recurse=False):
    'Delete given file/directory'
    if not recurse and not path.is_symlink() and path.is_dir() and \
            any(path.iterdir()):
        return 'Directory not empty'

    if git:
        ropt = '-r' if recurse else ''
        out, err = run(f'git rm -f {ropt} "{path}"')
        return f'git error: {err}' if err else None

    if trash:
        out, err = run(f'{args.trash_program} "{path}"')
        return f'{args.trash_program} error: {err}' if err else None

    if recurse:
        try:
            rmtree(str(path))
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

    return None

def rename(pathsrc, pathdest, is_git=False):
    'Rename given pathsrc to pathdest'
    if is_git:
        out, err = run(f'git mv -f "{pathsrc}" "{pathdest}"')
        if err:
            log('git mv ERROR: {err}', error=True)
    else:
        pathsrc.replace(pathdest)

class Path:
    'Class to manage each instance of a file/dir'
    paths = []
    tempdirs = set()

    def __init__(self, path):
        'Class constructor'
        self.path = path
        self.newpath = None
        self.temppath = None
        self.copies = []
        self.is_dir = path.is_dir()
        self.diagrepr = str(self.path)
        self.is_git = self.diagrepr in gitfiles

        self.linerepr = self.diagrepr if self.diagrepr.startswith('/') \
                else './' + self.diagrepr
        if self.is_dir and not self.diagrepr.endswith('/'):
            self.linerepr += '/'
            self.diagrepr += '/'

    @staticmethod
    def inc_path(path):
        'Find next unique file name'
        # Iterate forever, there can only be a finite number of existing
        # paths
        name = path.name
        for c in itertools.count():
            if not path.is_symlink() and not path.exists():
                return path
            path = path.with_name(name + ('~' if c <= 0 else f'~{c}'))

    def copy(self, pathdest):
        'Copy given pathsrc to pathdest'
        func = copytree if self.is_dir else copy2
        try:
            func(self.newpath, pathdest)
        except Exception as e:
            return str(e)
        return None

    def rename_temp(self):
        'Move this path to a temp place in advance of final move'
        tempdir = self.newpath.parent / TEMPDIR
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            print(f'Create dir for {self.diagrepr} ERROR: '
                    f'Can not write in {tempdir.parent}', file=sys.stderr)
        else:
            self.temppath = self.inc_path(tempdir / self.newpath.name)
            self.tempdirs.add(tempdir)
            rename(self.path, self.temppath, self.is_git)

    def restore_temp(self):
        'Restore temp path to final destination'
        if not self.temppath:
            return False
        self.newpath = self.inc_path(self.newpath)
        rename(self.temppath, self.newpath, self.is_git)
        return True

    def sort_name(self):
        'Return name for sort'
        return str(self.path)

    def sort_time(self):
        'Return time for sort'
        return self.path.stat().st_mtime

    def sort_size(self):
        'Return size for sort'
        return self.path.stat().st_size

    @classmethod
    def remove_temps(cls):
        'Remove all the temp dirs we created in rename_temp() above'
        for p in cls.tempdirs:
            remove(p, git=None, trash=None, recurse=True)

        cls.tempdirs.clear()

    @classmethod
    def append(cls, path):
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
    def add(cls, name, expand):
        'Add file[s]/dir[s] to the list of paths'
        path = pathlib.Path(name)
        if not path.exists():
            sys.exit(f'ERROR: {name} does not exist')

        if expand and path.is_dir():
            for child in sorted(path.iterdir()):
                if args.all or not child.name.startswith('.'):
                    cls.append(child)
        else:
            cls.append(path)

    @classmethod
    def writefile(cls, fp):
        'Write the file for user to edit'
        fp.writelines(f'{i}\t{p.linerepr}\n' for i, p in
                enumerate(cls.paths, 1))

    @classmethod
    def readfile(cls, fp):
        'Read the list of files/dirs as edited by user'
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
                sys.exit(f'ERROR: line {count} number {n} invalid:\n{rawline}')

            if num <= 0 or num > len(cls.paths):
                sys.exit(f'ERROR: line {count} number {num} '
                        f'out of range:\n{rawline}')

            path = cls.paths[num - 1]

            if len(pathstr) > 1:
                pathstr = pathstr.rstrip('/')

            newpath = pathlib.Path(pathstr)

            if path.newpath:
                if newpath != path.path:
                    path.copies.append(newpath)
            else:
                path.newpath = newpath

def editfile(filename):
    'Run the editor command'
    # Use explicit editor or choose default
    editor = os.getenv(EDITOR) or os.getenv('VISUAL') or \
            os.getenv('EDITOR') or 'vi'
    editcmd = shlex.split(editor) + [str(filename)]

    # Run the editor ..
    with open('/dev/tty') as tty:
        res = subprocess.run(editcmd, stdin=tty)

    # Check if editor returned error
    if res.returncode != 0:
        sys.exit(f'ERROR: {editor} returned {res.returncode}')

def main():
    'Main code'
    global args
    global console
    global console_error

    # Process command line options
    opt = argparse.ArgumentParser(description=__doc__.strip(),
            epilog='Note you can set default starting arguments in '
            f'{CNFFILE}. The negation options (i.e. the --no-* options '
            'and their shortforms) allow you to temporarily override your '
            'defaults.')
    opt.add_argument('-a', '--all', action='store_true',
            help='include all (including hidden) files')
    opt.add_argument('-A', '--no-all', dest='all', action='store_false',
            help='negate the -a/--all/ option')
    opt.add_argument('-r', '--recurse', action='store_true',
            help='recursively remove any files and directories in '
            'removed directories')
    opt.add_argument('-R', '--no-recurse', dest='recurse', action='store_false',
            help='negate the -r/--recurse/ option')
    opt.add_argument('-q', '--quiet', action='store_true',
            help='do not print rename/remove/copy actions')
    opt.add_argument('-Q', '--no-quiet', dest='quiet', action='store_false',
            help='negate the -q/--quiet/ option')
    opt.add_argument('-G', '--no-git', dest='git',
            action='store_const', const=0,
            help='do not use git if invoked within a git repository')
    opt.add_argument('-g', '--git', dest='git',
            action='store_const', const=1,
            help='negate the --no-git option and DO use automatic git')
    opt.add_argument('-t', '--trash', action='store_true',
            help='use trash program to do deletions')
    opt.add_argument('-T', '--no-trash', dest='trash', action='store_false',
            help='negate the -t/--trash/ option')
    opt.add_argument('--trash-program', default='trash-put',
            help='trash program to use, default="%(default)s"')
    opt.add_argument('-c', '--no-color', action='store_true',
            help='do not color rename/remove/copy messages')
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
    opt.add_argument('-I', '--sort-time', dest='sort',
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
    opt.add_argument('--suffix',
            help=f'specify suffix for editor file, default="{SUFFIX}"')
    opt.add_argument('args', nargs='*',
            help='file|dir, or "-" for stdin')

    # Merge in default args from user config file. Then parse the
    # command line.
    cnffile = pathlib.Path(CNFFILE).expanduser()
    cnfargs = shlex.split(cnffile.read_text().strip()) \
            if cnffile.exists() else []
    args = opt.parse_args(cnfargs + sys.argv[1:])

    verbose = not args.quiet

    if not args.no_color:
        from rich.console import Console
        console = Console()
        console_error = Console(stderr=True)

    # Check if we are in a git repo
    if args.git != 0:
        out, err = run('git ls-files')
        if err and args.git:
            print(f'Git invocation error: {err}', file=sys.stderr)
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
                    Path.add(line.rstrip('\n\r'), False)
        else:
            Path.add(name, not args.dirnames)

    # Sanity check that we have something to edit
    if not Path.paths:
        desc = 'files' if args.files else \
                'directories' if args.dirs else 'files or directories'
        print(f'No {desc}.')
        return None

    if args.sort == 1:
        Path.paths.sort(key=Path.sort_name, reverse=args.sort_reverse)
    elif args.sort == 2:
        Path.paths.sort(key=Path.sort_time, reverse=args.sort_reverse)
    elif args.sort == 3:
        Path.paths.sort(key=Path.sort_size, reverse=args.sort_reverse)

    if args.group_dirs is not None and args.group_dirs >= 0:
        ldirs, lfiles = [], []
        for path in Path.paths:
            (ldirs if path.is_dir else lfiles).append(path)
        Path.paths = ldirs + lfiles if args.group_dirs else lfiles + ldirs

    # Create a temp file for the user to edit then read the lines back
    suffix = SUFFIX if args.suffix is None else args.suffix
    with tempfile.TemporaryDirectory() as fdir:
        fpath = pathlib.Path(f'{fdir}/{PROG}-{os.getpid()}{suffix}')
        with fpath.open('w') as fp:
            Path.writefile(fp)
        editfile(fpath)
        with fpath.open() as fp:
            Path.readfile(fp)

    # Reduce paths to only those that were removed or changed by the user
    paths = [p for p in Path.paths if p.path != p.newpath or p.copies]

    # Pass 1: Rename all moved files & dirs to temps, delete all removed
    # files.
    for p in paths:
        # Lazy eval the next path value
        p.note = ' recursively' if p.is_dir and any(p.path.iterdir()) else ''

        if p.newpath:
            if p.newpath != p.path:
                p.rename_temp()
        elif not p.is_dir:
            err = remove(p.path, p.is_git, args.trash)
            if err:
                log('remove', f'Remove {p.diagrepr} ERROR: {err}', error=True)
            elif verbose:
                log('remove', f'Removed {p.diagrepr}')

    # Pass 2: Delete all removed dirs, if empty or recursive delete.
    for p in paths:
        if p.is_dir and not p.newpath:
            if remove(p.path, p.is_git, args.trash, args.recurse) is None:
                # Have removed, so flag as finished for final dirs pass below
                p.is_dir = False
                if verbose:
                    log('remove', f'Removed {p.diagrepr}{p.note}')

    # Pass 3. Rename all temp files and dirs to final target, and make
    # copies.
    for p in paths:
        appdash = '/' if p.is_dir else ''
        if p.restore_temp() and verbose:
            log('rename', f'Renamed {p.diagrepr} to {p.newpath}{appdash}')

        for c in p.copies:
            err = p.copy(c)
            if err:
                log('copy', f'Copy {p.diagrepr} to {c}{appdash}{p.note} '
                        f'ERROR: {err}', error=True)
            elif verbose:
                log('copy', f'Copied {p.diagrepr} to {c}{appdash}{p.note}')

    # Remove all the temporary dirs we created
    Path.remove_temps()

    # Pass 4. Delete all remaining dirs
    for p in paths:
        if p.is_dir and not p.newpath:
            err = remove(p.path, p.is_git, args.trash, args.recurse)
            if err:
                log('remove', f'Remove {p.diagrepr} ERROR: {err}', error=True)
            elif verbose:
                log('remove', f'Removed {p.diagrepr}{p.note}')

if __name__ == '__main__':
    sys.exit(main())
