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
        get_contracts_deployment_info,
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

    deployment_data = get_contracts_deployment_info(web3.eth.chainId)
    TOKEN_NETWORK_REGISTRY_ADDRESS = deployment_data['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY].address

    # And then use:
    # compiled_contract_data['abi']
    # compiled_contract_data['bin']
    # TOKEN_NETWORK_REGISTRY_ADDRESS
    # to initialize the contract instance

    # To use one of the 3rd party services contracts:
    compiled_ms_contract = manager.get_contract(CONTRACT_MONITORING_SERVICE)
    deployed_services = get_contracts_deployed(web3.eth.chainId, services=True)
    MONITORING_SERVICE_ADDRESS = deployment_data['contracts'][CONTRACT_MONITORING_SERVICE].address

Looking Up Gas Consumption
--------------------------

Each ``contracts_version`` (at least ``0.8.0``) comes with gas consumption measurements::

    gas = gas_measurements(contracts_version)
    gas["TokenNetwork.setTotalDeposit"]

evaluates to something like 45000.


Test-only Contracts
-------------------

All contracts under ``raiden_contracts/contracts/test/`` are only for testing purposes and they should not be used in production.

Development
-----------

If you want to test and further develop outside the officially provided source code, compiled files and deployed addresses, you can do it at your own risk.


If you want to install the package from source::

    make install-dev

To verify that the precompiled ``raiden_contracts/data/contracts.json`` file corresponds to the source code of the contracts::

    make verify_contracts


Compile the contracts
^^^^^^^^^^^^^^^^^^^^^

Needed if you have made changes to the source code.
Make sure you have `solc` installed: https://solidity.readthedocs.io/en/latest/installing-solidity.html

::

    make compile_contracts


Updating gas costs
^^^^^^^^^^^^^^^^^^

To update the gas costs run

::

    make update_gas_costs


Testing
^^^^^^^

If you want to write tests, check `/raiden_contracts/tests/README.md` first.

::

    # tests
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

When the ``raiden`` command takes an optional argument ``--secret-registry-from-deployment-file <deployment-file>``, the command tries to reuse ``SecretRegistry`` instance found in ``<deployment-file>``.  For example, some deployment files are found under ``raiden_contracts/data*/deployment_*.json``.

Deploying the mock token contract for paying for the services (not to be done on the mainnet)::

    python -m raiden_contracts.deploy token --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --token-supply 20000000 --token-name ServiceToken --token-decimals 18 --token-symbol SVT

Deploying the 3rd party service contracts with the ``services`` command::

    python -m raiden_contracts.deploy services --rpc-provider http://127.0.0.1:8545 --private-key /path/to/your/private_key/file --gas-price 10 --gas-limit 6000000 --token-address TOKEN_USED_TO_PAY_SERVICES --user-deposit-whole-limit MAX_TOTAL_AMOUNT_OF_TOKENS_DEPOSITED_IN_USER_DEPOSIT --service-deposit-bump-numerator NUMERATOR_OF_PRICE_DUMP --service-deposit-bump-denominator DENOMINATOR_OF_PRICE_DUMP --service-deposit-decay-constant DECAY_CONSTANT --initial-service-deposit-price INITIAL_PRICE --service-deposit-min-price MIN_PRICE --service-registration-duration REGISTRATION_DURATION_IN_SECS --token-network-registry-address TOKEN_NETWORK_REGISTRY_ADDRESS

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


Utilities for minting, balance checking, token transfer
-------------------------------------------------------
You can mint tokens from a CustomToken contract, WETH contract from any testnet
and query balances from the commandline using the ``token_ops.py``
Sample usage

* Minting tokens ::

   python token_ops.py mint --rpc-url http://127.0.0.1:8545 --private-key ~/priv_chain/blkchain1/keystore/private_net_address --token-address 0x2feEd0E54238051dddCc01bF3960B143e887a9B7 --amount 1000

* Minting tokens with a password file ::

   python token_ops.py mint --rpc-url https://rpc.slock.it/goerli --private-key ~/.ethereum/keystore/UTC--2019-04-25T07-10-37.872928741Z--f8608ad00ab66b3a2aa21253c7915413034d0be5 --password ~/.ethereum/keystore/passwd_F8608A.txt --token-address 0x610f3c3C1998FAd6A659A9f5Bb83962DA27eAf1d --amount 1000

* Getting weth tokens ::

   python token_ops.py weth --rpc-url http://127.0.0.1:8545 --private-key ~/priv_chain/blkchain1/keystore/private_net_address --token-address 0xdf048aa8cbA44f9590F888BAb5e5AC78AAb503C8 --amount 1000

* Query account balance in any token ::

   python token_ops.py balance --rpc-url http://127.0.0.1:8545 --token-address 0xdf048aa8cbA44f9590F888BAb5e5AC78AAb503C8 --address 0xb8eb60F2E45667c9B2cFf861b82656452659C6dE

* Transfer tokens ::

   python token_ops.py transfer --rpc-url http://127.0.0.1:8545 --private-key ~/priv_chain/blkchain1/keystore/private_net_address --token-address 0xdf048aa8cbA44f9590F888BAb5e5AC78AAb503C8 --amount 1000 --destination 0x7ba5f1c08548f80d52856c21e87fcca05c5e40e3


Making a Release
----------------

See `Release Process Document`_.

.. _Release Process Document: RELEASE.rst


Directory Structure
-------------------

- `raiden_contracts`
    - `contracts`
        - `lib` - libraries used by core contracts
        - `services` - contains 3rd party services contracts
        - `test` - test contracts used to test core contracts
        - raiden core contracts files
    - `data` - compiled contracts data & deployment information
    - `data_0.3._` - compiled contracts data & deployment information for an older version with only a channel limit of 100 tokens
    - `data_0.4.0` - compiled contracts data & deployment information for Red Eyes release
    - `data_0.x.y` - compiled contracts data & deployment information only for test nets
    - `deploy` - deployment & verification scripts
    - `tests`
        - `fixtures` - fixtures used by all tests
        - `property` - property tests for core contracts
        - `unit` - unit tests for internal functions in core contracts
        - `utils` - specific utilities for tests, closely related to the contracts logic
        - main test files for both core & service contracts
    - `utils`
        - general utilities for tests (signing, merkle trees, logs), independent of the contracts logic
        - some utilities related to the contracts logic that might be exported by projects using the package
    - `constants.py` - package deliverable, constants used by projects that import the package
    - `contract_manager.py` - package deliverable, used by projects that import the package, gets the correct compiled contracts data based on version
- setup files for requirements, builds etc.


FAQ
---

Why am I seeing many version numbers?
  You are seeing a version number of the PyPI package and several version numbers of smart contract sources.  This same PyPI package provides access to multiple deployments of smart contracts. People use ``raiden-contracts`` PyPI package to interact with a mainnet deployment made a while ago, an older testnet deployment without deposit limits, or a newer testnet deployment with deposit limits and with service contracts.

Why does the same package provide different versions of smart contracts?
  Because a prominent user (``raiden``) uses a single version of this package. They might one day start using multiple TokenNetwork deployments from multiple contracts versions.

Are the package version and the smart contracts versions related?
  Yes, especially since package version 0.33.3. Whenever there is a new contracts version, the package version and the contracts version get a minor upgrade (Y increases in 0.Y.Z), and they look similar. When a package upgrade only contains Python changes, the package version only gets a patch upgrade (Z increases in 0.Y.Z).

How to find the addresses of deployed contracts?
  Search above for ``get_contracts_deployed`` and see the usage.

How to mint the tokens on the test network?
  Each contract that receives a token has a public variable ``Token public token``.  On the test networks, they might be `CustomToken contract <https://github.com/raiden-network/raiden-contracts/blob/59631b6c8b7bcb0b9a3accdf1fb41082c29dcaa1/raiden_contracts/data/source/test/CustomToken.sol>`__ so you can call ``mint(how_many)`` function of the CustomToken contract to get some new tokens.

I see ``block gas exceeded``
  Perhaps you've added ``--gas-limit`` option with a too big integer. Try dropping the option.
