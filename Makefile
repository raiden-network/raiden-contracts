.PHONY: all compile_contracts verify_contracts install lint isort black format mypy clean release

all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

install:
	pip install -r requirements.txt
	pip install -e .

ISORT_PARAMS = --ignore-whitespace --settings-path ./ --recursive raiden_contracts/

BLACK_PARAMS = --line-length 99 raiden_contracts/

lint:
	black --check $(BLACK_PARAMS)
	flake8 raiden_contracts/
	pylint --rcfile .pylint.rc --load-plugins pylint_quotes raiden_contracts/
	isort $(ISORT_PARAMS) --check-only

isort:
	isort $(ISORT_PARAMS)

black:
	black $(BLACK_PARAMS)

format: isort black

mypy:
	mypy --ignore-missing-imports --check-untyped-defs raiden_contracts

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
