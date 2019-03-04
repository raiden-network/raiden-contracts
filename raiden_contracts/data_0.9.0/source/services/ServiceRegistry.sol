pragma solidity 0.5.4;

import "raiden/Token.sol";
import "raiden/Utils.sol";

contract ServiceRegistry is Utils {
    string constant public contract_version = "0.9.0";
    Token public token;

    mapping(address => uint256) public deposits;  // token amount staked by the service provider
    mapping(address => string) public urls;  // URLs of services for HTTP access
    address[] public service_addresses;  // list of available services (ethereum addresses)

    constructor(address _token_address) public {
        require(_token_address != address(0x0));
        require(contractExists(_token_address));

        token = Token(_token_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
    }

    function deposit(uint amount) public {
        require(amount > 0);

        // This also allows for MSs to deposit and use other MSs
        deposits[msg.sender] += amount;

        // Transfer the deposit to the smart contract
        require(token.transferFrom(msg.sender, address(this), amount));
    }

    /// Set the URL used to access a service via HTTP.
    /// When this is called for the first time, the service's ethereum address
    /// is also added to `service_addresses`.
    function setURL(string memory new_url) public {
        require(bytes(new_url).length != 0);
        if (bytes(urls[msg.sender]).length == 0) {
            service_addresses.push(msg.sender);
        }
        urls[msg.sender] = new_url;
    }

    /// Returns number of registered services. Useful for accessing service_addresses.
    function serviceCount() public view returns(uint) {
        return service_addresses.length;
    }
}
