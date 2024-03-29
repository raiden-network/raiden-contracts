// SPDX-License-Identifier: MIT
/* solium-disable */
pragma solidity 0.8.10;

import "raiden/Token.sol";

/*
This implements ONLY the standard functions and NOTHING else.
For a token like you would want to deploy in something like Mist, see HumanStandardToken.sol.

If you deploy this, you won't have anything useful.

Implements ERC 20 Token standard: https://github.com/ethereum/EIPs/issues/20
.*/

contract StandardToken is Token {
    uint256 internal _total_supply;
    mapping (address => uint256) public balances;
    mapping (address => mapping (address => uint256)) allowed;

    function transfer(address _to, uint256 _value)
        public override
        returns (bool success)
    {
        //Default assumes totalSupply can't be over max (2^256 - 1).
        //If your token leaves out totalSupply and can issue more tokens as time goes on, you need to check if it doesn't wrap.
        //Replace the if with this one instead.
        //if (balances[msg.sender] >= _value && balances[_to] + _value > balances[_to]) {
        if (balances[msg.sender] >= _value && _value > 0) {
            balances[msg.sender] -= _value;
            balances[_to] += _value;
            emit Transfer(msg.sender, _to, _value);
            return true;
        } else { return false; }
    }

    function transferFrom(address _from, address _to, uint256 _value)
        public override
        returns (bool success)
    {
        //same as above. Replace this line with the following if you want to protect against wrapping uints.
        //if (balances[_from] >= _value && allowed[_from][msg.sender] >= _value && balances[_to] + _value > balances[_to]) {
        require(balances[_from] >= _value);
        require(allowed[_from][msg.sender] >= _value);
        require(_value > 0);
        if ((balances[_from] >= _value) && (allowed[_from][msg.sender] >= _value) && (_value > 0)) {
            balances[_to] += _value;
            balances[_from] -= _value;
            allowed[_from][msg.sender] -= _value;
            emit Transfer(_from, _to, _value);
            return true;
        } else { return false; }
    }

    function balanceOf(address _owner) public override view returns (uint256 balance) {
        return balances[_owner];
    }

    function approve(address _spender, uint256 _value) public override returns (bool success) {
        allowed[msg.sender][_spender] = _value;
        emit Approval(msg.sender, _spender, _value);
        return true;
    }

    function allowance(address _owner, address _spender) public override view returns (uint256 remaining) {
      return allowed[_owner][_spender];
    }

    function totalSupply() public override view returns (uint256 supply) {
        return _total_supply;
    }

    function decimals() public virtual override view returns (uint8 decimals) {
        return 18;
    }
}
