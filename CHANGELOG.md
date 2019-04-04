# Changelog

Documents changes that result in:
- smart contracts redeployment, especially ABI changes
- API changes in the package (externally used constants, externally used utilities and scripts)
- important bug fixes between releases

## Unreleased

## [0.17.2](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.17.2) - 2019-04-06

- [#813](https://github.com/raiden-network/raiden-contracts/pull/813) expose mypy type checking results to the other packages.

## [0.17.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.17.1) - 2019-04-02

- [#809](https://github.com/raiden-network/raiden-contracts/pull/809) fix a bug in `get_contracts_deployment_info()`.

## [0.17.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.17.0) - 2019-03-27

- [#711](https://github.com/raiden-network/raiden-contracts/pull/711) Re-enable setTotalWithdraw() function of TokenNetwork contract.
- [#788](https://github.com/raiden-network/raiden-contracts/pull/788) Fix a bug that prevented deploying 0.3._ TokenNetworks
- [#785](https://github.com/raiden-network/raiden-contracts/pull/785) Require click>=7.0

## [0.16.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.16.0) - 2019-03-26

- [#775](https://github.com/raiden-network/raiden-contracts/pull/775) Added contract_manager.get_contracts_deployed_info() that takes a module (`SERVICES`, `RAIDEN` or `ALL`) instead of `services:bool`
- [#775](https://github.com/raiden-network/raiden-contracts/pull/775) Deprecated get_contracts_deployed() whose name sounded wrong and that had to be called twice.
- [#755](https://github.com/raiden-network/raiden-contracts/pull/755) deploy script does not take --registry option anymore.  Use --token-network-registry instead.

## [0.15.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.15.0) - 2019-03-19

- [#749](https://github.com/raiden-network/raiden-contracts/pull/749) Fixed the problem where Monitoring Services were rewarded too late
- [#741](https://github.com/raiden-network/raiden-contracts/pull/741) Removed raiden_contracts/contracts. Instead, please edit raiden_contracts/data/source directly.

## [0.14.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.14.0) - 2019-03-11

- [#720](https://github.com/raiden-network/raiden-contracts/pull/720) Removed checks in MonitoringService.canMonitor() until the design is determined.
- [#696](https://github.com/raiden-network/raiden-contracts/pull/696) ContractManager created with version=None has contracts_version == None
- [#678](https://github.com/raiden-network/raiden-contracts/pull/678) Add a deployment-time configurable limit on the whole balance of UserDeposit
- [#678](https://github.com/raiden-network/raiden-contracts/pull/678) Deployment script's `service` command takes an additional option `--user-deposit-whole-limit`

## [0.13.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.13.0) - 2019-03-04

- [#655](https://github.com/raiden-network/raiden-contracts/pull/655) Deployment script's `register` command takes two additional options --channel-participant-deposit-limit and --token-network-deposit-limit
- [#655](https://github.com/raiden-network/raiden-contracts/pull/655) TokenNetworkRegistry's createERC20TokenNetwork() function takes two additional arguments `_channel_participant_deposit_limit` and `_token_network_deposit_limit`.
- [#655](https://github.com/raiden-network/raiden-contracts/pull/655) TokenNetwork's constructor takes two additional arguments `_channel_participant_deposit_limit` and `_token_network_deposit_limit`
- [#652](https://github.com/raiden-network/raiden-contracts/pull/652) TokenNetworkRegistry's constructor takes an additional argument `max_number_of_token_networks`
- [#651](https://github.com/raiden-network/raiden-contracts/pull/651) Removed flavors

## [0.12.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.12.0) - 2019-02-28

- Add data/gas.json that contains gas measurements on the development version.
- Move Raiden contracts to "raiden" subdir, so that the imports match the directory layout.
- `contracts_data_path`, `contracts_precompiled_path` and `contracts_gas_path` require an additional `flavor` argument (either `Flavor.Limited` or `Flavor.Unlimited`).
- Started providing Solidity sources next to the deployment data in `raiden_contracts/data`

## [0.11.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.11.0) - 2019-02-14

- Deployed on testnets with a new fake token for service payments.

## [0.10.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.10.1) - 2019-02-13

- [#557](https://github.com/raiden-network/raiden-contracts/pull/557) Revert the new gas measurements

## [0.10.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.10.0) - 2019-02-13

- https://github.com/raiden-network/raiden-contracts/compare/v0.9.0...master
- rename RaidenServiceBundle contract to ServiceRegistry
- [#485](https://github.com/raiden-network/raiden-contracts/pull/485) Add OneToN contract
- [#468](https://github.com/raiden-network/raiden-contracts/pull/468) Remove `raiden-libs` dependency
- [#448](https://github.com/raiden-network/raiden-contracts/pull/448) Add UserDepositContract

## [0.9.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.9.0) - 2019-01-23

- https://github.com/raiden-network/raiden-contracts/compare/v0.8.0...v0.9.0
- various changes in the smart contract comments
- various documentation updates
- internal tests structure updates
- addition of docstrings in the existing tests
- [#426](https://github.com/raiden-network/raiden-contracts/pull/426) Add support for deploying the testnet `0.3._` version (not to be used in production)
- [#407](https://github.com/raiden-network/raiden-contracts/pull/407) Fix bug in deployment that recompiled the contracts
- [#396](https://github.com/raiden-network/raiden-contracts/pull/396) Introducing mypy in Travis builds
- [#379](https://github.com/raiden-network/raiden-contracts/pull/379) [#404](https://github.com/raiden-network/raiden-contracts/pull/404) Removing `raiden-libs` dependency
- [#372](https://github.com/raiden-network/raiden-contracts/pull/372) MSC - Prefix reward hash with "Ethereum Signed Message"
- [#366](https://github.com/raiden-network/raiden-contracts/pull/366) Additional `MonitoringService` `require` check
- [#363](https://github.com/raiden-network/raiden-contracts/pull/363) Refactor equals() function
- [#360](https://github.com/raiden-network/raiden-contracts/pull/360) Update monitoring service to core contracts changes

## [0.8.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.8.0) - 2018-11-12

### Changed

- https://github.com/raiden-network/raiden-contracts/compare/v0.7.0...v0.8.0
- [#345](https://github.com/raiden-network/raiden-contracts/pull/345) Script for verifying contracts with etherscan
- [#348](https://github.com/raiden-network/raiden-contracts/pull/348) Add required gas for creating a `TokenNetwork` in `constants.py`

## [0.7.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.7.0) - 2018-10-25

### Changed

- Red Eyes Bug Bounty Release on Mainnet
- https://github.com/raiden-network/raiden-contracts/compare/v0.6.0...v0.7.0

## [0.6.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.6.0) - 2018-10-17

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.5.0...v0.6.0

## [0.5.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.5.1) - 2018-10-12

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.5.0...v0.5.1

## [0.5.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.5.0) - 2018-10-11

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.4.0...v0.5.0

## [0.4.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.4.1) - 2018-10-05

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.4.0...v0.4.1

## [0.4.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.4.0) - 2018-09-21

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.3.0...v0.4.0

## [0.3.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.3.1) - 2018-09-17

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.3.0...v0.3.1

## [0.3.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.3.0) - 2018-09-07

### Changed

https://github.com/raiden-network/raiden-contracts/compare/v0.2.0...v0.3.0

## [0.2.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.2.0) - 2018-08-10

### Changed

- First python package release
