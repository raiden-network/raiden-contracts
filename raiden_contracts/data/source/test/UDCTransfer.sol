// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

import "services/UserDeposit.sol";

// Basic contract to test the UDC's transfer function by passing this contract
// as a trusted contract to the UDC.

contract UDCTransfer {

    UserDeposit user_deposit_contract;

    constructor(address udc_address)
    {
        require(udc_address != address(0x0), "udc_address is zero");
        user_deposit_contract = UserDeposit(udc_address);
    }

    function transfer(address sender, address receiver, uint256 amount)
        external
        returns (bool success)
    {
        return user_deposit_contract.transfer(sender, receiver, amount);
    }
}
