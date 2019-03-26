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

Recommended::

    pip install raiden-contracts


Finding Deployed Contract Instances
-----------------------------------

We do not recommend the smart contracts to be used in production as of this moment. All contracts are WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. Use at your own risk.

You can find other useful constants that you can import in ``raiden_contracts/constants.py``.

.. Note::
    This package supports many contract versions, including:

    * Development ``0.3._`` contracts version (from ``0.3.0`` package release: https://github.com/raiden-network/raiden-contracts/releases/tag/v0.3.0). No limits on the number of tokens registered; has a limit of 100 tokens per channel). Source code: https://github.com/raiden-network/raiden-contracts/tree/fc1c79329a165c738fc55c3505cf801cc79872e4/raiden_contracts/contracts
    * Red Eyes Mainnet ``0.4.0`` contracts version (from ``0.7.0`` package release: https://github.com/raiden-network/raiden-contracts/releases/tag/v0.7.0). Source code: https://github.com/raiden-network/raiden-contracts/tree/fac73623d5b92b7c070fdde2b446648ec9117474/raiden_contracts/contracts
    * current !development version corresponding with the ``master`` branch (might not be stable).

    The current policy is to add all new deployment data together with the sources.

If you want to use the officially deployed contracts, please use the ``raiden_contracts/data_<CONTRACTS_VERSION>`` files to get the precompiled data (ABI, bytecode etc.) and addresses for initializing the contract instances. Alternatively, in Python scripts, with ``raiden-contracts`` package, you can find the already deployed contract instances like::

    from raiden_contracts.contract_manager import (
        ContractManager,
        contracts_precompiled_path,
    )
    from raiden_contracts.constants import (
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        CONTRACT_MONITORING_SERVICE,
        CONTRACTS_VERSION,
        EVENT_TOKEN_NETWORK_CREATED,
    )

    # ``raiden-contracts`` provides ``contracts_version``s like
    # ``0.9.0``, ``'0.4.0'`` and ``'0.3._'``.  They are explained below.

    # Uses the newest test net release available on Kovan, Rinkeby and Ropsten.
    contracts_version = CONTRACTS_VERSION

    # Uses Red Eyes, Mainnet enabled version with deposit limits.
    # The version is also available on Kovan, Rinkeby and Ropsten.
    contracts_version = '0.4.0'

    # Uses the pre-red-eyes development version, probably without
    # deposit limits. Available only on Kovan, Rinkeby and Ropsten.
    # The Solidity source of this version is unknown on Etherscan.
    # See https://github.com/raiden-network/raiden-contracts/issues/543
    contracts_version = '0.3._'

    manager = ContractManager(contracts_precompiled_path(contracts_version))
    compiled_contract_data = manager.get_contract(CONTRACT_TOKEN_NETWORK_REGISTRY)

    deployment_data = get_contracts_deployment_info(int(web3.version.network))
    TOKEN_NETWORK_REGISTRY_ADDRESS = deployment_data['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY].address

    # And then use:
    # compiled_contract_data['abi']
    # compiled_contract_data['bin']
    # TOKEN_NETWORK_REGISTRY_ADDRESS
    # to initialize the contract instance

    # To use one of the 3rd party services contracts:
    compiled_ms_contract = manager.get_contract(CONTRACT_MONITORING_SERVICE)
    deployed_services = get_contracts_deployed(int(web3.version.network), services=True)
    MONITORING_SERVICE_ADDRESS = deployment_data['contracts'][CONTRACT_MONITORING_SERVICE].address

Test-only Contracts
-------------------

All contracts under ``raiden_contracts/contracts/test/`` are only for testing purposes and they should not be used in production.

Development
-----------

If you want to test and further develop outside the officially provided source code, compiled files and deployed addresses, you can do it at your own risk.


If you want to install the package from source::

    make install

To verify that the precompiled ``raiden_contracts/data/contracts.json`` file corresponds to the source code of the contracts::

    make verify_contracts

For development and testing, you have to install additional dependencies::

    pip install -r requirements-dev.txt


Compile the contracts
^^^^^^^^^^^^^^^^^^^^^

Needed if you have made changes to the source code.
Make sure you have `solc` installed: https://solidity.readthedocs.io/en/latest/installing-solidity.html

::

    make compile_contracts


Testing
^^^^^^^

If you want to write tests, check `/raiden_contracts/tests/README.md` first.

::

    # tests
    make render_contracts
    pytest
    pytest raiden_contracts/tests/test_token_network.py

    # Recommended for speed:
    pip install pytest-xdist==1.17.1
    pytest -n NUM_OF_CPUs


If you are using the ``raiden-contracts`` package in your project, you can also test the source code directly (not only the precompiled contract data)::

    from raiden_contracts.contract_manager import (
        ContractManager,
        contracts_source_path,
    )

    manager = ContractManager(contracts_source_path(<CONTRACTS_VERSION>))


Deployment on a testnet
-----------------------

- get the source code from the latest stable release
- install development dependencies::

    pip install -r requirements-dev.txt

.. Note::
    If deploying on your own private chain, you need to start ``geth`` with ``--networkid <chainID_from_genesis.json>``. The private chain must be running the Byzantium protocol (or a later version) at the time of deployment.

    If you want to use a particular version of the contracts that is supported, you can use the ``deploy`` script with ``-- contracts-version "0.4.0"``.

Check deployment options::

    python -m raiden_contracts.deploy --help

Deploying the main Raiden Network contracts with the ``raiden`` command::

    python -m raiden_contracts.deploy raiden --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --gas-limit 6000000 --max-token-networks 1

Deploying the mock token contract for paying for the services (not to be done on the mainnet)::

    python -m raiden_contracts.deploy token --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --token-supply 20000000 --token-name ServiceToken --token-decimals 18 --token-symbol SVT

Deploying the 3rd party service contracts with the ``services`` command::

    python -m raiden_contracts.deploy services --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --gas-limit 6000000 --token-address TOKEN_USED_TO_PAY_SERVICES --user-deposit-whole-limit MAX_TOTAL_AMOUNT_OF_TOKENS_DEPOSITED_IN_USER_DEPOSIT

Deploying a token for testing purposes (please DO NOT use this for production purposes) with the ``token`` command::

    python -m raiden_contracts.deploy token --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --token-supply 10000000 --token-name TestToken --token-decimals 18 --token-symbol TTT

Registering a token with the ``TokenNetworkRegistry`` contract, so it can be used by the Raiden Network, with the ``register`` command::

    python -m raiden_contracts.deploy register --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --token-address TOKEN_TO_BE_REGISTERED_ADDRESS --token-network-registry-address TOKEN_NETWORK_REGISTRY_ADDRESS --channel-participant-deposit-limit 115792089237316195423570985008687907853269984665640564039457584007913129639935 --token-network-deposit-limit 115792089237316195423570985008687907853269984665640564039457584007913129639935

.. Note::
    Registering a token only works once. All subsequent transactions will fail.

Deployment information is stored in a ``deployment_[CHAIN_NAME].json`` file corresponding to the chain on which it was deployed. To verify that the deployed contracts match the compiled data in ``contracts.json`` and also match the deployment information in the file, we can run:

::

    python -m raiden_contracts.deploy verify --rpc-provider http://127.0.0.1:8545

    # Based on the network id, the script verifies the corresponding deployment_[CHAIN_NAME].json file
    # using the chain name-id mapping from constants.py


Verification with Etherscan
^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    python -m raiden_contracts.deploy.etherscan_verify --apikey ETHERSCAN_APIKEY --chain-id 3

If the command exists with status code 0, Etherscan has verified all contracts against Solidity sources.


Making a Release
----------------

See `Release Process Document`_.

.. _Release Process Document: RELEASE.rst

FAQ
---

Why am I seeing many version numbers?
  You are seeing a version number of the PyPI package and several version numbers of smart contract sources.  This same PyPI package provides access to multiple deployments of smart contracts. People use ``raiden-contracts`` PyPI package to interact with a mainnet deployment made a while ago, an older testnet deployment without deposit limits, or a newer testnet deployment with deposit limits and with service contracts.

Why does the same package provide different versions of smart contracts?
  Because a prominent user (``raiden``) is using a single version of this package in order to access different versions of smart contracts.

Are the package version and the smart contract versions related?
  No, not much. The smart contract versions of old deployments (``XYZ`` in ``raiden_contracts/contracts/data_<XYZ>``) never change. The smart contract version of the newest deployment (found in JSON files in ``raiden_contracts/contracts/data/``) sometimes increases with the package version but not always.

Why isn't the newest contract version synced with the package version?
  Just by the historical inertia. We have been using the ``bumpversion`` command in certain ways so that the contract version and the package version go further apart.  There is a `proposal <https://github.com/raiden-network/raiden-contracts/issues/584>`__ to sync smart contract versions to the package version sometimes.

How to find the addresses of deployed contracts?
  Search above for ``get_contracts_deployed`` and see the usage.

How to mint the tokens on the test network?
  Each contract that receives a token has a public variable ``Token public token``.  On the test networks, they might be `CustomToken contract <https://github.com/raiden-network/raiden-contracts/blob/59631b6c8b7bcb0b9a3accdf1fb41082c29dcaa1/raiden_contracts/data/source/test/CustomToken.sol>`__ so you can call ``mint(how_many)`` function of the CustomToken contract to get some new tokens.
