all: verify_contracts install

compile_contracts:
	python setup.py compile_contracts

verify_contracts:
	python setup.py verify_contracts

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	flake8 raiden_contracts/

clean:
	rm -rf build/ *egg-info/ dist .eggs

release: clean verify_contracts
	python setup.py sdist bdist_wheel upload
