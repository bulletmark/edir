NAME = $(shell basename $(CURDIR))
PYNAME = $(subst -,_,$(NAME))

check:
	ruff $(PYNAME).py
	flake8 $(PYNAME).py
	mypy $(PYNAME).py
	pyright $(PYNAME).py
	vermin --no-tips -i $(PYNAME).py setup.py

build:
	rm -rf dist
	python3 -m build

upload: build
	twine3 upload dist/*

doc:
	update-readme-usage

clean:
	@rm -vrf *.egg-info .venv/ build/ dist/ __pycache__/
