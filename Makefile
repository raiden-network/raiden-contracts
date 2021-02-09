.PHONY: all compile_contracts verify_contracts install install-dev lint isort black autopep8 format mypy clean release update_gas_costs

all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

update_gas_costs:
	pytest "raiden_contracts/tests/test_print_gas.py::test_print_gas" -s

install:
	pip install --use-deprecated=legacy-resolver -r requirements.txt
	pip install --use-deprecated=legacy-resolver -e .

install-dev:
	pip install --use-deprecated=legacy-resolver -U -r requirements-dev.txt
	pip install --use-deprecated=legacy-resolver -e .

LINT_FILES = raiden_contracts/ setup.py

ISORT_PARAMS = --ignore-whitespace --settings-path ./ raiden_contracts/

BLACK_PARAMS = --line-length 99 raiden_contracts/

lint: mypy solium
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

autopep8:
	autopep8 --in-place --recursive raiden_contracts/

format: autopep8 isort black

solium:
	command -v solium > /dev/null  || { echo 'solium not installed, skipping'; exit 0; }; solium -d raiden_contracts/data/source/

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
