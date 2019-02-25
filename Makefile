all: verify_contracts install

render_templates:
	rm -rf raiden_contracts/contracts
	cp -r raiden_contracts/contracts_template raiden_contracts/contracts

compile_contracts: render_templates
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

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
