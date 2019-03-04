all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts
	rm -rf raiden_contracts/data/source
	cp -r raiden_contracts/contracts raiden_contracts/data/source

verify_contracts:
	python setup.py verify_contracts
	diff -r raiden_contracts/contracts raiden_contracts/data/source

install:
	pip install -r requirements.txt
	pip install -e .

ISORT_PARAMS = --ignore-whitespace --settings-path ./ --recursive raiden_contracts/

lint:
	flake8 raiden_contracts/
	pylint --rcfile .pylint.rc raiden_contracts/
	isort $(ISORT_PARAMS) --check-only

isort:
	isort $(ISORT_PARAMS)

mypy:
	mypy --ignore-missing-imports --check-untyped-defs raiden_contracts

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
