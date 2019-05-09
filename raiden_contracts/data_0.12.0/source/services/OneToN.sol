pragma solidity 0.5.4;

import "raiden/Utils.sol";
import "services/UserDeposit.sol";
import "lib/ECVerify.sol";

contract OneToN is Utils {
    string constant public contract_version = "0.12.0";

    UserDeposit public deposit_contract;

    // The signature given to claim() has to be computed with
    // this chain_id.  Otherwise the call fails.
    uint256 public chain_id;

    // Indicates which sessions have already been settled by storing
    // keccak256(receiver, sender, expiration_block) => expiration_block.
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
        uint256 expiration_block,
        uint256 transferred
    );

    /*
     *  Constructor
     */

    /// @param _deposit_contract Address of UserDeposit contract
    constructor(
        address _deposit_contract,
        uint256 _chain_id
    )
        public
    {
        deposit_contract = UserDeposit(_deposit_contract);
        chain_id = _chain_id;
    }

    /// @notice Submit an IOU to claim the owed amount.
    /// If the deposit is smaller than the claim, the remaining deposit is
    /// claimed. If no tokens are claimed, `claim` may be retried, later.
    /// @param sender Address from which the amount is transferred
    /// @param receiver Address to which the amount is transferred
    /// @param amount Owed amount of tokens
    /// @param expiration_block Tokens can only be claimed before this time
    /// @param signature Sender's signature over keccak256(sender, receiver, amount, expiration_block)
    /// @return Amount of transferred tokens
    function claim(
        address sender,
        address receiver,
        uint256 amount,
        uint256 expiration_block,
        address one_to_n_address,
        bytes memory signature
    )
        public
        returns (uint)
    {
        require(one_to_n_address == address(this));
        require(block.number <= expiration_block);

        // validate signature
        address addressFromSignature = recoverAddressFromSignature(
            sender,
            receiver,
            amount,
            expiration_block,
            one_to_n_address,
            chain_id,
            signature
        );
        require(addressFromSignature == sender);

        // must not be claimed before
        bytes32 _key = keccak256(abi.encodePacked(receiver, sender, expiration_block));
        require(settled_sessions[_key] == 0);

        // claim as much as possible
        uint256 transferable = min(amount, deposit_contract.balances(sender));
        if (transferable > 0) {
            // register to avoid double claiming
            settled_sessions[_key] = expiration_block;
            emit Claimed(sender, receiver, expiration_block, transferable);

            // event SessionSettled(_key, expiration_block);
            require(deposit_contract.transfer(sender, receiver, transferable));
        }
        return transferable;
    }

    // TODO: gas saving function to claim multiple IOUs and free space in one transaction

    /*
     *  Internal Functions
     */

    function recoverAddressFromSignature(
        address sender,
        address receiver,
        uint256 amount,
        uint256 expiration_block,
        address one_to_n_address,
        uint256 chain_id,
        bytes memory signature
    )
        pure
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n156",
            sender,
            receiver,
            amount,
            expiration_block,
            one_to_n_address,
            chain_id
        ));
        return ECVerify.ecverify(message_hash, signature);
    }

    function min(uint256 a, uint256 b) pure internal returns (uint256)
    {
        return a > b ? b : a;
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
