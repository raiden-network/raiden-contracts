all: verify_contracts install

render_templates:
	python setup.py render_templates

compile_contracts: render_templates
	python setup.py compile_contracts
	rm -rf raiden_contracts/data/source raiden_contracts/data_unlimited/source
	cp -r raiden_contracts/contracts raiden_contracts/data/source
	cp -r raiden_contracts/contracts_without_limits raiden_contracts/data_unlimited/source

verify_contracts: render_templates
	python setup.py verify_contracts
	diff -r raiden_contracts/contracts raiden_contracts/data/source

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	flake8 raiden_contracts/

mypy:
	mypy --ignore-missing-imports --check-untyped-defs raiden_contracts

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
