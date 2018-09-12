pragma solidity ^0.4.23;

import "raiden/Utils.sol";
import "raiden/Token.sol";
import "raiden/TokenNetwork.sol";


/// @title TokenNetworkRegistry
/// @notice The TokenNetwork Registry deploys new TokenNetwork contracts for the
/// Raiden Network protocol.
contract TokenNetworkRegistry is Utils {

    string constant public contract_version = "0.3._";
    address public secret_registry_address;
    uint256 public chain_id;
    uint256 public settlement_timeout_min;
    uint256 public settlement_timeout_max;

    // Only for the limited Bug Bounty release
    address public deprecation_executor;

    // Token address => TokenNetwork address
    mapping(address => address) public token_to_token_networks;

    event TokenNetworkCreated(address indexed token_address, address indexed token_network_address);

    modifier onlyDeprecationExecutor() {
        require(msg.sender == deprecation_executor);
        _;
    }

    constructor(
        address _secret_registry_address,
        uint256 _chain_id,
        uint256 _settlement_timeout_min,
        uint256 _settlement_timeout_max
    )
        public
    {
        require(_chain_id > 0);
        require(_settlement_timeout_min > 0);
        require(_settlement_timeout_max > 0);
        require(_settlement_timeout_max > _settlement_timeout_min);
        require(_secret_registry_address != address(0x0));
        require(contractExists(_secret_registry_address));
        secret_registry_address = _secret_registry_address;
        chain_id = _chain_id;
        settlement_timeout_min = _settlement_timeout_min;
        settlement_timeout_max = _settlement_timeout_max;

        deprecation_executor = msg.sender;
    }

    /// @notice Deploy a new TokenNetwork contract for the Token deployed at
    /// `_token_address`.
    /// @param _token_address Ethereum address of an already deployed token, to
    /// be used in the new TokenNetwork contract.
    function createERC20TokenNetwork(address _token_address)
        onlyDeprecationExecutor
        external
        returns (address token_network_address)
    {
        require(token_to_token_networks[_token_address] == address(0x0));

        TokenNetwork token_network;

        // Token contract checks are in the corresponding TokenNetwork contract
        token_network = new TokenNetwork(
            _token_address,
            secret_registry_address,
            chain_id,
            settlement_timeout_min,
            settlement_timeout_max,
            deprecation_executor
        );

        token_network_address = address(token_network);

        token_to_token_networks[_token_address] = token_network_address;
        emit TokenNetworkCreated(_token_address, token_network_address);

        return token_network_address;
    }
}
