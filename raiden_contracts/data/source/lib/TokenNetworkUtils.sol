// SPDX-License-Identifier: MIT
pragma solidity 0.7.6;

library TokenNetworkUtils {
    function getMaxPossibleReceivableAmount(
        uint256 participant1_deposit,
        uint256 participant1_withdrawn,
        uint256 participant1_transferred,
        uint256 participant1_locked,
        uint256 participant2_deposit,
        uint256 participant2_withdrawn,
        uint256 participant2_transferred,
        uint256 participant2_locked
    )
        public
        pure
        returns (uint256)
    {
        uint256 participant1_max_transferred;
        uint256 participant2_max_transferred;
        uint256 participant1_net_max_received;
        uint256 participant1_max_amount;

        // This is the maximum possible amount that participant1 could transfer
        // to participant2, if all the pending lock secrets have been
        // registered
        participant1_max_transferred = failsafe_addition(
            participant1_transferred,
            participant1_locked
        );

        // This is the maximum possible amount that participant2 could transfer
        // to participant1, if all the pending lock secrets have been
        // registered
        participant2_max_transferred = failsafe_addition(
            participant2_transferred,
            participant2_locked
        );

        // We enforce this check artificially, in order to get rid of hard
        // to deal with over/underflows. Settlement balance calculation is
        // symmetric (we can calculate either RmaxP1 and RmaxP2 first, order does
        // not affect result). This means settleChannel must be called with
        // ordered values.
        require(participant2_max_transferred >= participant1_max_transferred, "TNU: transfers not ordered");

        assert(participant1_max_transferred >= participant1_transferred);
        assert(participant2_max_transferred >= participant2_transferred);

        // This is the maximum amount that participant1 can receive at settlement time
        participant1_net_max_received = (
            participant2_max_transferred -
            participant1_max_transferred
        );

        // Next, we add the participant1's deposit and subtract the already
        // withdrawn amount
        participant1_max_amount = failsafe_addition(
            participant1_net_max_received,
            participant1_deposit
        );

        // Subtract already withdrawn amount
        (participant1_max_amount, ) = failsafe_subtract(
            participant1_max_amount,
            participant1_withdrawn
        );
        return participant1_max_amount;
    }

    function min(uint256 a, uint256 b) public pure returns (uint256)
    {
        return a > b ? b : a;
    }

    function max(uint256 a, uint256 b) public pure returns (uint256)
    {
        return a > b ? a : b;
    }

    /// @dev Special subtraction function that does not fail when underflowing.
    /// @param a Minuend
    /// @param b Subtrahend
    /// @return Minimum between the result of the subtraction and 0, the maximum
    /// subtrahend for which no underflow occurs
    function failsafe_subtract(uint256 a, uint256 b)
        public
        pure
        returns (uint256, uint256)
    {
        return a > b ? (a - b, b) : (0, a);
    }

    /// @dev Special addition function that does not fail when overflowing.
    /// @param a Addend
    /// @param b Addend
    /// @return Maximum between the result of the addition or the maximum
    /// uint256 value
    function failsafe_addition(uint256 a, uint256 b)
        public
        pure
        returns (uint256)
    {
        uint256 MAX_SAFE_UINT256 = (
            115792089237316195423570985008687907853269984665640564039457584007913129639935
        );
        uint256 sum = a + b;
        return sum >= a ? sum : MAX_SAFE_UINT256;
    }
}
