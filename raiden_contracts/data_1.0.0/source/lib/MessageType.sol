// SPDX-License-Identifier: MIT
/* solium-disable error-reason */
pragma solidity 0.8.10;
pragma abicoder v2;

library MessageType {

    enum MessageTypeId {
        None,
        BalanceProof,
        BalanceProofUpdate,
        Withdraw,
        CooperativeSettle,
        IOU,
        MSReward
    }
}
