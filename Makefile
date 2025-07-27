NAME = $(shell basename $(CURDIR))
PYFILES = $(NAME).py

check::
	ruff check $(PYFILES)
	mypy $(PYFILES)
	pyright $(PYFILES)
	vermin -vv --no-tips -i $(PYFILES)
	md-link-checker

build::
	rm -rf dist
	uv build

upload:: build
	uv-publish

doc::
	update-readme-usage

format::
	ruff check --select I --fix $(PYFILES) && ruff format $(PYFILES)

clean::
	@rm -vrf *.egg-info .venv/ build/ dist/ __pycache__/
