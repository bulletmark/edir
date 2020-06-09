#!/usr/bin/env python3
'Program to rename and remove files and directories using your editor.'
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
from shutil import rmtree

# Some constants
PROG = pathlib.Path(sys.argv[0]).stem
CNFFILE = pathlib.Path(f'~/.config/{PROG}-flags.conf').expanduser()
EDITOR = PROG.upper() + '_EDITOR'

# The temp dir we will use in the dir of each target move
TEMPDIR = '.tmp-' + PROG
args = None

def remove(path, *, git=False, recurse=False):
    'Delete given file/directory'
    if not recurse and path.is_dir() and any(path.iterdir()):
        return 'Directory not empty'

    if git:
        ropt = '-r' if recurse else ''
        res = subprocess.run(f'git rm -f {ropt} {path}'.split(),
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                universal_newlines=True)
        return f'git error: {res.stderr.strip()}' if res.stderr else None

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

def rename(pathsrc, pathdest):
    'Rename given pathsrc to pathdest'
    if args.git:
        subprocess.run(f'git mv -f {pathsrc} {pathdest}'.split(),
                stdout=subprocess.DEVNULL)
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
        self.is_dir = path.is_dir()

        self.diagrepr = str(self.path)
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

    def rename_temp(self):
        'Move this path to a temp place in advance of final move'
        tempdir = self.newpath.parent / TEMPDIR
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
        except Exception:
            print(f'{self.diagrepr} mkdir ERROR: '
                    f'Can not write in {tempdir.parent}', file=sys.stderr)
        else:
            self.temppath = self.inc_path(tempdir / self.newpath.name)
            self.tempdirs.add(tempdir)
            rename(self.path, self.temppath)

    def restore_temp(self):
        'Restore temp path to final destination'
        if not self.temppath:
            return False
        self.newpath = self.inc_path(self.newpath)
        rename(self.temppath, self.newpath)
        return True

    @classmethod
    def remove_temps(cls):
        'Remove all the temp dirs we created in rename_temp() above'
        for p in cls.tempdirs:
            remove(p, git=False, recurse=True)

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
        fp.flush()

    @classmethod
    def readfile(cls, fp):
        'Read the list of files/dirs as edited by user'
        fp.seek(0)
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

            if path.newpath:
                sys.exit(f'ERROR: line {count} number {num} edited twice:'
                        f'\n{rawline}')

            if len(pathstr) > 1:
                pathstr = pathstr.rstrip('/')

            path.newpath = pathlib.Path(pathstr)

def editfile(filename):
    'Run the editor command'
    # Use explicit editor (+ arguments) or choose default
    editcmd = shlex.split(os.getenv(EDITOR, ''))
    if not editcmd:
        editcmd = [os.getenv('VISUAL') or os.getenv('EDITOR') or 'vi']

    editcmd.append(filename)

    # Run the editor ..
    with open('/dev/tty') as tty:
        res = subprocess.run(editcmd, stdin=tty)

    # Check if editor returned error
    if res.returncode != 0:
        sys.exit(f'ERROR: {editcmd} returned {res.returncode}')

def main():
    'Main code'
    global args
    # Process command line options
    opt = argparse.ArgumentParser(description=__doc__.strip(),
            epilog='Note you can set default starting arguments in '
            '~/.config/edir-flags.conf.')
    opt.add_argument('-a', '--all', action='store_true',
            help='include/show all (including hidden) files')
    opt.add_argument('-r', '--recurse', action='store_true',
            help='recursively remove any files and directories in '
            'removed directories')
    opt.add_argument('-q', '--quiet', action='store_true',
            help='do not print rename/remove actions')
    opt.add_argument('-d', '--dirnames', action='store_true',
            help='edit given directory names directly, not their contents')
    opt.add_argument('-g', '--git', action='store_true',
            help='do "git mv" instead of "mv" and "git rm" instead of "rm"')
    opt.add_argument('--git-auto', action='store_true',
            help='apply --git option automatically if invoked from '
            'within a git repository')
    opt.add_argument('-G', '--no-git-auto', action='store_true',
            help='negate the --git-auto option (useful if you have set '
            '--git-auto as your default)')
    grp = opt.add_mutually_exclusive_group()
    grp.add_argument('-F', '--files', action='store_true',
            help='only show files')
    grp.add_argument('-D', '--dirs', action='store_true',
            help='only show directories')
    opt.add_argument('-L', '--nolinks', action='store_true',
            help='ignore all symlinks')
    opt.add_argument('args', nargs='*',
            help='file|dir, or "-" for stdin')

    # Add default args from env vars

    # Merge in default args from user config file. Then parse the
    # command line.
    cnfargs = shlex.split(CNFFILE.read_text().strip()) \
            if CNFFILE.exists() else []
    args = opt.parse_args(cnfargs + sys.argv[1:])
    verbose = not args.quiet

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

    # Check if we are in a git repo
    if args.git or (args.git_auto and not args.no_git_auto):
        res = subprocess.run('git rev-parse --is-inside-work-tree'.split(),
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                universal_newlines=True)
        is_git_repo = res.stdout and res.stdout.strip() == 'true'

        if args.git and not is_git_repo:
            opt.error('must be within a git repo to use -g/--git option')

        args.git = is_git_repo

    # Create a temp file for the user to edit then read the lines back
    with tempfile.NamedTemporaryFile('r+t', suffix='.sh') as fp:
        Path.writefile(fp)
        editfile(fp.name)
        Path.readfile(fp)

    # Reduce paths to only those that were removed or changed by the user
    paths = [p for p in Path.paths if p.path != p.newpath]

    # Pass 1: Rename all moved files & dirs to temps and delete all
    # removed files.
    for p in paths:
        if p.newpath:
            p.rename_temp()
        elif not p.is_dir:
            err = remove(p.path, git=args.git)
            if err:
                print(f'{p.diagrepr} remove ERROR: {err}', file=sys.stderr)
            elif verbose:
                print(f'{p.diagrepr} removed')

    # Pass 2: Delete all empty removed dirs.
    for p in paths:
        if p.is_dir and not p.newpath:
            if remove(p.path, git=args.git) is None:
                # Have removed, so flag as finished for final dirs pass below
                p.is_dir = False
                if verbose:
                    print(f'{p.diagrepr} removed')

    # Pass 3. Rename all temp files and dirs to final target
    for p in paths:
        if p.restore_temp() and verbose:
            appdash = '/' if p.is_dir else ''
            print(f'{p.diagrepr} -> {p.newpath}{appdash}')

    # Remove all the temporary dirs we created
    Path.remove_temps()

    # Pass 4. Delete all remaining dirs
    for p in paths:
        if p.is_dir and not p.newpath:
            note = ' recursively' if args.recurse and \
                    any(p.path.iterdir()) else ''
            err = remove(p.path, git=args.git, recurse=args.recurse)
            if err:
                print(f'{p.diagrepr} remove ERROR: {err}', file=sys.stderr)
            elif verbose:
                print(f'{p.diagrepr} removed{note}')

if __name__ == '__main__':
    sys.exit(main())
