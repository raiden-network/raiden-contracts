pragma solidity ^0.4.23;

import "./Utils.sol";
import "./Token.sol";
import "./TokenNetwork.sol";

contract TokenNetworkRegistry is Utils {

    /*
     *  Data structures
     */

    string constant public contract_version = "0.3._";
    address public secret_registry_address;
    uint256 public chain_id;

    // Token address => TokenNetwork address
    mapping(address => address) public token_to_token_networks;

    /*
     *  Events
     */

    event TokenNetworkCreated(address indexed token_address, address indexed token_network_address);

    /*
     *  Constructor
     */

    constructor(address _secret_registry_address, uint256 _chain_id) public {
        require(_chain_id > 0);
        require(_secret_registry_address != 0x0);
        require(contractExists(_secret_registry_address));
        secret_registry_address = _secret_registry_address;
        chain_id = _chain_id;
    }

    /*
     *  External Functions
     */

    function createERC20TokenNetwork(address _token_address)
        external
        returns (address token_network_address)
    {
        require(token_to_token_networks[_token_address] == 0x0);

        // Token contract checks are in the corresponding TokenNetwork contract

        token_network_address = new TokenNetwork(
            _token_address,
            secret_registry_address,
            chain_id
        );

        token_to_token_networks[_token_address] = token_network_address;
        emit TokenNetworkCreated(_token_address, token_network_address);

        return token_network_address;
    }
}
