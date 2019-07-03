pragma solidity 0.5.4;

import "raiden/Token.sol";
import "raiden/Utils.sol";

contract ServiceRegistry is Utils {
    Token public token;
    address public owner;

    mapping(address => uint256) public deposits;  // token amount staked by the service provider
    mapping(address => string) public urls;  // URLs of services for HTTP access
    address[] public service_addresses;  // list of available services (ethereum addresses)

    // @param _token_for_registration The address of the ERC20 token contract that services use for registration fees
    constructor(address _token_for_registration) public {
        require(_token_for_registration != address(0x0));
        require(contractExists(_token_for_registration));

        token = Token(_token_for_registration);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
        owner = msg.sender;
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


// MIT License

// Copyright (c) 2018

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
