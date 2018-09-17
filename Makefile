all: compile_contracts install

compile_contracts:
	python setup.py build

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	flake8 raiden_contracts/

clean:
	rm -rf build/ *egg-info/ raiden_contracts/data/contracts.json.gz dist .eggs

release: clean
	RAIDEN_SOLC_REQUIRED=1 python setup.py sdist bdist_wheel upload
