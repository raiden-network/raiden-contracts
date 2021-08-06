.PHONY: all compile_contracts verify_contracts install install-dev lint isort black autopep8 format mypy clean release update_gas_costs dist upload-pypi

all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

update_gas_costs:
	pytest "raiden_contracts/tests/test_print_gas.py::test_print_gas" -s

install:
	pip install -r requirements.txt
	pip install -e .

install-dev:
	pip install -U -r requirements-dev.txt
	pip install -e .

LINT_FILES = raiden_contracts/ setup.py

ISORT_PARAMS = --ignore-whitespace --settings-path ./ raiden_contracts/

BLACK_PARAMS = raiden_contracts/

lint: mypy
	black --check --diff $(BLACK_PARAMS)
	flake8 $(LINT_FILES)
	pylint $(LINT_FILES)
	isort $(ISORT_PARAMS) --check-only

mypy:
	mypy $(LINT_FILES)

isort:
	isort $(ISORT_PARAMS)

black:
	black $(BLACK_PARAMS)

format: isort black

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload

dist:
	python setup.py sdist
	python setup.py bdist_wheel

upload-pypi: dist
	twine upload dist/*
