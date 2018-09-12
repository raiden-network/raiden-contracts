pragma solidity ^0.4.23;

library TokenNetworkUtils {
    struct SettlementData {
        uint256 deposit;
        uint256 withdrawn;
        uint256 transferred;
        uint256 locked;
    }

    /// @dev Calculates the merkle root for an array of hashes
    function getMerkleRoot(bytes32[] merkle_tree)
        pure
        internal
        returns (bytes32)
    {
        uint256 i;
        bytes32 merkle_root;
        bytes32 lockhash;
        uint256 length = merkle_tree.length - 1;

        while (length > 1) {
            if (length % 2 != 0) {
                merkle_tree[length] = merkle_tree[length - 1];
                length += 1;
            }

            for (i = 0; i < length - 1; i += 2) {
                if (merkle_tree[i] == merkle_tree[i + 1]) {
                    lockhash = merkle_tree[i];
                } else if (merkle_tree[i] < merkle_tree[i + 1]) {
                    lockhash = keccak256(abi.encodePacked(merkle_tree[i], merkle_tree[i + 1]));
                } else {
                    lockhash = keccak256(abi.encodePacked(merkle_tree[i + 1], merkle_tree[i]));
                }
                merkle_tree[i / 2] = lockhash;
            }
            length = i / 2;
        }

        merkle_root = merkle_tree[0];

        return merkle_root;
    }

    function getMaxPossibleReceivableAmount(
        SettlementData participant1_settlement,
        SettlementData participant2_settlement
    )
        pure
        internal
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
            participant1_settlement.transferred,
            participant1_settlement.locked
        );

        // This is the maximum possible amount that participant2 could transfer
        // to participant1, if all the pending lock secrets have been
        // registered
        participant2_max_transferred = failsafe_addition(
            participant2_settlement.transferred,
            participant2_settlement.locked
        );

        // We enforce this check artificially, in order to get rid of hard
        // to deal with over/underflows. Settlement balance calculation is
        // symmetric (we can calculate either RmaxP1 and RmaxP2 first, order does
        // not affect result). This means settleChannel must be called with
        // ordered values.
        require(participant2_max_transferred >= participant1_max_transferred);

        assert(participant1_max_transferred >= participant1_settlement.transferred);
        assert(participant2_max_transferred >= participant2_settlement.transferred);

        // This is the maximum amount that participant1 can receive at settlement time
        participant1_net_max_received = (
            participant2_max_transferred -
            participant1_max_transferred
        );

        // Next, we add the participant1's deposit and subtract the already
        // withdrawn amount
        participant1_max_amount = failsafe_addition(
            participant1_net_max_received,
            participant1_settlement.deposit
        );

        // Subtract already withdrawn amount
        (participant1_max_amount, ) = failsafe_subtract(
            participant1_max_amount,
            participant1_settlement.withdrawn
        );
        return participant1_max_amount;
    }

    function min(uint256 a, uint256 b) pure internal returns (uint256)
    {
        return a > b ? b : a;
    }

    /// @dev Special subtraction function that does not fail when underflowing.
    /// @param a Minuend
    /// @param b Subtrahend
    /// @return Minimum between the result of the subtraction and 0, the maximum
    /// subtrahend for which no underflow occurs.
    function failsafe_subtract(uint256 a, uint256 b)
        pure
        internal
        returns (uint256, uint256)
    {
        return a > b ? (a - b, b) : (0, a);
    }

    /// @dev Special addition function that does not fail when overflowing.
    /// @param a Addend
    /// @param b Addend
    /// @return Maximum between the result of the addition or the maximum
    /// uint256 value.
    function failsafe_addition(uint256 a, uint256 b)
        pure
        internal
        returns (uint256)
    {
        uint256 MAX_SAFE_UINT256 = (
            115792089237316195423570985008687907853269984665640564039457584007913129639935
        );
        uint256 sum = a + b;
        return sum >= a ? sum : MAX_SAFE_UINT256;
    }

    /// @notice Check if a contract exists
    /// @param contract_address The address to check whether a contract is
    /// deployed or not
    /// @return True if a contract exists, false otherwise
    function contractExists(address contract_address) view internal returns (bool) {
        uint size;

        assembly {
            size := extcodesize(contract_address)
        }

        return size > 0;
    }
}
