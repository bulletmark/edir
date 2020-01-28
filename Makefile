# Copyright (C) 2016 Mark Blakeney. This program is distributed under
# the terms of the GNU General Public License.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or any
# later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License at <http://www.gnu.org/licenses/> for more
# details.

NAME = edir

DOC = README.md
DOCOUT = $(DOC:.md=.html)

all:
	@echo "Type sudo make install|uninstall"
	@echo "or make sdist|upload|doc|check|clean"

install:
	pip3 install .

uninstall:
	pip3 uninstall $(NAME)

sdist:
	python3 setup.py sdist

upload: sdist
	twine3 upload dist/*

doc:	$(DOCOUT)

$(DOCOUT): $(DOC)
	markdown $< >$@

check:
	flake8 $(NAME).py $(NAME) setup.py
	vermin -i -q --no-tips $(NAME).py $(NAME) setup.py

clean:
	@rm -vrf $(DOCOUT) *.egg-info build/ dist/ __pycache__/
