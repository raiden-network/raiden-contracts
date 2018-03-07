# raiden-contracts

## Prerequisites


-  Python 3.6
-  https://pip.pypa.io/en/stable/

## Installation

`make`

or:
```
pip install -r requirements.txt

```

## Use

```
populus compile

# tests
pytest
pytest -p no:warnings -s
pytest tests/test_token_network.py -p no:warnings -s

# Recommended for speed:
pip install pytest-xdist==1.17.1
pytest -p no:warnings -s -n NUM_OF_CPUs

```
