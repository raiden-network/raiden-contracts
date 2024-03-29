Release Process Document
========================

Package Deliverables
^^^^^^^^^^^^^^^^^^^^

For each contract version ``x.y.z``, deliverables are located in ``raiden_contracts/data_x.y.z``.  For the version currently under development, deliverables are located in ``raiden_contracts/data``

Deliverables:

- smart contracts source code from ``raiden_contracts/data*/source``
- compiled contracts data from ``raiden_contracts/data*/contracts.json``
- deployment information from ``raiden_contracts/data*/deployment_*.json``, with Ethereum addresses, transaction data (transaction hash, block number, constructor arguments, gas cost)
- gas costs information from ``raiden_contracts/data*/gas.json``
- scripts for deployment & contract verification on Etherscan from ``raiden_contracts/deploy``
- source code tests from ``raiden_contracts/tests``

Package Release Process
^^^^^^^^^^^^^^^^^^^^^^^

When we want to release another version of the ``raiden-contracts`` package, we need to:


#. `Check if any source code changes have been done <check-source-changes>`_. If no, skip this step. If yes:

   #. `Bump the version on the smart contracts <bump-contracts>`_
   #. `Deploy smart contracts <_deploy-contracts>`_ on all the supported chains and overwrite ``deployment_*,json`` files with the new deployment data.
   #. `Verify the deployed smart contracts on Etherscan <verify-contracts>`_
   #. `Measure Gas Costs <measure-gas>`_
   #. `Create a new data directory <create-new-dir>`_

#. `Update Changelog <change-changelog>`_
#. `Bump the package version <bump-package>`_
#. `Release the new package version <_release-package>`_

.. _check-source-changes:

Check Source Code Changes
-------------------------

First, identify the last release in `the GitHub page <https://github.com/raiden-network/raiden-contracts/releases>`__ and find the corresponding tag in Git.

For a package release, source code changes imply changes in:

**Compiled Data**

The compiled data for all the contracts resides in the ``data/contracts.json`` file.

Now, we do not manually need to check if the compiled data is correct, because this check is included in our Continuous Integration testing. Any source code change forces us to recompile the contracts with ``make compile_contracts``, otherwise our CI tests will fail: https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/raiden_contracts/tests/test_contracts_compilation.py. These tests check:

* if the ``contracts_version`` from ``contracts.json`` matches the current ``CONTRACTS_VERSION``
* if the ``contracts_checksums`` and ``overall_checksum`` from ``contracts.json`` matches the source code checksums, calculated in the test.

**Deployment Data**

Deployment data is kept in the ``data/deployment_[CHAIN_NAME].json`` files.

We **DO** need to manually check whether source code changes have been done since the last release. We should add an automatic check here before releasing (e.g. checking that the ``contracts_version`` here matches the one from ``data/contracts.json``)


.. _bump-contracts:

Bump Smart Contracts Version
----------------------------

* Edit the version located here:
  * ``CONTRACTS_VERSION`` https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/raiden_contracts/constants.py#L4
* We are currently at a ``0.*`` version. Our first ``major`` bump will be made when a stable, not-limited version will be released on the main net.
* ``minor`` bumps are made for any contract changes. A modified comment counts as a contract change. The new version should match the next package version.
* ``patch`` bumps are never used.

.. _deploy-contracts:

Deploy Smart Contracts
----------------------

Instructions for deploying the contracts can be found at https://github.com/raiden-network/raiden-contracts#deployment-on-a-testnet, using the ``python -m raiden_contracts.deploy`` script.
We currently deploy on:

* Ropsten - for all releases
* Rinkeby - for all releases
* Kovan - for all releases
* Görli - for all releases
* Mainnet - only for pre-major or major releases


**Checking Validity of deployment_*.json Data**

We have checks for:

* ``contracts_version``: https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/raiden_contracts/deploy/__main__.py#L503
* ``chain_id``: https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/raiden_contracts/deploy/__main__.py#L504
* deployment addresses & transaction data for each contract, checked against the chain we are running the script on

These checks are performed at the end of the deployment script. They can also be run independently with ``python -m raiden_contracts.deploy verify``, as described in the above link.

We also have CI tests that check whether the deployment data returned by the deployment script contains all necessary information, for all the contracts we need to deploy: https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/raiden_contracts/tests/test_deploy_script.py.

.. _verify-contracts:

Etherscan Verification
----------------------

Etherscan verification is documented here: https://github.com/raiden-network/raiden-contracts#verification-with-etherscan.

.. _measure-gas:

Measure Gas Costs
-----------------

``raiden_contracts`` package provides ``data/gas.json`` showing the amount of gas that each operation requires. A ``pytest`` execution updates the JSON file:

::

    make update_gas_costs

.. _create-new-dir

Create a New Data Directory
---------------------------

Copy ``data`` directory into ``data_x.y.z`` where ``x.y.z`` is the contract version.  Also, edit ``data_x.y.z/contracts.json`` to change ``contracts_version`` from ``null`` to ``x.y.z``.

.. _change-changelog:

Change the Versions of CHANGELOG.md
-----------------------------------

* Make sure all significant changes from the last release are listed.
* Turn the existing ``Unreleased`` section into a new release section.

.. _bump-package:

Bump Package Version
--------------------

Before bumping the package version, ``git add`` the deployment data at ``data/deployment_[CHAIN_NAME].json``. Also make sure ``MANIFEST.in`` contains all the deployment JSON files.  Then run

::

    bump2version --config-file ./.bumpversion.cfg [PART]

``[PART]`` can be ``major``, ``minor``, ``patch``.

* The script changes the version located here:
  * ``VERSION`` https://github.com/raiden-network/raiden-contracts/blob/9fd2124eb648a629aee886f37ade5e502431371f/setup.py#L15
* We are currently at a ``0.*`` version. Our first ``major`` bump will be made when a stable, not-limited version will be released on the main net.
* for now, ``minor`` bumps are done if contracts_version changes.
* ``patch`` bumps are made for any other fix

This command triggers a commit and a local tag is created. A PR must be made with the commit changes.

.. _release-package:

Upload Package to PyPI
----------------------

Use `make upload-pypi` to build the python packages and upload them to PyPI. You will need access to the project at https://pypi.org/project/raiden-contracts/.
