# Raiden Network Smart Contracts Tests

## Current Package Structure:

- `raiden_contracts`
    - `contracts`
        - `lib` - libraries used by core contracts
        - `services` - contains 3rd party services contracts
        - `test` - test contracts used to test core contracts
        - raiden core contracts files
    - `data` - compiled contracts data & deployment information
    - `data_0.3._` - compiled contracts data & deployment information for an older version with only a channel limit of 100 tokens
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


## Writing Tests

- when implementing a new feature or changing code, make sure your PR also contains tests that cover the changes.
- always think about edge cases, go over each Solidity source code line that was changed in your PR and make sure a test covers it if needed.
- don’t only test the happy case. If you don't have `with pytest.raises():` in your tests, something is wrong


### How to Start Testing a Contract

- create a `test_contract_name.py` test file for testing the constructor & all public variables for that contract (including the version) - see [TokenNetwork tests](/raiden_contracts/tests/test_token_network.py)
- if the contract is big - create multiple `test_contract/[contract]_contract_function_name.py` test files for testing each contract function separately. E.g. `test_channel_open.py` (we don't have the contract name here, but we have `channel`, which is specific enough)

#### Testing the Constructor & Contract Public Variables

- have a version test. E.g. [test_version](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_token_network.py#L16)
- test `TypeErrors` - make sure your constructor receives the intended number of arguments, of the intended type. E.g. [test_constructor_call](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_token_network.py#L20) for the `TokenNetwork` contract.
- check that all public contract variables indeed have `public` access. E.g. [test_constructor_call_state](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_token_network_registry.py#L84) from the `TokenNetworkRegistry` contract

#### Testing a Function

Tests usually follow this order when writing them in a file:

- test `TypeErrors` - make sure your function receives the intended number of arguments, of the intended type. E.g. [test_open_channel_call](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_channel_open.py#L25)
- go through each line of code and see wether a test can be written to cover it. E.g. for this line `channel_counter += 1;` in [TokenNetwork.openChannel](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/contracts/TokenNetwork.sol#L267), this [test_counter](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_channel_open.py#L75) was added
- `test_function_name_state` - always exists and tests the contract state for when the function is successful (no `pytest.raises`, but much `assert`):
    - pre-call tests for all contract state variables that are related, all  related getter functions
    - post-call tests for all contract state variables that are related, all  related getter functions, comparing to the pre-call ones
    - E.g. [test_open_channel_state](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_channel_open.py#L152)
    - some of these checks are written as fixtures and reused by tests. You can find them in [fixtures/channel.py](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/fixtures/channel.py) E.g. [common_settle_state_tests](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/fixtures/channel.py#L271)
- tests for each event. E.g. [test_open_channel_event](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_channel_open.py#L315)

#### State Fixtures

- usually, for testing some contract functions, the contract needs to be in a specific state. There are fixtures that provide the state that we need. E.g. for [testing channel deposits](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/test_channel_deposit.py#L225), we first need to [create_channel](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/fixtures/channel.py#L33). These helper fixtures can be found in [fixtures/channel.py](https://github.com/raiden-network/raiden-contracts/blob/5189111e4528004b43b8090a6603e6a68de2202e/raiden_contracts/tests/fixtures/channel.py)
