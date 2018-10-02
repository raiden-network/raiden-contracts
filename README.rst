Raiden Network Smart Contracts
==============================

.. image:: https://badges.gitter.im/Join%20Chat.svg
    :target: https://gitter.im/raiden-network/raiden?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
    :alt: Chat on Gitter

`Raiden Network Smart Contract specs`_

.. _Raiden Network Smart Contract specs: https://raiden-network-specification.readthedocs.io/en/latest/smart_contracts.html

Prerequisites
-------------

-  Python 3.6
-  https://pip.pypa.io/en/stable/

Installation
------------

::

    make install


Deployment on a testnet
-----------------------

::

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


Development
-----------

::

    pip install -r requirements-dev.txt


Compile the contracts
^^^^^^^^^^^^^^^^^^^^^

::

    python setup.py build


Testing
^^^^^^^

::

    # tests
    pytest
    pytest raiden_contracts/tests/test_token_network.py

    # Recommended for speed:
    pip install pytest-xdist==1.17.1
    pytest -n NUM_OF_CPUs
