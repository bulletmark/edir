#!/usr/bin/python3
# Setup script to install this package.
# M.Blakeney, Mar 2018.

import re
from pathlib import Path
from setuptools import setup

here = Path(__file__).resolve().parent
name = re.sub(r'-.*', '', here.stem)
readme = here.joinpath('README.md').read_text()

setup(
    name=name,
    version='1.2',
    description='Utility to rename and remove files/dirs using your editor',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/bulletmark/{}'.format(name),
    author='Mark Blakeney',
    author_email='mark@irsaere.net',
    keywords='vidir',
    license='GPLv3',
    py_modules=[name],
    python_requires='>=3.5',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    data_files=[
        ('share/doc/{}'.format(name), ['README.md']),
    ],
    # Don't use console scripts until woeful startup issue is addressed.
    # See https://github.com/pypa/setuptools/issues/510.
    # entry_points = {
    #     'console_scripts': ['{}={}:main'.format(name, name)],
    # }
    scripts=[name]
)
