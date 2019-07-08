pragma solidity 0.5.4;

import "raiden/Token.sol";
import "raiden/Utils.sol";

contract Deposit {
    Token public token;
    address public withdrawer;
    uint256 public release_at;

    constructor(address _token, uint256 _release_at, address _withdrawer) public {
        token = Token(_token);
        // Don't care even if it's in the past.
        release_at = _release_at;
        withdrawer = _withdrawer;
    }

    function deposit(uint256 _amount) external returns (bool success) {
        require(token.transferFrom(msg.sender, address(this), _amount));
        return true;
    }

    function withdraw(address _to) external returns (bool success) {
        uint256 sent_amount = token.balanceOf(address(this));
        require(msg.sender == withdrawer);
        require(now >= release_at);
        require(sent_amount > 0);
        require(token.transfer(_to, sent_amount));
        return true;
    }
}


contract ServiceRegistry is Utils {
    Token public token;
    address public owner;

    // After a price is set to set_price at timestamp set_price_at,
    // the price decays according to decayed_price().
    uint256 public set_price;
    uint256 public set_price_at;

    // Once the price is too low, 20% increase cannot not move the price upwards.
    uint256 constant min_price = 1000;

    mapping(address => uint256) public service_valid_till;
    mapping(address => string) public urls;  // URLs of services for HTTP access

    event RegisteredService(address indexed service, uint256 valid_till, uint256 deposit_amount, Deposit deposit_contract);

    // @param _token_for_registration The address of the ERC20 token contract that services use for registration fees
    constructor(address _token_for_registration, uint256 _initial_price) public {
        require(_token_for_registration != address(0x0), "token at address zero");
        require(contractExists(_token_for_registration), "token has no code");
        require(_initial_price >= min_price, "initial price too low");

        token = Token(_token_for_registration);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0, "total supply zero");
        owner = msg.sender;

        // Set up the price and the set price timestamp
        set_price = _initial_price;
        set_price_at = now;
    }

    function deposit(uint _limit_amount) public {
        uint256 amount = current_price();
        require(_limit_amount >= amount, "not enough limit");

        // Extend the service position.
        uint256 valid_till = service_valid_till[msg.sender];
        if (valid_till < now) { // first time joiner or expired service.
            valid_till = now;
        }
        valid_till = valid_till + 180 days;
        // Check against overflow.
        require(valid_till < valid_till + 180 days);
        valid_till = valid_till + 180 days;
        assert(valid_till > service_valid_till[msg.sender]);
        service_valid_till[msg.sender] = valid_till;

        // Record the price
        set_price = amount * 6 / 5;
        set_price_at = now;

        // Move the deposit in a new Deposit contract.
        require(token.transferFrom(msg.sender, address(this), amount));
        Deposit depo = new Deposit(address(token), valid_till, msg.sender);
        require(token.approve(address(depo), amount));
        require(depo.deposit(amount));

        // Fire event
        emit RegisteredService(msg.sender, valid_till, amount, depo);
    }

    /// Set the URL used to access a service via HTTP.
    /// When this is called for the first time, the service's ethereum address
    /// is also added to `service_addresses`.
    function setURL(string memory new_url) public {
        require(now < service_valid_till[msg.sender]);
        require(bytes(new_url).length != 0, "new url is empty string");
        urls[msg.sender] = new_url;
    }

    uint constant decay_constant = 200 days; // Maybe make this configurable?

    function decayed_price(uint256 set_price, uint256 time_passed) public
        view returns (uint256) {
        // We are here trying to approximate some exponential decay.
        // exp(- X / A) where
        //   X is the number of seconds since the last price change
        //   A is the decay constant (A = 200 days correspnods to 0.5% decrease per day)

        // exp(- X / A) ~~ P / Q where
        //   P = 24 A^4
        //   Q = 24 A^4 + 24 A^3X + 12 A^2X^2 + 4 AX^3 + X^4
        // Note: swap P and Q, and then think about the Taylor expansion.

        uint256 X = time_passed;

        if (X >= 2 ** 64) { // The computation below overflows.
            return min_price;
        }

        uint256 A = decay_constant;

        uint256 P = 24 * (A ** 4);
        uint256 Q = P + 24*(A**3)*X + 12*(A**2)*(X**2) + 4*A*(X**3) + X**4;

        uint256 price = set_price * P / Q;

        // Not allowing a price smaller than 1000.
        // Once it's too low it's too low forever.
        if (price < min_price) {  // Maybe make this configurable too?
            price = min_price;
        }
        return price;

    }

    function current_price() public view returns (uint256) {
        require(now >= set_price_at);
        uint256 passed = now - set_price_at;

        return decayed_price(set_price, passed);
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
