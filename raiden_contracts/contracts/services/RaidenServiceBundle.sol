pragma solidity ^0.4.23;

import "raiden/Token.sol";
import "raiden/Utils.sol";

contract RaidenServiceBundle is Utils {
    string constant public contract_version = "0.4.0";
    Token public token;

    mapping(address => uint256) public deposits;

    constructor(address _token_address) public {
        require(_token_address != 0x0);
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
}
