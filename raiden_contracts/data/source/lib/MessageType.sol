// SPDX-License-Identifier: MIT
/* solium-disable error-reason */
pragma solidity 0.7.6;
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
