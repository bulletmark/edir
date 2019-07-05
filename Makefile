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

DOC = README.md

NAME = edir
DOCOUT = $(DOC:.md=.html)

all:
	@echo "Type sudo make install|uninstall, or make doc|check|clean"

install:
	@python setup.py install --root=$(or $(DESTDIR),/) --optimize=1

uninstall:
	@rm -vrf $(DESTDIR)/usr/bin/$(NAME)* $(DESTDIR)/etc/$(NAME).conf \
	    $(DESTDIR)/usr/share/doc/$(NAME) \
	    $(DESTDIR)/usr/lib/python*/site-packages/*$(NAME)* \
	    $(DESTDIR)/usr/lib/python*/site-packages/*/*$(NAME)*

sdist:
	python3 setup.py sdist

upload: sdist
	twine upload dist/*

doc:	$(DOCOUT)

check:
	flake8 $(NAME).py $(NAME) setup.py

$(DOCOUT): $(DOC)
	markdown $< >$@

clean:
	@rm -vrf $(DOCOUT) *.egg-info build/ dist/ __pycache__/
