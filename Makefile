all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

install:
	pip install -r requirements.txt
	pip install -e .

ISORT_PARAMS = --ignore-whitespace --settings-path ./ --recursive raiden_contracts/

lint:
	flake8 raiden_contracts/
	pylint --rcfile .pylint.rc --load-plugins pylint_quotes raiden_contracts/
	isort $(ISORT_PARAMS) --check-only

isort:
	isort $(ISORT_PARAMS)

mypy:
	mypy --ignore-missing-imports --check-untyped-defs raiden_contracts

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
