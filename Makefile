.PHONY: all compile_contracts verify_contracts install install-dev lint isort black autopep8 format mypy clean release update_gas_costs

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
	pip install -r requirements-dev.txt
	pip install -e .

ISORT_PARAMS = --ignore-whitespace --settings-path ./ --recursive raiden_contracts/

BLACK_PARAMS = --line-length 99 raiden_contracts/

lint:
	black --check --diff $(BLACK_PARAMS)
	flake8 raiden_contracts/
	pylint raiden_contracts/
	mypy raiden_contracts
	isort $(ISORT_PARAMS) --check-only

isort:
	isort $(ISORT_PARAMS)

black:
	black $(BLACK_PARAMS)

autopep8:
	autopep8 --in-place --recursive raiden_contracts/

format: autopep8 isort black

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
