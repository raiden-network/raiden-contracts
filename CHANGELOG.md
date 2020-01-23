# Changelog

Documents changes that result in:
- smart contracts redeployment, especially ABI changes
- API changes in the package (externally used constants, externally used utilities and scripts)
- important bug fixes between releases

## [0.35.0]

- No code changes, just different parameters for testnet deployments than in
  0.34. Settings are the same as in the 0.33 deployments, again.

## [0.34.0]

- [#1318](https://github.com/raiden-network/raiden-contracts/pull/1318) add `make install-dev`.
- [#1350](https://github.com/raiden-network/raiden-contracts/pull/1350) remove support for deploying unlimited contracts

## [0.33.3](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.33.3) - 2019-10-24

- [#1313](https://github.com/raiden-network/raiden-contracts/pull/1313) fix deployment using --contracts-version CONTRACT_VERSION, even when ``data`` and ``data_CONTRACTS_VERSION`` contain different sources
- [#1299](https://github.com/raiden-network/raiden-contracts/pull/1299) fix consistency of data_0.25.2
- [#1306](https://github.com/raiden-network/raiden-contracts/pull/1306) move data_0.25.2 to data_0.33.0

## [0.33.2](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.33.2) - 2019-10-17

- [#1296](https://github.com/raiden-network/raiden-contracts/pull/1296) re-deploy service contracts
- [#1296](https://github.com/raiden-network/raiden-contracts/pull/1296) removed Kovan deployment files (perhaps people don't use them)

## [0.33.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.33.1) - 2019-10-15

- [#1288](https://github.com/raiden-network/raiden-contracts/pull/1288) fix MANIFEST.in
- More keyword arguments in Python scripts

## [0.33.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.33.0) - 2019-10-12

- [#1260](https://github.com/raiden-network/raiden-contracts/pull/1260) Simplify the usage of ContractSourceManager. Users don't need to call compute_checksums() to initialize the object.
- Some refactoring and typo fixes.

## [0.32.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.32.0) - 2019-09-25

- The minimum settlement window is now shorter (20 blocks) on test networks.
- [#1213](https://github.com/raiden-network/raiden-contracts/pull/1213) etherscan_verify.py now fails when a source imports a nonexistent file.
- Add many tests
- [#1205](https://github.com/raiden-network/raiden-contracts/pull/1205) When ServiceRegistry creates a new Deposit, ServiceRegistry asserts that the deadline is in the future.
- [#1238](https://github.com/raiden-network/raiden-contracts/pull/1238) Reward Proof now contains ``non_closing_address`` that goes together with ``non_closing_signature``.

## [0.31.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.31.0) - 2019-08-20

- [#1163](https://github.com/raiden-network/raiden-contracts/pull/1163) MonitoringService.monitor() no longer works for service providers that are not registered in ServiceRegistry
- [#1177](https://github.com/raiden-network/raiden-contracts/pull/1177) When ServiceRegistry is deprecated, deposits can be immediately be withdrawn.

## [0.30.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.30.0) - 2019-08-15

- [#1150](https://github.com/raiden-network/raiden-contracts/pull/1150) Use different message ID for chnanelClose() and updateNonClosingBalanceProof()
- [#1148](https://github.com/raiden-network/raiden-contracts/pull/1148) Add TokenNetworkRegistry's address to MonitoringService's constructor arguments
- [#1160](https://github.com/raiden-network/raiden-contracts/pull/1160) Revert the upgrade web3.py and other dependencies
- [#1151](https://github.com/raiden-network/raiden-contracts/pull/1151) OneToN doesn't work for service providers not registered in ServiceRegistry

## [0.29.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.29.1) - 2019-08-13

- [#1153](https://github.com/raiden-network/raiden-contracts/pull/1153) Upgrade web3.py and other dependencies

## [0.29.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.29.0) - 2019-07-26

- [#1143](https://github.com/raiden-network/raiden-contracts/pull/1143) Add ServiceRegistry.hasValidRegistration() function that returns whether a given address has a valid registration.

## [0.28.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.28.0) - 2019-07-26

- [#1140](https://github.com/raiden-network/raiden-contracts/pull/1140) ServiceRegistry exposes the list of addresses that have made deposits

## [0.27.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.27.0) - 2019-07-23

- [#1136](https://github.com/raiden-network/raiden-contracts/pull/1136) ServiceRegistry has a deprecation switch.
- [#1132](https://github.com/raiden-network/raiden-contracts/pull/1132) ServiceRegistry has a controller that can change parameters.
- [#1116](https://github.com/raiden-network/raiden-contracts/pull/1116) ServiceRegistry's required deposit changes dynamically.
- [#1124](https://github.com/raiden-network/raiden-contracts/pull/1124) TokenNetwork's closeChannel() can be called by anybody on behalf of the closing participant.
- [#1118](https://github.com/raiden-network/raiden-contracts/pull/1118) TokenNetwork's ChannelClosed and NonClosingBalanceProofUpdated events contain balance_hash from the submitted balance proofs.
- [#1126](https://github.com/raiden-network/raiden-contracts/pull/1126) TokenNetwork's ChannelSettled event contains locksroots of the two sets of pending transfers.

## [0.26.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.26.0) - 2019-07-11

- [#1119](https://github.com/raiden-network/raiden-contracts/pull/1119) Changed the signature construction of monitoring reward proof so that a signature covers the whole reward proof
- [#1108](https://github.com/raiden-network/raiden-contracts/pull/1108) Added a new event DeprecationSwitch to TokenNetwork

## [0.25.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.25.1) - 2019-07-03

- [#1101](https://github.com/raiden-network/raiden-contracts/pull/1101) Add more gas measurements about CustomToken calls

## [0.25.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.25.0) - 2019-07-03

- [#1103](https://github.com/raiden-network/raiden-contracts/pull/1103) Add `expiration_block` argument to `TokenNetwork.setTotalWithdraw()`.
- [#1099](https://github.com/raiden-network/raiden-contracts/pull/1099) Remove `raiden_contracts.constants.GAS_REQUIRED_FOR*` constants. Use instead `raiden_contracts.contract_manager.gas_measurements()`.
- [#1079](https://github.com/raiden-network/raiden-contracts/pull/1079) Measure gas consumption of CustomToken.mint()
- [#1050](https://github.com/raiden-network/raiden-contracts/pull/1050) MonitoringService.claimReward() returns a boolean as the signature says

## [0.24.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.24.0) - 2019-06-19

- [#1023](https://github.com/raiden-network/raiden-contracts/pull/1023) Remove `contract_version` variable from the contracts
- [#1070](https://github.com/raiden-network/raiden-contracts/pull/1070) Type-annotate `ChainID`s

## [0.23.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.23.0) - 2019-06-07

- [#1013](https://github.com/raiden-network/raiden-contracts/pull/1013) Remove EndpointRegistry contract
- [#1024](https://github.com/raiden-network/raiden-contracts/pull/1024) When OneToN checks the signature of an IOU, it considers MessageTypeId.IOU
- [#1062](https://github.com/raiden-network/raiden-contracts/pull/1062) Stopped using Merkle trees; instead the concatenation of all submitted locks is hashed
- [#1043](https://github.com/raiden-network/raiden-contracts/pull/1062) This Changelog is supposed to appear in the package

## [0.22.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.22.0) - 2019-06-03

- [#1034](https://github.com/raiden-network/raiden-contracts/pull/1034) Add gas.json in the package so `gas_measurements(contracts_version)` works.
- [#1025](https://github.com/raiden-network/raiden-contracts/pull/1025) MonitoringService.monitor() takes a signature that takes in the message ID.

## [0.21.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.21.0) - 2019-05-28

- [#1027](https://github.com/raiden-network/raiden-contracts/pull/1027) Add `gas_measurements(contracts_version)` that shows the gas measurements as a dictionary.
- [#988](https://github.com/raiden-network/raiden-contracts/pull/988) Unlock-related functions' and events' arguments are renamed into `sender` and `receiver`

## [0.20.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.20.0) - 2019-05-17

- [#979](https://github.com/raiden-network/raiden-contracts/pull/979) Start using SHA256 for the hashlock.
- [#979](https://github.com/raiden-network/raiden-contracts/pull/979) Start accepting zero as the secret.

## [0.19.1](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.19.1) - 2019-05-14

- [#973](https://github.com/raiden-network/raiden-contracts/pull/973) Stop forcing a development-time dependency during the usual installation

## [0.19.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.19.0) - 2019-05-09

- [#909](https://github.com/raiden-network/raiden-contracts/pull/909) MonitoringService prioritizes services
- [#853](https://github.com/raiden-network/raiden-contracts/pull/853) add chain_id in the IOU claims for OneToN
- [#928](https://github.com/raiden-network/raiden-contracts/pull/928) [#956](https://github.com/raiden-network/raiden-contracts/pull/956) black formatter is enabled
- [#896](https://github.com/raiden-network/raiden-contracts/pull/896) [#941](https://github.com/raiden-network/raiden-contracts/pull/941) Some Python code cleanup
- [#867](https://github.com/raiden-network/raiden-contracts/pull/867) get_contracts_deployment_info() returns None instead of raising a ValueError when no deployment file is found.
- [#863](https://github.com/raiden-network/raiden-contracts/pull/863) Deploy 0.4.0 version on Goerli

## [0.18.0](https://github.com/raiden-network/raiden-contracts/releases/tag/v0.18.0) - 2019-04-12

- [#831](https://github.com/raiden-network/raiden-contracts/pull/831) Add contracts_version=0.11.1 that includes Görli deployment

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
