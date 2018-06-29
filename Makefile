all: compile_contracts install

compile_contracts:
	python setup.py build

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	flake8 raiden_contracts/

clean:
	rm -rf build/ *egg-info/ raiden_contracts/data/contracts.json dist
