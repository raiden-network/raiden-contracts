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

## Deployment on a testnet

! You need to have the compiled contract data first. You can run `populus compile` for that.

```
# Following calls are equivalent

python -m deploy

python -m deploy \
       --rpc-provider http://127.0.0.1:8545 \
       --json build/contracts.json
       --owner 0x5601Ea8445A5d96EEeBF89A67C4199FbB7a43Fbb \
       --wait 300 \
       --token-name CustomToken --token-symbol TKN \
       --supply 10000000 --token-decimals 18

# Provide a custom deployed token
python -m deploy --token-address <TOKEN_ADDRESS>

```

## Use

```
populus compile

# tests
pytest
pytest -p no:warnings -s
pytest raiden_contracts/tests/test_token_network.py -p no:warnings -s

# Recommended for speed:
pip install pytest-xdist==1.17.1
pytest -p no:warnings -s -n NUM_OF_CPUs

```
