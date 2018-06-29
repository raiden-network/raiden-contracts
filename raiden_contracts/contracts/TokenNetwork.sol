pragma solidity ^0.4.23;

import "raiden/Token.sol";
import "raiden/Utils.sol";
import "raiden/lib/ECVerify.sol";
import "raiden/SecretRegistry.sol";

contract TokenNetwork is Utils {

    /*
     *  Data structures
     */

    string constant public contract_version = "0.3._";

    // Instance of the token used as digital currency by the channels
    Token public token;

    // Instance of SecretRegistry used for storing secrets revealed in a mediating transfer.
    SecretRegistry public secret_registry;

    // Chain ID as specified by EIP155 used in balance proof signatures to avoid replay attacks
    uint256 public chain_id;

    uint256 public settlement_timeout_min;
    uint256 public settlement_timeout_max;

    uint256 constant public MAX_SAFE_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935;

    // channel_identifier => Channel, where the channel identifier is the keccak256 of the
    // addresses of the two participants
    mapping (bytes32 => Channel) public channels;

    // We keep the unlock data in a separate mapping to allow channel data structures to be
    // removed when settling. If there are locked transfers, we need to store data needed to
    // unlock them at a later time. Key is the channel_identifier.
    mapping(bytes32 => UnlockData) channel_identifier_to_unlock_data;

    struct Participant {
        // Total amount of token transferred to this smart contract through the
        // `setTotalDeposit` function, note that direct token transfer cannot be
        // tracked and will be burned.
        uint256 deposit;

        // Total amount of tokens withdrawn by the participant. This is a strictly monotonic value
        uint256 withdrawn_amount;

        // This is a value set to true after the channel has been closed, only if this is the
        // participant who closed the channel.
        // This is bytes1 and it gets packed with the rest of the struct data.
        bool is_the_closer;

        // keccak256 of the balance data provided after a closeChannel or an
        // updateNonClosingBalanceProof call
        bytes32 balance_hash;

        // Monotonically increasing counter of the off-chain transfers, provided along
        // with the balance_hash
        uint256 nonce;
    }

    struct UnlockData {
        // Data provided when uncooperatively settling the channel, used to unlock locked
        // transfers at a later point in time. The key is the merkle tree root of all pending
        // transfers. The value is the total amount of tokens locked in the pending transfers.
        // Note that we store all locksroots for both participants here, with the assumption that
        // no two locksroots can be the same due to having different values for
        // the secrethash of each lock.
        mapping (bytes32 => uint256) locksroot_to_locked_amount;
    }

    struct Channel {
        // After opening the channel this value represents the settlement window. This is the
        // number of blocks that need to be mined between closing the channel uncooperatively
        // and settling the channel.
        // After the channel has been uncooperatively closed, this value represents the
        // block number after which settleChannel can be called.
        uint256 settle_block_number;

        // Channel state
        // 1 = open, 2 = closed
        // 0 = non-existent or settled
        uint8 state;

        mapping(address => Participant) participants;
    }

    struct SettlementData {
        uint256 deposit;
        uint256 withdrawn;
        uint256 transferred;
        uint256 locked;
    }

    /*
     *  Events
     */

    event ChannelOpened(
        bytes32 indexed channel_identifier,
        address indexed participant1,
        address indexed participant2,
        uint256 settle_timeout
    );

    event ChannelNewDeposit(
        bytes32 indexed channel_identifier,
        address indexed participant,
        uint256 total_deposit
    );

    // withdrawn_amount is the total amount withdrawn by the participant from the channel
    event ChannelWithdraw(
        bytes32 indexed channel_identifier,
        address indexed participant, uint256 total_withdraw
    );

    event ChannelClosed(bytes32 indexed channel_identifier, address indexed closing_participant);

    event ChannelUnlocked(
        bytes32 indexed channel_identifier,
        address indexed participant,
        uint256 unlocked_amount,
        uint256 returned_tokens
    );

    event NonClosingBalanceProofUpdated(
        bytes32 indexed channel_identifier,
        address indexed closing_participant
    );

    event ChannelSettled(
        bytes32 indexed channel_identifier,
        uint256 participant1_amount,
        uint256 participant2_amount
    );

    /*
     * Modifiers
     */

    modifier isOpen(address participant, address partner) {
        bytes32 channel_identifier = getChannelIdentifier(participant, partner);
        require(channels[channel_identifier].state == 1);
        _;
    }

    modifier settleTimeoutValid(uint256 timeout) {
        require(timeout >= settlement_timeout_min && timeout <= settlement_timeout_max);
        _;
    }

    /*
     *  Constructor
     */

    constructor(
        address _token_address,
        address _secret_registry,
        uint256 _chain_id,
        uint256 _settlement_timeout_min,
        uint256 _settlement_timeout_max
    )
        public
    {
        require(_token_address != 0x0);
        require(_secret_registry != 0x0);
        require(_chain_id > 0);
        require(_settlement_timeout_min > 0);
        require(_settlement_timeout_max > 0);
        require(_settlement_timeout_max > _settlement_timeout_min);
        require(contractExists(_token_address));
        require(contractExists(_secret_registry));

        token = Token(_token_address);

        secret_registry = SecretRegistry(_secret_registry);
        chain_id = _chain_id;
        settlement_timeout_min = _settlement_timeout_min;
        settlement_timeout_max = _settlement_timeout_max;

        // Make sure the contract is indeed a token contract
        require(token.totalSupply() > 0);
    }

    /*
     *  Public functions
     */

    /// @notice Opens a new channel between `participant1` and `participant2`.
    /// Can be called by anyone.
    /// @param participant1 Ethereum address of a channel participant.
    /// @param participant2 Ethereum address of the other channel participant.
    /// @param settle_timeout Number of blocks that need to be mined between a
    /// call to closeChannel and settleChannel.
    function openChannel(address participant1, address participant2, uint256 settle_timeout)
        settleTimeoutValid(settle_timeout)
        public
        returns (bytes32)
    {
        bytes32 channel_identifier = getChannelIdentifier(participant1, participant2);
        Channel storage channel = channels[channel_identifier];

        require(channel.settle_block_number == 0);
        require(channel.state == 0);

        // Store channel information
        channel.settle_block_number = settle_timeout;
        // Mark channel as opened
        channel.state = 1;

        emit ChannelOpened(channel_identifier, participant1, participant2, settle_timeout);

        return channel_identifier;
    }

    /// @notice Sets the channel participant total deposit value.
    /// Can be called by anyone.
    /// @param participant Channel participant whose deposit is being set.
    /// @param total_deposit Idempotent function which sets the total amount of
    /// tokens that the participant will have as a deposit.
    /// @param partner Channel partner address, needed to compute the channel identifier.
    function setTotalDeposit(address participant, uint256 total_deposit, address partner)
        isOpen(participant, partner)
        public
    {
        require(total_deposit > 0);

        bytes32 channel_identifier;
        uint256 added_deposit;
        uint256 channel_deposit;

        channel_identifier = getChannelIdentifier(participant, partner);
        Channel storage channel = channels[channel_identifier];
        Participant storage participant_state = channel.participants[participant];
        Participant storage partner_state = channel.participants[partner];

        // Calculate the actual amount of tokens that will be transferred
        added_deposit = total_deposit - participant_state.deposit;

        // Update the participant's channel deposit
        participant_state.deposit += added_deposit;

        // Calculate the entire channel deposit, to avoid overflow
        channel_deposit = participant_state.deposit + partner_state.deposit;

        emit ChannelNewDeposit(channel_identifier, participant, participant_state.deposit);

        // Do the transfer
        require(token.transferFrom(msg.sender, address(this), added_deposit));

        require(participant_state.deposit >= added_deposit);
        require(channel_deposit >= participant_state.deposit);
        require(channel_deposit >= partner_state.deposit);
    }

    /// @notice Allows `participant` to withdraw tokens from the channel that he has with
    /// `partner`, without closing it. Can be called by anyone. Can only be called once per
    /// each signed withdraw message.
    /// @param participant Channel participant, who will receive the withdrawn amount.
    /// @param total_withdraw Total amount of tokens that are marked as withdrawn from the channel
    /// during the channel lifecycle.
    /// @param partner Channel partner address, needed to compute the channel identifier.
    /// @param participant_signature Participant's signature on the withdraw data.
    /// @param partner_signature Partner's signature on the withdraw data.
    function setTotalWithdraw(
        address participant,
        uint256 total_withdraw,
        address partner,
        bytes participant_signature,
        bytes partner_signature
    )
        external
    {
        require(total_withdraw > 0);

        bytes32 channel_identifier;
        uint256 total_deposit;
        uint256 current_withdraw;

        channel_identifier = getChannelIdentifier(participant, partner);
        Channel storage channel = channels[channel_identifier];

        Participant storage participant_state = channel.participants[participant];
        Participant storage partner_state = channel.participants[partner];

        total_deposit = participant_state.deposit + partner_state.deposit;

        // Using the total_withdraw (monotonically increasing) in the signed message ensures
        // that we do not allow reply attack to happen, by using the same withdraw proof twice.
        current_withdraw = total_withdraw - participant_state.withdrawn_amount;

        participant_state.withdrawn_amount += current_withdraw;

        // Do the tokens transfer
        require(token.transfer(participant, current_withdraw));

        // Channel must be open
        require(channel.state == 1);

        verifyWithdrawSignatures(
            channel_identifier,
            participant,
            partner,
            total_withdraw,
            participant_signature,
            partner_signature
        );

        require(current_withdraw > 0);

        // Underflow check
        require(participant_state.withdrawn_amount >= current_withdraw);
        require(participant_state.withdrawn_amount == total_withdraw);

        // Entire withdrawn amount must not be bigger than the entire channel deposit
        require(participant_state.withdrawn_amount <= (total_deposit - partner_state.withdrawn_amount));

        require(total_deposit >= participant_state.deposit);
        require(total_deposit >= partner_state.deposit);

        // A withdraw should never happen if a participant already has a balance proof in storage
        assert(participant_state.nonce == 0);
        assert(partner_state.nonce == 0);

        emit ChannelWithdraw(channel_identifier, participant, participant_state.withdrawn_amount);
    }

    /// @notice Close the channel defined by the two participant addresses. Only a participant
    /// may close the channel, providing a balance proof signed by its partner. Callable only once.
    /// @param partner Channel partner of the `msg.sender`, who provided the signature.
    /// We need the partner for computing the channel identifier.
    /// @param balance_hash Hash of (transferred_amount, locked_amount, locksroot).
    /// @param additional_hash Computed from the message. Used for message authentication.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param signature Partner's signature of the balance proof data.
    function closeChannel(
        address partner,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes signature
    )
        isOpen(msg.sender, partner)
        public
    {
        address recovered_partner_address;
        bytes32 channel_identifier;

        channel_identifier = getChannelIdentifier(msg.sender, partner);
        Channel storage channel = channels[channel_identifier];

        // Mark the channel as closed and mark the closing participant
        channel.state = 2;
        channel.participants[msg.sender].is_the_closer = true;

        // This is the block number at which the channel can be settled.
        channel.settle_block_number += uint256(block.number);

        // Nonce 0 means that the closer never received a transfer, therefore never received a
        // balance proof, or he is intentionally not providing the latest transfer, in which case
        // the closing party is going to lose the tokens that were transferred to him.
        if (nonce > 0) {
            recovered_partner_address = recoverAddressFromBalanceProof(
                channel_identifier,
                balance_hash,
                nonce,
                additional_hash,
                signature
            );

            updateBalanceProofData(channel, recovered_partner_address, nonce, balance_hash);

            // Signature must be from the channel partner
            require(partner == recovered_partner_address);
        }

        emit ChannelClosed(channel_identifier, msg.sender);
    }

    /// @notice Called on a closed channel, the function allows the non-closing participant to
    /// provide the last balance proof, which modifies the closing participant's state. Can be
    /// called multiple times by anyone.
    /// @param closing_participant Channel participant who closed the channel.
    /// @param non_closing_participant Channel participant who needs to update the balance proof.
    /// @param balance_hash Hash of (transferred_amount, locked_amount, locksroot).
    /// @param additional_hash Computed from the message. Used for message authentication.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param closing_signature Closing participant's signature of the balance proof data.
    /// @param non_closing_signature Non-closing participant signature of the balance proof data.
    function updateNonClosingBalanceProof(
        address closing_participant,
        address non_closing_participant,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes closing_signature,
        bytes non_closing_signature
    )
        external
    {
        require(balance_hash != 0x0);
        require(nonce > 0);

        bytes32 channel_identifier;
        address recovered_non_closing_participant;
        address recovered_closing_participant;

        channel_identifier = getChannelIdentifier(closing_participant, non_closing_participant);
        Channel storage channel = channels[channel_identifier];

        // We need the signature from the non-closing participant to allow anyone
        // to make this transaction. E.g. a monitoring service.
        recovered_non_closing_participant = recoverAddressFromBalanceProofUpdateMessage(
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            non_closing_signature
        );

        recovered_closing_participant = recoverAddressFromBalanceProof(
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature
        );

        Participant storage closing_participant_state = channel.participants[closing_participant];

        // Update the balance proof data for the closing_participant
        updateBalanceProofData(channel, closing_participant, nonce, balance_hash);

        emit NonClosingBalanceProofUpdated(channel_identifier, closing_participant);

        // Channel must be closed
        require(channel.state == 2);

        // Channel must be in the settlement window
        require(channel.settle_block_number >= block.number);

        // Make sure the first signature is from the closing participant
        require(closing_participant_state.is_the_closer);

        require(closing_participant == recovered_closing_participant);
        require(non_closing_participant == recovered_non_closing_participant);
    }

    /// @notice Settles the balance between the two parties.
    /// @param participant1 Channel participant.
    /// @param participant1_transferred_amount The latest known amount of tokens transferred
    /// from `participant1` to `participant2`.
    /// `participant1_transferred_amount + participant1_locked_amount` MUST be <= `participant2_transferred_amount + participant2_locked_amount`
    /// @param participant1_locked_amount Amount of tokens owed by `participant1` to
    /// `participant2`, contained in locked transfers that will be retrieved by calling `unlock`
    /// after the channel is settled.
    /// @param participant1_locksroot The latest known merkle root of the pending hash-time locks
    /// of `participant1`, used to validate the unlocked proofs.
    /// @param participant2 Other channel participant.
    /// @param participant2_transferred_amount The latest known amount of tokens transferred
    /// from `participant2` to `participant1`.
    /// `participant1_transferred_amount + participant1_locked_amount` MUST be <= `participant2_transferred_amount + participant2_locked_amount`
    /// @param participant2_locked_amount Amount of tokens owed by `participant2` to
    /// `participant1`, contained in locked transfers that will be retrieved by calling `unlock`
    /// after the channel is settled.
    /// @param participant2_locksroot The latest known merkle root of the pending hash-time locks
    /// of `participant2`, used to validate the unlocked proofs.
    function settleChannel(
        address participant1,
        uint256 participant1_transferred_amount,
        uint256 participant1_locked_amount,
        bytes32 participant1_locksroot,
        address participant2,
        uint256 participant2_transferred_amount,
        uint256 participant2_locked_amount,
        bytes32 participant2_locksroot
    )
        public
    {
        bytes32 channel_identifier;

        channel_identifier = getChannelIdentifier(participant1, participant2);
        Channel storage channel = channels[channel_identifier];

        // Channel must be closed
        require(channel.state == 2);

        // Settlement window must be over
        require(channel.settle_block_number < block.number);

        Participant storage participant1_state = channel.participants[participant1];
        Participant storage participant2_state = channel.participants[participant2];

        require(verifyBalanceHashData(
            participant1_state,
            participant1_transferred_amount,
            participant1_locked_amount,
            participant1_locksroot
        ));

        require(verifyBalanceHashData(
            participant2_state,
            participant2_transferred_amount,
            participant2_locked_amount,
            participant2_locksroot
        ));

        // We are calculating the final token amounts that need to be transferred to the
        // participants and the amount of tokens that need to remain locked in the contract. These
        // tokens can be unlocked by calling `unlock`.
        // participant1_transferred_amount is the amount of tokens that participant1 will receive
        // participant2_transferred_amount is the amount of tokens that participant2 will receive
        // We are reusing variables due to the local variables number limit. For better readability
        // this can be refactored further.
        (
            participant1_transferred_amount,
            participant2_transferred_amount,
            participant1_locked_amount,
            participant2_locked_amount
        ) = getSettleTransferAmounts(
            participant1_state,
            participant1_transferred_amount,
            participant1_locked_amount,
            participant2_state,
            participant2_transferred_amount,
            participant2_locked_amount
        );

        // Remove the channel data from storage
        delete channel.participants[participant1];
        delete channel.participants[participant2];
        delete channels[channel_identifier];

        // Store balance data needed for `unlock`
        updateUnlockData(
            channel_identifier,
            participant1_locked_amount,
            participant1_locksroot
        );
        updateUnlockData(
            channel_identifier,
            participant2_locked_amount,
            participant2_locksroot
        );

        // Do the actual token transfers
        if (participant1_transferred_amount > 0) {
            require(token.transfer(participant1, participant1_transferred_amount));
        }

        if (participant2_transferred_amount > 0) {
            require(token.transfer(participant2, participant2_transferred_amount));
        }

        emit ChannelSettled(
            channel_identifier,
            participant1_transferred_amount,
            participant2_transferred_amount
        );
    }

    function getSettleTransferAmounts(
        Participant storage participant1_state,
        uint256 participant1_transferred_amount,
        uint256 participant1_locked_amount,
        Participant storage participant2_state,
        uint256 participant2_transferred_amount,
        uint256 participant2_locked_amount
    )
        view
        private
        returns (uint256, uint256, uint256, uint256)
    {
        // Direct token transfers done through the token `transfer` function
        // cannot be accounted for, these superfluous tokens will be burned,
        // this is because there is no way to tell which participant (if any)
        // had ownership over the token.

        // Cases that require attention:
        // case1. If participant1 does NOT provide a balance proof or provides an old balance proof.
        // participant2_transferred_amount can be [0, real_participant2_transferred_amount)
        // We need to punish participant1.
        // case2. If participant2 does NOT provide a balance proof or provides an old balance proof.
        // participant1_transferred_amount can be [0, real_participant1_transferred_amount)
        // We need to punish participant2.
        // case3. If neither participants provide a balance proof, we just subtract their
        // withdrawn amounts from their deposits.

        uint256 participant1_amount;
        uint256 participant2_amount;
        uint256 total_available_deposit;

        SettlementData memory participant1_settlement;
        SettlementData memory participant2_settlement;

        participant1_settlement.deposit = participant1_state.deposit;
        participant1_settlement.withdrawn = participant1_state.withdrawn_amount;
        participant1_settlement.transferred = participant1_transferred_amount;
        participant1_settlement.locked = participant1_locked_amount;

        participant2_settlement.deposit = participant2_state.deposit;
        participant2_settlement.withdrawn = participant2_state.withdrawn_amount;
        participant2_settlement.transferred = participant2_transferred_amount;
        participant2_settlement.locked = participant2_locked_amount;

        total_available_deposit = getChannelAvailableDeposit(
            participant1_state,
            participant2_state
        );

        // This amount is the maximum possible amount that participant1 can receive
        // and also contains the entire locked amount of the pending transfers
        // from participant2 to participant1.
        participant1_amount = getMaxPossibleReceivableAmount(
            participant1_settlement,
            participant2_settlement
        );

        // We need to bound this to the available channel deposit
        participant1_amount = min(participant1_amount, total_available_deposit);

        // Now it is safe to subtract without underflow
        participant2_amount = total_available_deposit - participant1_amount;

        // We take out the pending transfers locked amount, bounding it by the maximum receivable amount.
        (participant1_amount, participant2_locked_amount) = failsafe_subtract(
            participant1_amount,
            participant2_locked_amount
        );

        // We take out the pending transfers locked amount, bounding it by the maximum receivable amount.
        (participant2_amount, participant1_locked_amount) = failsafe_subtract(
            participant2_amount,
            participant1_locked_amount
        );

        // This should never happen:
        assert(participant1_amount <= total_available_deposit);
        assert(participant2_amount <= total_available_deposit);
        assert(total_available_deposit == (
            participant1_amount +
            participant2_amount +
            participant1_locked_amount +
            participant2_locked_amount
        ));

        return (
            participant1_amount,
            participant2_amount,
            participant1_locked_amount,
            participant2_locked_amount
        );
    }

    /// @notice Unlocks all locked off-chain transfers and sends the locked tokens to the
    /// participant. Anyone can call unlock on behalf of a channel participant.
    /// @param participant Address of the participant who will receive the unlocked tokens.
    /// @param partner Address of the participant who owes the locked tokens.
    /// @param merkle_tree_leaves The entire merkle tree of pending transfers.
    function unlock(
        address participant,
        address partner,
        bytes merkle_tree_leaves
    )
        public
    {
        require(merkle_tree_leaves.length > 0);

        bytes32 channel_identifier;
        bytes32 computed_locksroot;
        uint256 unlocked_amount;
        uint256 locked_amount;
        uint256 returned_tokens;

        channel_identifier = getChannelIdentifier(participant, partner);

        // Calculate the locksroot for the pending transfers and the amount of tokens
        // corresponding to the locked transfers with secrets revealed on chain.
        (computed_locksroot, unlocked_amount) = getMerkleRootAndUnlockedAmount(merkle_tree_leaves);

        // The partner must have a non-empty locksroot that must be the same as
        // the computed locksroot.
        UnlockData storage unlock_data = channel_identifier_to_unlock_data[channel_identifier];

        // Get the amount of tokens that have been left in the contract, to account for the
        // pending transfers.
        locked_amount = unlock_data.locksroot_to_locked_amount[computed_locksroot];

        // Make sure we don't transfer more tokens than previously reserved in the smart contract.
        unlocked_amount = min(unlocked_amount, locked_amount);

        // Transfer the rest of the tokens back to the partner
        returned_tokens = locked_amount - unlocked_amount;

        // Remove partner's unlock data
        delete unlock_data.locksroot_to_locked_amount[computed_locksroot];

        // Transfer the unlocked tokens to the participant. unlocked_amount can be 0
        if (unlocked_amount > 0) {
            require(token.transfer(participant, unlocked_amount));
        }

        // Transfer the rest of the tokens back to the partner
        if (returned_tokens > 0) {
            require(token.transfer(partner, returned_tokens));
        }

        emit ChannelUnlocked(channel_identifier, participant, unlocked_amount, returned_tokens);

        // Channel must be settled and channel data deleted
        require(channels[channel_identifier].state == 0);

        require(computed_locksroot != 0);
        require(locked_amount > 0);
        require(locked_amount >= returned_tokens);
        assert(locked_amount >= unlocked_amount);
    }

    function cooperativeSettle(
        address participant1_address,
        uint256 participant1_balance,
        address participant2_address,
        uint256 participant2_balance,
        bytes participant1_signature,
        bytes participant2_signature
    )
        public
    {
        bytes32 channel_identifier;
        address participant1;
        address participant2;
        uint256 total_available_deposit;
        uint256 initial_state;

        channel_identifier = getChannelIdentifier(participant1_address, participant2_address);
        Channel storage channel = channels[channel_identifier];
        initial_state = channel.state;

        participant1 = recoverAddressFromCooperativeSettleSignature(
            channel_identifier,
            participant1_address,
            participant1_balance,
            participant2_address,
            participant2_balance,
            participant1_signature
        );

        participant2 = recoverAddressFromCooperativeSettleSignature(
            channel_identifier,
            participant1_address,
            participant1_balance,
            participant2_address,
            participant2_balance,
            participant2_signature
        );

        Participant storage participant1_state = channel.participants[participant1];
        Participant storage participant2_state = channel.participants[participant2];

        total_available_deposit = getChannelAvailableDeposit(
            participant1_state,
            participant2_state
        );

        // Remove channel data from storage before doing the token transfers
        delete channel.participants[participant1];
        delete channel.participants[participant2];
        delete channels[channel_identifier];


        // Do the token transfers
        if (participant1_balance > 0) {
            require(token.transfer(participant1, participant1_balance));
        }

        if (participant2_balance > 0) {
            require(token.transfer(participant2, participant2_balance));
        }

        // The channel must be open
        require(initial_state == 1);

        // The provided addresses must be the same as the recovered ones
        require(participant1 == participant1_address);
        require(participant2 == participant2_address);

        // The sum of the provided balances must be equal to the total available deposit
        require(total_available_deposit == (participant1_balance + participant2_balance));
        emit ChannelSettled(channel_identifier, participant1_balance, participant2_balance);

    }

    /// @dev Returns the unique identifier for the channel
    /// @param participant Address of a channel participant.
    /// @param partner Address of the channel partner.
    /// @return Unique identifier for the channel.
    function getChannelIdentifier(address participant, address partner)
        pure
        public
        returns (bytes32)
    {
        require(participant != 0x0);
        require(partner != 0x0);

        // Participant addresses must be different
        require(participant != partner);

        // Lexicographic order of the channel addresses
        // This limits the number of channels that can be opened between two nodes to 1.
        if (participant < partner) {
            return keccak256(abi.encodePacked(participant, partner));
        } else {
            return keccak256(abi.encodePacked(partner, participant));
        }
    }

    function updateBalanceProofData(
        Channel storage channel,
        address participant,
        uint256 nonce,
        bytes32 balance_hash
    )
        internal
    {
        Participant storage participant_state = channel.participants[participant];

        // Multiple calls to updateNonClosingBalanceProof can be made and we need to store
        // the last known balance proof data
        require(nonce > participant_state.nonce);

        participant_state.nonce = nonce;
        participant_state.balance_hash = balance_hash;
    }

    function updateUnlockData(
        bytes32 channel_identifier,
        uint256 locked_amount,
        bytes32 locksroot
    )
        internal
    {
        // If there are transfers to unlock, store the locksroot and total amount of tokens
        if (locked_amount == 0 || locksroot == 0) {
            return;
        }

        UnlockData storage unlock_data = channel_identifier_to_unlock_data[channel_identifier];
        unlock_data.locksroot_to_locked_amount[locksroot] = locked_amount;
    }

    function getChannelAvailableDeposit(
        Participant storage participant1_state,
        Participant storage participant2_state
    )
        view
        internal
        returns (uint256 total_available_deposit)
    {
        total_available_deposit = (
            participant1_state.deposit +
            participant2_state.deposit -
            participant1_state.withdrawn_amount -
            participant2_state.withdrawn_amount
        );
    }

    function getMaxPossibleReceivableAmount(
        SettlementData participant1_settlement,
        SettlementData participant2_settlement
    )
        view
        internal
        returns (uint256)
    {
        uint256 participant1_max_transferred;
        uint256 participant2_max_transferred;
        uint256 participant1_net_max_transferred;
        uint256 participant1_max_amount;

        // This is the maximum possible amount that participant1 could transfer to participant2,
        // if all the pending lock secrets have been registered
        participant1_max_transferred = failsafe_addition(
            participant1_settlement.transferred,
            participant1_settlement.locked
        );

        // This is the maximum possible amount that participant2 could transfer to participant1,
        // if all the pending lock secrets have been registered
        participant2_max_transferred = failsafe_addition(
            participant2_settlement.transferred,
            participant2_settlement.locked
        );

        // We enforce this check artificially, in order to get rid of some hard to deal with cases
        // This means settleChannel must be called with ordered values
        require(participant2_max_transferred >= participant1_max_transferred);

        assert(participant1_max_transferred >= participant1_settlement.transferred);
        assert(participant2_max_transferred >= participant2_settlement.transferred);

        // This is the maximum amount that participant2 can receive from participant1, after
        // we take into account all the transferred or pending amounts
        participant1_net_max_transferred = (
            participant2_max_transferred -
            participant1_max_transferred
        );

        // Next, we add the participant1's deposit and subtract the already withdrawn amount
        participant1_max_amount = failsafe_addition(
            participant1_net_max_transferred,
            participant1_settlement.deposit
        );

        // Subtract already withdrawn amount
        (participant1_max_amount, ) = failsafe_subtract(
            participant1_max_amount,
            participant1_settlement.withdrawn
        );
        return participant1_max_amount;
    }

    function verifyBalanceHashData(
        Participant storage participant,
        uint256 transferred_amount,
        uint256 locked_amount,
        bytes32 locksroot
    )
        view
        internal
        returns (bool)
    {
        // When no balance proof has been provided, we need to check this separately because
        // hashing values of 0 outputs a value != 0
        if (participant.balance_hash == 0 &&
            transferred_amount == 0 &&
            locked_amount == 0 &&
            locksroot == 0
        ) {
            return true;
        }

        // Make sure the hash of the provided state is the same as the stored balance_hash
        return participant.balance_hash == keccak256(abi.encodePacked(
            transferred_amount,
            locked_amount,
            locksroot
        ));
    }

    /// @dev Returns the channel specific data.
    /// @param participant1 Address of one of the channel participants.
    /// @param participant2 Address of the other channel participant.
    /// @return Channel state and settle_block_number.
    function getChannelInfo(address participant1, address participant2)
        view
        external
        returns (bytes32, uint256, uint8)
    {
        bytes32 channel_identifier;

        channel_identifier = getChannelIdentifier(participant1, participant2);
        Channel storage channel = channels[channel_identifier];

        return (
            channel_identifier,
            channel.settle_block_number,
            channel.state
        );
    }

    /// @dev Returns the channel specific data.
    /// @param participant Address of the channel participant whose data will be returned.
    /// @param partner Address of the participant's channel partner.
    /// @return Participant's channel deposit, whether the participant has called
    /// `closeChannel` or not, balance_hash and nonce.
    function getChannelParticipantInfo(address participant, address partner)
        view
        external
        returns (uint256, uint256, bool, bytes32, uint256)
    {
        bytes32 channel_identifier;
        channel_identifier = getChannelIdentifier(participant, partner);

        Participant storage participant_state = channels[channel_identifier].participants[
            participant
        ];

        return (
            participant_state.deposit,
            participant_state.withdrawn_amount,
            participant_state.is_the_closer,
            participant_state.balance_hash,
            participant_state.nonce
        );
    }

    /// @dev Returns the locked amount of tokens for a given locksroot.
    /// @param participant1 Address of a channel participant.
    /// @param participant2 Address of the other channel participant.
    /// @return The amount of tokens locked in the contract.
    function getParticipantLockedAmount(
        address participant1,
        address participant2,
        bytes32 locksroot
    )
        view
        public
        returns (uint256)
    {
        bytes32 channel_identifier;
        channel_identifier = getChannelIdentifier(participant1, participant2);
        UnlockData storage unlock_data = channel_identifier_to_unlock_data[channel_identifier];

        return unlock_data.locksroot_to_locked_amount[locksroot];
    }

    /*
     * Internal Functions
     */

    function recoverAddressFromBalanceProof(
        bytes32 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes signature
    )
        view
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            balance_hash,
            nonce,
            additional_hash,
            channel_identifier,
            address(this),
            chain_id
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }

    function recoverAddressFromBalanceProofUpdateMessage(
        bytes32 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes closing_signature,
        bytes non_closing_signature
    )
        view
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            balance_hash,
            nonce,
            additional_hash,
            channel_identifier,
            address(this),
            chain_id,
            closing_signature
        ));

        signature_address = ECVerify.ecverify(message_hash, non_closing_signature);
    }

    function recoverAddressFromCooperativeSettleSignature(
        bytes32 channel_identifier,
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
        bytes32 message_hash = keccak256(abi.encodePacked(
            participant1,
            participant1_balance,
            participant2,
            participant2_balance,
            channel_identifier,
            address(this),
            chain_id
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }

    function recoverAddressFromWithdrawMessage(
        bytes32 channel_identifier,
        address participant,
        uint256 total_withdraw,
        bytes signature
    )
        view
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            participant,
            total_withdraw,
            channel_identifier,
            address(this),
            chain_id
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }

    function verifyWithdrawSignatures(
        bytes32 channel_identifier,
        address participant,
        address partner,
        uint256 total_withdraw,
        bytes participant_signature,
        bytes partner_signature
    )
        view
        internal
    {
        address recovered_participant_address;
        address recovered_partner_address;

        recovered_participant_address = recoverAddressFromWithdrawMessage(
            channel_identifier,
            participant,
            total_withdraw,
            participant_signature
        );
        recovered_partner_address = recoverAddressFromWithdrawMessage(
            channel_identifier,
            participant,
            total_withdraw,
            partner_signature
        );
        // Check recovered addresses from signatures
        require(participant == recovered_participant_address);
        require(partner == recovered_partner_address);
    }

    function getMerkleRootAndUnlockedAmount(bytes merkle_tree_leaves)
        view
        internal
        returns (bytes32, uint256)
    {
        uint256 length = merkle_tree_leaves.length;

        // each merkle_tree lock component has this form:
        // (locked_amount || expiration_block || secrethash) = 3 * 32 bytes
        require(length % 96 == 0);

        uint256 i;
        uint256 total_unlocked_amount;
        uint256 unlocked_amount;
        bytes32 lockhash;
        bytes32 merkle_root;

        bytes32[] memory merkle_layer = new bytes32[](length / 96 + 1);

        for (i = 32; i < length; i += 96) {
            (lockhash, unlocked_amount) = getLockDataFromMerkleTree(merkle_tree_leaves, i);
            total_unlocked_amount += unlocked_amount;
            merkle_layer[i / 96] = lockhash;
        }

        length /= 96;

        while (length > 1) {
            if (length % 2 != 0) {
                merkle_layer[length] = merkle_layer[length - 1];
                length += 1;
            }

            for (i = 0; i < length - 1; i += 2) {
                if (merkle_layer[i] == merkle_layer[i + 1]) {
                    lockhash = merkle_layer[i];
                } else if (merkle_layer[i] < merkle_layer[i + 1]) {
                    lockhash = keccak256(abi.encodePacked(merkle_layer[i], merkle_layer[i + 1]));
                } else {
                    lockhash = keccak256(abi.encodePacked(merkle_layer[i + 1], merkle_layer[i]));
                }
                merkle_layer[i / 2] = lockhash;
            }
            length = i / 2;
        }

        merkle_root = merkle_layer[0];

        return (merkle_root, total_unlocked_amount);
    }

    function getLockDataFromMerkleTree(bytes merkle_tree_leaves, uint256 offset)
        view
        internal
        returns (bytes32, uint256)
    {
        uint256 expiration_block;
        uint256 locked_amount;
        uint256 reveal_block;
        bytes32 secrethash;
        bytes32 lockhash;

        if (merkle_tree_leaves.length <= offset) {
            return (lockhash, 0);
        }

        assembly {
            expiration_block := mload(add(merkle_tree_leaves, offset))
            locked_amount := mload(add(merkle_tree_leaves, add(offset, 32)))
            secrethash := mload(add(merkle_tree_leaves, add(offset, 64)))
        }

        // Calculate the lockhash for computing the merkle root
        lockhash = keccak256(abi.encodePacked(expiration_block, locked_amount, secrethash));

        // Check if the lock's secret was revealed in the SecretRegistry
        // The secret must have been revealed in the SecretRegistry contract before the lock's
        // expiration_block in order for the hash time lock transfer to be successful.
        reveal_block = secret_registry.getSecretRevealBlockHeight(secrethash);
        if (reveal_block == 0 || expiration_block <= reveal_block) {
            locked_amount = 0;
        }

        return (lockhash, locked_amount);
    }

    function min(uint256 a, uint256 b) pure internal returns (uint256)
    {
        return a > b ? b : a;
    }

    function max(uint256 a, uint256 b) pure internal returns (uint256)
    {
        return a > b ? a : b;
    }

    /// @dev Special subtraction function that does not fail when underflowing.
    /// @param a Minuend
    /// @param b Subtrahend
    /// @return Minimum between the result of the subtraction and 0, the maximum subtrahend for which no underflow occurs.
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
    /// @return Maximum between the result of the addition or the maximum uint256 value.
    function failsafe_addition(uint256 a, uint256 b)
        pure
        internal
        returns (uint256)
    {
        uint256 sum = a + b;
        return sum >= a ? sum : MAX_SAFE_UINT256;
    }
}
