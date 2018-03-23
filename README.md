# raiden-contracts

## Prerequisites


-  Python 3.6
-  https://pip.pypa.io/en/stable/

## Installation

```
make install
```

## Deployment on a testnet


```
# Following calls are equivalent

python -m deploy

python -m deploy \
       --rpc-provider http://127.0.0.1:8545 \
       --json raiden_contracts/data/contracts.json
       --owner 0x5601Ea8445A5d96EEeBF89A67C4199FbB7a43Fbb \
       --wait 300 \
       --token-name CustomToken --token-symbol TKN \
       --supply 10000000 --token-decimals 18

# Provide a custom deployed token
python -m deploy --token-address <TOKEN_ADDRESS>

```

## Development

We use `populus` for development. At the moment, this library is incompatible with recent libraries that act as dependencies. Therefore, we have to use different environments here.

```bash
pip install -r requirements-dev.txt
```

After you are finished, to uninstall `populus` and install the dependencies for the `raiden-contracts` package, you can do:

```
pip freeze  | xargs pip uninstall -y
pip install -r requirements.txt

```

### Compile the contracts

```
python setup.py build
```

### Testing

```
# tests
pytest
pytest -p no:warnings -s
pytest raiden_contracts/tests/test_token_network.py -p no:warnings -s

# Recommended for speed:
pip install pytest-xdist==1.17.1
pytest -p no:warnings -s -n NUM_OF_CPUs

```
