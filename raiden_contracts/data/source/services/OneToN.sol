// SPDX-License-Identifier: MIT
pragma solidity 0.8.10;
pragma abicoder v2;

import "lib/ECVerify.sol";
import "lib/MessageType.sol";
import "raiden/Utils.sol";
import "services/ServiceRegistry.sol";
import "services/UserDeposit.sol";

contract OneToN is Utils {
    UserDeposit public deposit_contract;
    ServiceRegistry public service_registry_contract;

    // The signature given to claim() has to be computed with
    // this chain_id.  Otherwise the call fails.
    uint256 public chain_id;

    // Indicates which sessions have already been settled by storing
    // keccak256(receiver, sender, claimable_until) => claimable_until.
    mapping (bytes32 => uint256) public settled_sessions;

    /*
     *  Events
     */

    // The session has been settled and can't be claimed again. The receiver is
    // indexed to allow services to know when claims have been successfully
    // processed.
    // When users want to get notified about low balances, they should listen
    // for UserDeposit.BalanceReduced, instead.
    // The first three values identify the session, `transferred` is the amount
    // of tokens that has actually been transferred during the claim.
    event Claimed(
        address sender,
        address indexed receiver,
        uint256 claimable_until,
        uint256 transferred
    );

    /*
     *  Constructor
     */

    /// @param _deposit_contract Address of UserDeposit contract
    /// @param _service_registry_contract Address of ServiceRegistry contract
    constructor(
        address _deposit_contract,
        uint256 _chain_id,
        address _service_registry_contract
    ) {
        deposit_contract = UserDeposit(_deposit_contract);
        chain_id = _chain_id;
        service_registry_contract = ServiceRegistry(_service_registry_contract);
    }

    /// @notice Submit an IOU to claim the owed amount.
    /// If the deposit is smaller than the claim, the remaining deposit is
    /// claimed. If no tokens are claimed, `claim` may be retried, later.
    /// @param sender Address from which the amount is transferred
    /// @param receiver Address to which the amount is transferred
    /// @param amount Owed amount of tokens
    /// @param claimable_until Tokens can only be claimed before this time
    /// @param signature Sender's signature over keccak256(sender, receiver, amount, claimable_until)
    /// @return Amount of transferred tokens
    function claim(
        address sender,
        address receiver,
        uint256 amount,
        uint256 claimable_until,
        bytes memory signature
    )
        public
        returns (uint)
    {
        require(service_registry_contract.hasValidRegistration(receiver), "receiver not registered");
        require(block.timestamp <= claimable_until, "IOU expired");

        // validate signature
        address addressFromSignature = recoverAddressFromSignature(
            sender,
            receiver,
            amount,
            claimable_until,
            chain_id,
            signature
        );
        require(addressFromSignature == sender, "Signature mismatch");

        // must not be claimed before
        bytes32 _key = keccak256(abi.encodePacked(receiver, sender, claimable_until));
        require(settled_sessions[_key] == 0, "Already settled session");

        // claim as much as possible
        uint256 transferable = min(amount, deposit_contract.balances(sender));
        if (transferable > 0) {
            // register to avoid double claiming
            settled_sessions[_key] = claimable_until;
            assert(claimable_until > 0);
            emit Claimed(sender, receiver, claimable_until, transferable);

            require(deposit_contract.transfer(sender, receiver, transferable), "deposit did not transfer");
        }
        return transferable;
    }

    /// @notice Submit multiple IOUs to claim the owed amount.
    /// This is the same as calling `claim` multiple times, except for the reduced gas cost.
    /// @param senders Addresses from which the amounts are transferred
    /// @param receivers Addresses to which the amounts are transferred
    /// @param amounts Owed amounts of tokens
    /// @param claimable_until_list Tokens can only be claimed before this time
    /// @param signatures Sender's signatures concatenated into a single bytes array
    /// @return Amount of transferred tokens
    function bulkClaim(
        address[] calldata senders,
        address[] calldata receivers,
        uint256[] calldata amounts,
        uint256[] calldata claimable_until_list,
        bytes calldata signatures
    )
        external
        returns (uint)
    {
        uint256 transferable = 0;
        require(
            senders.length == receivers.length &&
            senders.length == amounts.length &&
            senders.length == claimable_until_list.length,
            "Same number of elements required for all input parameters"
        );
        require(
            signatures.length == senders.length * 65,
            "`signatures` should contain 65 bytes per IOU"
        );
        for (uint256 i = 0; i < senders.length; i++) {
            transferable += claim(
                senders[i],
                receivers[i],
                amounts[i],
                claimable_until_list[i],
                getSingleSignature(signatures, i)
            );
        }
        return transferable;
    }

    /*
     *  Internal Functions
     */

    /// @notice Get a single signature out of a byte array that contains concatenated signatures.
    /// @param signatures Multiple signatures concatenated into a single byte array
    /// @param i Index of the requested signature (zero based; the caller must check ranges)
    function getSingleSignature(
        bytes memory signatures,
        uint256 i
    )
        internal
        pure
        returns (bytes memory)
    {
        assert(i < signatures.length);
        uint256 offset = i * 65;
        // We need only 65, but we can access only whole words, so the next usable size is 3 * 32.
        bytes memory signature = new bytes(96);
        assembly { // solium-disable-line security/no-inline-assembly
            // Copy the 96 bytes, using `offset` to start at the beginning
            // of the requested signature.
            mstore(add(signature, 32), mload(add(add(signatures, 32), offset)))
            mstore(add(signature, 64), mload(add(add(signatures, 64), offset)))
            mstore(add(signature, 96), mload(add(add(signatures, 96), offset)))

            // The first 32 bytes store the length of the dynamic array.
            // Since a signature is 65 bytes, we set the length to 65, so
            // that only the signature is returned.
            mstore(signature, 65)
        }
        return signature;
    }

    function recoverAddressFromSignature(
        address sender,
        address receiver,
        uint256 amount,
        uint256 claimable_until,
        uint256 chain_id,
        bytes memory signature
    )
        internal
        view
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(
            abi.encodePacked(
                signature_prefix,
                "188",
                address(this),
                chain_id,
                uint256(MessageType.MessageTypeId.IOU),
                sender,
                receiver,
                amount,
                claimable_until
            )
        );
        return ECVerify.ecverify(message_hash, signature);
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
