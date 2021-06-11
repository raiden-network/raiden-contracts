// SPDX-License-Identifier: MIT
/* solium-disable indentation */
pragma solidity 0.7.6;

import "lib/ECVerify.sol";
import "lib/MessageType.sol";

library TokenNetworkUtils {
    string public constant signature_prefix = "\x19Ethereum Signed Message:\n";

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

    function recoverAddressFromBalanceProof(
        uint256 chain_id,
        uint256 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes memory signature
    )
        internal
        view
        returns (address signature_address)
    {
        // Length of the actual message: 20 + 32 + 32 + 32 + 32 + 32 + 32
        string memory message_length = "212";

        bytes32 message_hash = keccak256(abi.encodePacked(
            signature_prefix,
            message_length,
            address(this),
            chain_id,
            uint256(MessageType.MessageTypeId.BalanceProof),
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }

    function recoverAddressFromBalanceProofCounterSignature(
        MessageType.MessageTypeId message_type_id,
        uint256 chain_id,
        uint256 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes memory closing_signature,
        bytes memory non_closing_signature
    )
        internal
        view
        returns (address signature_address)
    {
        // Length of the actual message: 20 + 32 + 32 + 32 + 32 + 32 + 32 + 65
        string memory message_length = "277";

        bytes32 message_hash = keccak256(abi.encodePacked(
            signature_prefix,
            message_length,
            address(this),
            chain_id,
            uint256(message_type_id),
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature
        ));

        signature_address = ECVerify.ecverify(message_hash, non_closing_signature);
    }

    /* function recoverAddressFromCooperativeSettleSignature(
        uint256 channel_identifier,
        address participant1,
        uint256 participant1_balance,
        address participant2,
        uint256 participant2_balance,
        bytes signature
    )
        view
        internal
        returns (address signature_address)
    {
        // Length of the actual message: 20 + 32 + 32 + 32 + 20 + 32 + 20 + 32
        string memory message_length = '220';

        bytes32 message_hash = keccak256(abi.encodePacked(
            signature_prefix,
            message_length,
            address(this),
            chain_id,
            uint256(MessageTypeId.CooperativeSettle),
            channel_identifier,
            participant1,
            participant1_balance,
            participant2,
            participant2_balance
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    } */

    function recoverAddressFromWithdrawMessage(
        uint256 chain_id,
        uint256 channel_identifier,
        address participant,
        uint256 total_withdraw,
        uint256 expiration_block,
        bytes memory signature
    )
        internal
        view
        returns (address signature_address)
    {
        // Length of the actual message: 20 + 32 + 32 + 32 + 20 + 32 + 32
        string memory message_length = "200";

        bytes32 message_hash = keccak256(abi.encodePacked(
            signature_prefix,
            message_length,
            address(this),
            chain_id,
            uint256(MessageType.MessageTypeId.Withdraw),
            channel_identifier,
            participant,
            total_withdraw,
            expiration_block
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }
}
