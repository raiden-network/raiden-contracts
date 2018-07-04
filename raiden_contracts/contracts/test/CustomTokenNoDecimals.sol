pragma solidity ^0.4.23;

/*
This Token Contract implements the standard token functionality (https://github.com/ethereum/EIPs/issues/20), the ERC223 functionality (https://github.com/ethereum/EIPs/issues/223) as well as the following OPTIONAL extras intended for use by humans.

In other words. This is intended for deployment in something like a Token Factory or Mist wallet, and then used by humans.
Imagine coins, currencies, shares, voting weight, etc.
Machine-based, rapid creation of many tokens would not necessarily need these extra features or will be minted in other manners.

1) Initial Finite Supply (upon creation one specifies how much is minted).
2) In the absence of a token registry: Optional Decimal, Symbol & Name.

.*/

import "test/StandardTokenNoDecimals.sol";

/// @title CustomToken
contract CustomTokenNoDecimals is StandardTokenNoDecimals {

    /*
     *  Token metadata
     */
    string public version = 'H0.1';       //human 0.1 standard. Just an arbitrary versioning scheme.
    string public name;
    string public symbol;
    uint8 public _decimals;
    uint256 public multiplier;

    address public owner_address;

    /*
     * Events
     */
    event Minted(address indexed _to, uint256 indexed _num);

    /*
     *  Public functions
     */
    /// @dev Contract constructor function.
    /// @param initial_supply Initial supply of tokens.
    /// @param token_name Token name for display.
    /// @param token_symbol Token symbol.
    constructor(
        uint256 initial_supply,
        string token_name,
        string token_symbol
    )
        public
    {
        // Set the name for display purposes
        name = token_name;

        // Amount of decimals for display purposes
        _decimals = 0;
        multiplier = 1;

        // Set the symbol for display purposes
        symbol = token_symbol;

        // Initial supply is assigned to the owner
        owner_address = msg.sender;
        balances[owner_address] = initial_supply;
        _total_supply = initial_supply;
    }

    /// @notice Allows tokens to be minted and assigned to `msg.sender`
    function mint(uint256 num) public {
        balances[msg.sender] += num;
        _total_supply += num;

        emit Minted(msg.sender, num);

        require(balances[msg.sender] >= num);
        assert(_total_supply >= num);
    }

    /// @notice Transfers the collected ETH to the contract owner.
    function transferFunds() public {
        require(msg.sender == owner_address);
        require(address(this).balance > 0);

        owner_address.transfer(address(this).balance);
        assert(address(this).balance == 0);
    }
}
