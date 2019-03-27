pragma solidity 0.5.4;

import "raiden/Utils.sol";
import "raiden/Token.sol";
import "raiden/TokenNetwork.sol";


/// @title TokenNetworkRegistry
/// @notice The TokenNetwork Registry deploys new TokenNetwork contracts for the
/// Raiden Network protocol.
contract TokenNetworkRegistry is Utils {

    string constant public contract_version = "0.11.0";
    address public secret_registry_address;
    uint256 public chain_id;
    uint256 public settlement_timeout_min;
    uint256 public settlement_timeout_max;
    uint256 public max_token_networks;

    // Only for the limited Red Eyes release
    address public deprecation_executor;
    uint256 public token_network_created = 0;

    // Token address => TokenNetwork address
    mapping(address => address) public token_to_token_networks;

    event TokenNetworkCreated(address indexed token_address, address indexed token_network_address);

    modifier canCreateTokenNetwork() {
        require(token_network_created < max_token_networks);
        _;
    }

    /// @param _secret_registry_address The address of SecretRegistry that's used by all
    /// TokenNetworks created by this contract.
    /// @param _chain_id EIP-155 Chain-ID of the chain where this contract is deployed.
    /// @param _settlement_timeout_min The shortest settlement period (in number of blocks)
    /// that can be chosen at the channel opening.
    /// @param _settlement_timeout_max The longest settlement period (in number of blocks)
    /// that can be chosen at the channel opening.
    /// @param _max_token_networks the number of tokens that can be registered.
    /// MAX_UINT256 means no limits.
    constructor(
        address _secret_registry_address,
        uint256 _chain_id,
        uint256 _settlement_timeout_min,
        uint256 _settlement_timeout_max,
        uint256 _max_token_networks
    )
        public
    {
        require(_chain_id > 0);
        require(_settlement_timeout_min > 0);
        require(_settlement_timeout_max > 0);
        require(_settlement_timeout_max > _settlement_timeout_min);
        require(_secret_registry_address != address(0x0));
        require(contractExists(_secret_registry_address));
        require(_max_token_networks > 0);
        secret_registry_address = _secret_registry_address;
        chain_id = _chain_id;
        settlement_timeout_min = _settlement_timeout_min;
        settlement_timeout_max = _settlement_timeout_max;
        max_token_networks = _max_token_networks;

        deprecation_executor = msg.sender;
    }

    /// @notice Deploy a new TokenNetwork contract for the Token deployed at
    /// `_token_address`.
    /// @param _token_address Ethereum address of an already deployed token, to
    /// be used in the new TokenNetwork contract.
    function createERC20TokenNetwork(
        address _token_address,
        uint256 _channel_participant_deposit_limit,
        uint256 _token_network_deposit_limit
    )
        canCreateTokenNetwork
        external
        returns (address token_network_address)
    {
        require(token_to_token_networks[_token_address] == address(0x0));

        // We limit the number of token networks to 1 for the Bug Bounty release
        token_network_created = token_network_created + 1;

        TokenNetwork token_network;

        // Token contract checks are in the corresponding TokenNetwork contract
        token_network = new TokenNetwork(
            _token_address,
            secret_registry_address,
            chain_id,
            settlement_timeout_min,
            settlement_timeout_max,
            deprecation_executor,
            _channel_participant_deposit_limit,
            _token_network_deposit_limit
        );

        token_network_address = address(token_network);

        token_to_token_networks[_token_address] = token_network_address;
        emit TokenNetworkCreated(_token_address, token_network_address);

        return token_network_address;
    }
}
