pragma solidity ^0.4.23;

import "raiden/Token.sol";
import "raiden/Utils.sol";
import "raiden/lib/ECVerify.sol";
import "raiden/SecretRegistry.sol";

/// @title TokenNetwork
/// @notice Stores and manages all the Raiden Network channels that use the
/// token specified
/// in this TokenNetwork contract.
contract TokenNetwork is Utils {

    string constant public contract_version = "0.3._";

    // Instance of the token used by the channels
    Token public token;

    // Instance of SecretRegistry used for storing secrets revealed in a
    // mediating transfer.
    SecretRegistry public secret_registry;

    // Chain ID as specified by EIP155 used in balance proof signatures to
    // avoid replay attacks
    uint256 public chain_id;

    uint256 public settlement_timeout_min;
    uint256 public settlement_timeout_max;

    uint256 constant public MAX_SAFE_UINT256 = (
        115792089237316195423570985008687907853269984665640564039457584007913129639935
    );

    // Bug bounty release deposit limit
    uint256 public deposit_limit;

    // Global, monotonically increasing counter that keeps track of all the
    // opened channels in this contract
    uint256 public channel_counter;

    // channel_identifier => Channel
    // channel identifier is the channel_counter value at the time of opening
    // the channel
    mapping (uint256 => Channel) public channels;

    // This is needed to enforce one channel per pair of participants
    // The key is keccak256(participant1_address, participant2_address)
    mapping (bytes32 => uint256) public participants_hash_to_channel_identifier;

    // We keep the unlock data in a separate mapping to allow channel data
    // structures to be removed when settling uncooperatively. If there are
    // locked pending transfers, we need to store data needed to unlock them at
    // a later time.
    // The key is `keccak256(uint256 channel_identifier, address participant,
    // address partner)` Where `participant` is the participant that sent the
    // pending transfers We need `partner` for knowing where to send the
    // claimable tokens
    mapping(bytes32 => UnlockData) unlock_identifier_to_unlock_data;

    struct Participant {
        // Total amount of tokens transferred to this smart contract through
        // the `setTotalDeposit` function, for a specific channel, in the
        // participant's benefit.
        // This is a strictly monotonic value. Note that direct token transfer
        // cannot be tracked and will be burned.
        uint256 deposit;

        // Total amount of tokens withdrawn by the participant during the
        // lifecycle of this channel.
        // This is a strictly monotonic value.
        uint256 withdrawn_amount;

        // This is a value set to true after the channel has been closed, only
        // if this is the participant who closed the channel.
        bool is_the_closer;

        // keccak256 of the balance data provided after a closeChannel or an
        // updateNonClosingBalanceProof call
        bytes32 balance_hash;

        // Monotonically increasing counter of the off-chain transfers,
        // provided along with the balance_hash
        uint256 nonce;
    }

    enum ChannelState {
        NonExistent, // 0
        Opened,      // 1
        Closed,      // 2
        Settled,     // 3; Note: The channel has at least one pending unlock
        Removed      // 4; Note: Channel data is removed, there are no pending unlocks
    }

    struct Channel {
        // After opening the channel this value represents the settlement
        // window. This is the number of blocks that need to be mined between
        // closing the channel uncooperatively and settling the channel.
        // After the channel has been uncooperatively closed, this value
        // represents the block number after which settleChannel can be called.
        uint256 settle_block_number;

        ChannelState state;

        mapping(address => Participant) participants;
    }

    struct SettlementData {
        uint256 deposit;
        uint256 withdrawn;
        uint256 transferred;
        uint256 locked;
    }

    struct UnlockData {
        // Merkle root of the pending transfers tree from the Raiden client
        bytes32 locksroot;
        // Total amount of tokens locked in the pending transfers corresponding
        // to the `locksroot`
        uint256 locked_amount;
    }

    event ChannelOpened(
        uint256 indexed channel_identifier,
        address indexed participant1,
        address indexed participant2,
        uint256 settle_timeout
    );

    event ChannelNewDeposit(
        uint256 indexed channel_identifier,
        address indexed participant,
        uint256 total_deposit
    );

    // total_withdraw is how much the participant has withdrawn during the
    // lifetime of the channel. The actual amount which the participant withdrew
    // is `total_withdraw - total_withdraw_from_previous_event_or_zero`
    event ChannelWithdraw(
        uint256 indexed channel_identifier,
        address indexed participant,
        uint256 total_withdraw
    );

    event ChannelClosed(
        uint256 indexed channel_identifier,
        address indexed closing_participant
    );

    event ChannelUnlocked(
        uint256 indexed channel_identifier,
        address indexed participant,
        address indexed partner,
        bytes32 locksroot,
        uint256 unlocked_amount,
        uint256 returned_tokens
    );

    event NonClosingBalanceProofUpdated(
        uint256 indexed channel_identifier,
        address indexed closing_participant,
        uint256 nonce
    );

    event ChannelSettled(
        uint256 indexed channel_identifier,
        uint256 participant1_amount,
        uint256 participant2_amount
    );

    modifier isOpen(uint256 channel_identifier) {
        require(channels[channel_identifier].state == ChannelState.Opened);
        _;
    }

    modifier settleTimeoutValid(uint256 timeout) {
        require(timeout >= settlement_timeout_min);
        require(timeout <= settlement_timeout_max);
        _;
    }

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

        // Try to get token decimals, otherwise assume 18
        bool exists = address(token).call(bytes4(keccak256("decimals()")));
        uint8 decimals = 18;
        if (exists) {
            decimals = token.decimals();
        }

        deposit_limit = 100 * (10 ** uint256(decimals));
    }

    /// @notice Opens a new channel between `participant1` and `participant2`.
    /// Can be called by anyone.
    /// @param participant1 Ethereum address of a channel participant.
    /// @param participant2 Ethereum address of the other channel participant.
    /// @param settle_timeout Number of blocks that need to be mined between a
    /// call to closeChannel and settleChannel.
    function openChannel(address participant1, address participant2, uint256 settle_timeout)
        settleTimeoutValid(settle_timeout)
        public
        returns (uint256)
    {
        bytes32 pair_hash;
        uint256 channel_identifier;

        // First increment the counter
        // There will never be a channel with channel_identifier == 0
        channel_counter += 1;
        channel_identifier = channel_counter;

        pair_hash = getParticipantsHash(participant1, participant2);

        // There must only be one channel opened between two participants at
        // any moment in time.
        require(participants_hash_to_channel_identifier[pair_hash] == 0);
        participants_hash_to_channel_identifier[pair_hash] = channel_identifier;

        Channel storage channel = channels[channel_identifier];

        require(channel.settle_block_number == 0);
        require(channel.state == ChannelState.NonExistent);

        // Store channel information
        channel.settle_block_number = settle_timeout;
        channel.state = ChannelState.Opened;

        emit ChannelOpened(
            channel_identifier,
            participant1,
            participant2,
            settle_timeout
        );

        return channel_identifier;
    }

    /// @notice Sets the channel participant total deposit value.
    /// Can be called by anyone.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant Channel participant whose deposit is being set.
    /// @param total_deposit The total amount of tokens that the participant
    /// will have as a deposit.
    /// @param partner Channel partner address, needed to compute the total
    /// channel deposit.
    function setTotalDeposit(
        uint256 channel_identifier,
        address participant,
        uint256 total_deposit,
        address partner
    )
        isOpen(channel_identifier)
        public
    {
        require(channel_identifier == getChannelIdentifier(participant, partner));
        require(total_deposit > 0);
        require(total_deposit <= deposit_limit);

        uint256 added_deposit;
        uint256 channel_deposit;

        Channel storage channel = channels[channel_identifier];
        Participant storage participant_state = channel.participants[participant];
        Participant storage partner_state = channel.participants[partner];

        // Calculate the actual amount of tokens that will be transferred
        added_deposit = total_deposit - participant_state.deposit;

        // Update the participant's channel deposit
        participant_state.deposit += added_deposit;

        // Calculate the entire channel deposit, to avoid overflow
        channel_deposit = participant_state.deposit + partner_state.deposit;

        emit ChannelNewDeposit(
            channel_identifier,
            participant,
            participant_state.deposit
        );

        // Do the transfer
        require(token.transferFrom(msg.sender, address(this), added_deposit));

        require(participant_state.deposit >= added_deposit);
        require(channel_deposit >= participant_state.deposit);
        require(channel_deposit >= partner_state.deposit);
    }

    /// @notice Allows `participant` to withdraw tokens from the channel that he
    /// has with `partner`, without closing it. Can be called by anyone. Can
    /// only be called once per each signed withdraw message.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant Channel participant, who will receive the withdrawn
    /// amount.
    /// @param total_withdraw Total amount of tokens that are marked as
    /// withdrawn from the channel during the channel lifecycle.
    /// @param partner Channel partner address, needed to compute the total
    /// channel deposit.
    /// @param participant_signature Participant's signature on the withdraw
    /// data.
    /// @param partner_signature Partner's signature on the withdraw data.
    function setTotalWithdraw(
        uint256 channel_identifier,
        address participant,
        uint256 total_withdraw,
        address partner,
        bytes participant_signature,
        bytes partner_signature
    )
        external
    {
        require(channel_identifier == getChannelIdentifier(participant, partner));
        require(total_withdraw > 0);

        uint256 total_deposit;
        uint256 current_withdraw;

        Channel storage channel = channels[channel_identifier];
        Participant storage participant_state = channel.participants[participant];
        Participant storage partner_state = channel.participants[partner];

        total_deposit = participant_state.deposit + partner_state.deposit;

        // Using the total_withdraw (monotonically increasing) in the signed
        // message ensures that we do not allow reply attack to happen, by
        // using the same withdraw proof twice.
        current_withdraw = total_withdraw - participant_state.withdrawn_amount;

        participant_state.withdrawn_amount += current_withdraw;

        // Do the tokens transfer
        require(token.transfer(participant, current_withdraw));
        require(channel.state == ChannelState.Opened);

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

        // Entire withdrawn amount must not be bigger than the entire channel
        // deposit
        require(participant_state.withdrawn_amount <= (total_deposit - partner_state.withdrawn_amount));

        require(total_deposit >= participant_state.deposit);
        require(total_deposit >= partner_state.deposit);

        // A withdraw should never happen if a participant already has a
        // balance proof in storage
        assert(participant_state.nonce == 0);
        assert(partner_state.nonce == 0);

        emit ChannelWithdraw(
            channel_identifier,
            participant,
            participant_state.withdrawn_amount
        );
    }

    /// @notice Close the channel defined by the two participant addresses. Only
    /// a participant may close the channel, providing a balance proof signed by
    /// its partner. Callable only once.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param partner Channel partner of the `msg.sender`, who provided the
    /// signature.
    /// @param balance_hash Hash of (transferred_amount, locked_amount,
    /// locksroot).
    /// @param additional_hash Computed from the message. Used for message
    /// authentication.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param signature Partner's signature of the balance proof data.
    function closeChannel(
        uint256 channel_identifier,
        address partner,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes signature
    )
        isOpen(channel_identifier)
        public
    {
        require(channel_identifier == getChannelIdentifier(msg.sender, partner));

        address recovered_partner_address;

        Channel storage channel = channels[channel_identifier];

        channel.state = ChannelState.Closed;
        channel.participants[msg.sender].is_the_closer = true;

        // This is the block number at which the channel can be settled.
        channel.settle_block_number += uint256(block.number);

        // Nonce 0 means that the closer never received a transfer, therefore
        // never received a balance proof, or he is intentionally not providing
        // the latest transfer, in which case the closing party is going to
        // lose the tokens that were transferred to him.
        if (nonce > 0) {
            recovered_partner_address = recoverAddressFromBalanceProof(
                channel_identifier,
                balance_hash,
                nonce,
                additional_hash,
                signature
            );

            updateBalanceProofData(
                channel,
                recovered_partner_address,
                nonce,
                balance_hash
            );

            // Signature must be from the channel partner
            require(partner == recovered_partner_address);
        }

        emit ChannelClosed(channel_identifier, msg.sender);
    }

    /// @notice Called on a closed channel, the function allows the non-closing
    /// participant to provide the last balance proof, which modifies the
    /// closing participant's state. Can be called multiple times by anyone.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param closing_participant Channel participant who closed the channel.
    /// @param non_closing_participant Channel participant who needs to update
    /// the balance proof.
    /// @param balance_hash Hash of (transferred_amount, locked_amount,
    /// locksroot).
    /// @param additional_hash Computed from the message. Used for message
    /// authentication.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param closing_signature Closing participant's signature of the balance
    /// proof data.
    /// @param non_closing_signature Non-closing participant signature of the
    /// balance proof data.
    function updateNonClosingBalanceProof(
        uint256 channel_identifier,
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
        require(channel_identifier == getChannelIdentifier(
            closing_participant,
            non_closing_participant
        ));
        require(balance_hash != 0x0);
        require(nonce > 0);

        address recovered_non_closing_participant;
        address recovered_closing_participant;

        Channel storage channel = channels[channel_identifier];

        // We need the signature from the non-closing participant to allow
        // anyone to make this transaction. E.g. a monitoring service.
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

        emit NonClosingBalanceProofUpdated(
            channel_identifier,
            closing_participant,
            nonce
        );

        require(channel.state == ChannelState.Closed);

        // Channel must be in the settlement window
        require(channel.settle_block_number >= block.number);

        // Make sure the first signature is from the closing participant
        require(closing_participant_state.is_the_closer);

        require(closing_participant == recovered_closing_participant);
        require(non_closing_participant == recovered_non_closing_participant);
    }

    /// @notice Settles the balance between the two parties. Note that arguments
    /// order counts: `participant1_transferred_amount +
    /// participant1_locked_amount` <= `participant2_transferred_amount +
    /// participant2_locked_amount`
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant1 Channel participant.
    /// @param participant1_transferred_amount The latest known amount of tokens
    /// transferred from `participant1` to `participant2`.
    /// @param participant1_locked_amount Amount of tokens owed by
    /// `participant1` to `participant2`, contained in locked transfers that
    /// will be retrieved by calling `unlock` after the channel is settled.
    /// @param participant1_locksroot The latest known merkle root of the
    /// pending hash-time locks of `participant1`, used to validate the unlocked
    /// proofs.
    /// @param participant2 Other channel participant.
    /// @param participant2_transferred_amount The latest known amount of tokens
    /// transferred from `participant2` to `participant1`.
    /// @param participant2_locked_amount Amount of tokens owed by
    /// `participant2` to `participant1`, contained in locked transfers that
    /// will be retrieved by calling `unlock` after the channel is settled.
    /// @param participant2_locksroot The latest known merkle root of the
    /// pending hash-time locks of `participant2`, used to validate the unlocked
    /// proofs.
    function settleChannel(
        uint256 channel_identifier,
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
        require(channel_identifier == getChannelIdentifier(participant1, participant2));

        bytes32 pair_hash;

        pair_hash = getParticipantsHash(participant1, participant2);
        Channel storage channel = channels[channel_identifier];

        require(channel.state == ChannelState.Closed);

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

        // We are calculating the final token amounts that need to be
        // transferred to the participants and the amount of tokens that need
        // to remain locked in the contract. These tokens can be unlocked by
        // calling `unlock`.
        // participant1_transferred_amount is the amount of tokens that
        // participant1 will receive.
        // participant2_transferred_amount is the amount of tokens that
        // participant2 will receive.
        // We are reusing variables due to the local variables number limit.
        // For better readability this can be refactored further.
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

        // Remove the pair's channel counter
        delete participants_hash_to_channel_identifier[pair_hash];

        // Store balance data needed for `unlock`
        storeUnlockData(
            channel_identifier,
            participant1,
            participant2,
            participant1_locked_amount,
            participant1_locksroot
        );
        storeUnlockData(
            channel_identifier,
            participant2,
            participant1,
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

    /// @notice Unlocks all pending off-chain transfers from `partner` to
    /// `participant` and sends the locked tokens corresponding to locks with
    /// secrets registered on-chain to the `participant`. Locked tokens
    /// corresponding to locks where the secret was not revelead on-chain will
    /// return to the `partner`. Anyone can call unlock.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant Address who will receive the claimable unlocked
    /// tokens.
    /// @param partner Address who sent the pending transfers and will receive
    /// the unclaimable unlocked tokens.
    /// @param merkle_tree_leaves The entire merkle tree of pending transfers
    /// that `partner` sent to `participant`.
    function unlock(
        uint256 channel_identifier,
        address participant,
        address partner,
        bytes merkle_tree_leaves
    )
        public
    {
        // Channel represented by channel_identifier must be settled and
        // channel data deleted
        require(channel_identifier != getChannelIdentifier(participant, partner));

        // After the channel is settled the storage is cleared, therefore the
        // value will be NonExistent and not Settled. The value Settled is used
        // for the external APIs
        require(channels[channel_identifier].state == ChannelState.NonExistent);

        require(merkle_tree_leaves.length > 0);

        bytes32 unlock_key;
        bytes32 locksroot;
        bytes32 computed_locksroot;
        uint256 unlocked_amount;
        uint256 locked_amount;
        uint256 returned_tokens;

        // Calculate the locksroot for the pending transfers and the amount of
        // tokens corresponding to the locked transfers with secrets revealed
        // on chain.
        (computed_locksroot, unlocked_amount) = getMerkleRootAndUnlockedAmount(
            merkle_tree_leaves
        );

        // The partner must have a non-empty locksroot on-chain that must be
        // the same as the computed locksroot.
        // Get the amount of tokens that have been left in the contract, to
        // account for the pending transfers `partner` -> `participant`.
        unlock_key = getUnlockIdentifier(channel_identifier, partner, participant);
        UnlockData storage unlock_data = unlock_identifier_to_unlock_data[unlock_key];
        locked_amount = unlock_data.locked_amount;

        // Locksroot must be the same as the computed locksroot
        require(unlock_data.locksroot == computed_locksroot);

        // There are no pending transfers if the locked_amount is 0.
        // Transaction must fail
        require(locked_amount > 0);

        // Make sure we don't transfer more tokens than previously reserved in
        // the smart contract.
        unlocked_amount = min(unlocked_amount, locked_amount);

        // Transfer the rest of the tokens back to the partner
        returned_tokens = locked_amount - unlocked_amount;

        // Remove partner's unlock data
        delete unlock_identifier_to_unlock_data[unlock_key];

        // Transfer the unlocked tokens to the participant. unlocked_amount can
        // be 0
        if (unlocked_amount > 0) {
            require(token.transfer(participant, unlocked_amount));
        }

        // Transfer the rest of the tokens back to the partner
        if (returned_tokens > 0) {
            require(token.transfer(partner, returned_tokens));
        }

        emit ChannelUnlocked(
            channel_identifier,
            participant,
            partner,
            computed_locksroot,
            unlocked_amount,
            returned_tokens
        );

        // At this point, this should always be true
        assert(locked_amount >= returned_tokens);
        assert(locked_amount >= unlocked_amount);
    }

    /// @notice Cooperatively settles the balances between the two channel
    /// participants and transfers the agreed upon token amounts to the
    /// participants. After this the channel lifecycle has ended and no more
    /// operations can be done on it.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant1_address Address of channel participant.
    /// @param participant1_balance Amount of tokens that `participant1_address`
    /// must receive when the channel is settled and removed.
    /// @param participant2_address Address of the other channel participant.
    /// @param participant2_balance Amount of tokens that `participant2_address`
    /// must receive when the channel is settled and removed.
    /// @param participant1_signature Signature of `participant1_address` on the
    /// cooperative settle message.
    /// @param participant2_signature Signature of `participant2_address` on the
    /// cooperative settle message.
    function cooperativeSettle(
        uint256 channel_identifier,
        address participant1_address,
        uint256 participant1_balance,
        address participant2_address,
        uint256 participant2_balance,
        bytes participant1_signature,
        bytes participant2_signature
    )
        public
    {
        require(channel_identifier == getChannelIdentifier(
            participant1_address,
            participant2_address
        ));
        bytes32 pair_hash;
        address participant1;
        address participant2;
        uint256 total_available_deposit;

        pair_hash = getParticipantsHash(participant1_address, participant2_address);
        Channel storage channel = channels[channel_identifier];

        require(channel.state == ChannelState.Opened);

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

        // Remove the pair's channel counter
        delete participants_hash_to_channel_identifier[pair_hash];


        // Do the token transfers
        if (participant1_balance > 0) {
            require(token.transfer(participant1, participant1_balance));
        }

        if (participant2_balance > 0) {
            require(token.transfer(participant2, participant2_balance));
        }

        // The provided addresses must be the same as the recovered ones
        require(participant1 == participant1_address);
        require(participant2 == participant2_address);

        // The sum of the provided balances must be equal to the total
        // available deposit
        require(total_available_deposit == (participant1_balance + participant2_balance));
        emit ChannelSettled(channel_identifier, participant1_balance, participant2_balance);

    }

    /// @notice Returns the unique identifier for the channel given by the
    /// contract.
    /// @param participant Address of a channel participant.
    /// @param partner Address of the other channel participant.
    /// @return Unique identifier for the channel. It can be 0 if channel does
    /// not exist.
    function getChannelIdentifier(address participant, address partner)
        view
        public
        returns (uint256)
    {
        require(participant != 0x0);
        require(partner != 0x0);
        require(participant != partner);

        bytes32 pair_hash = getParticipantsHash(participant, partner);
        return participants_hash_to_channel_identifier[pair_hash];
    }

    /// @dev Returns the channel specific data.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant1 Address of a channel participant.
    /// @param participant2 Address of the other channel participant.
    /// @return Channel settle_block_number and state.
    function getChannelInfo(
        uint256 channel_identifier,
        address participant1,
        address participant2
    )
        view
        external
        returns (uint256, ChannelState)
    {
        bytes32 unlock_key1;
        bytes32 unlock_key2;

        Channel storage channel = channels[channel_identifier];
        ChannelState state = channel.state;  // This must **not** update the storage

        if (state == ChannelState.NonExistent &&
            channel_identifier > 0 &&
            channel_identifier <= channel_counter
        ) {
            // The channel has been settled, channel data is removed Therefore,
            // the channel state in storage is actually `0`, or `NonExistent`
            // However, for this view function, we return `Settled`, in order
            // to provide a consistent external API
            state = ChannelState.Settled;

            // We might still have data stored for future unlock operations
            // Only if we do not, we can consider the channel as `Removed`
            unlock_key1 = getUnlockIdentifier(channel_identifier, participant1, participant2);
            UnlockData storage unlock_data1 = unlock_identifier_to_unlock_data[unlock_key1];

            unlock_key2 = getUnlockIdentifier(channel_identifier, participant2, participant1);
            UnlockData storage unlock_data2 = unlock_identifier_to_unlock_data[unlock_key2];

            if (unlock_data1.locked_amount == 0 && unlock_data2.locked_amount == 0) {
                state = ChannelState.Removed;
            }
        }

        return (
            channel.settle_block_number,
            state
        );
    }

    /// @dev Returns the channel specific data.
    /// @param channel_identifier Identifier for the channel on which this
    /// operation takes place.
    /// @param participant Address of the channel participant whose data will be
    /// returned.
    /// @param partner Address of the channel partner.
    /// @return Participant's deposit, withdrawn_amount, whether the participant
    /// has called `closeChannel` or not, balance_hash, nonce, locksroot,
    /// locked_amount.
    function getChannelParticipantInfo(
            uint256 channel_identifier,
            address participant,
            address partner
    )
        view
        external
        returns (uint256, uint256, bool, bytes32, uint256, bytes32, uint256)
    {
        bytes32 unlock_key;

        Participant storage participant_state = channels[channel_identifier].participants[
            participant
        ];
        unlock_key = getUnlockIdentifier(channel_identifier, participant, partner);
        UnlockData storage unlock_data = unlock_identifier_to_unlock_data[unlock_key];

        return (
            participant_state.deposit,
            participant_state.withdrawn_amount,
            participant_state.is_the_closer,
            participant_state.balance_hash,
            participant_state.nonce,
            unlock_data.locksroot,
            unlock_data.locked_amount
        );
    }

    /// @dev Get the hash of the participant addresses, ordered
    /// lexicographically.
    /// @param participant Address of a channel participant.
    /// @param partner Address of the other channel participant.
    function getParticipantsHash(address participant, address partner)
        pure
        public
        returns (bytes32)
    {
        require(participant != 0x0);
        require(partner != 0x0);
        require(participant != partner);

        if (participant < partner) {
            return keccak256(abi.encodePacked(participant, partner));
        } else {
            return keccak256(abi.encodePacked(partner, participant));
        }
    }

    function getUnlockIdentifier(
        uint256 channel_identifier,
        address participant,
        address partner
    )
        pure
        public
        returns (bytes32)
    {
        require(participant != partner);
        return keccak256(abi.encodePacked(channel_identifier, participant, partner));
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

        // Multiple calls to updateNonClosingBalanceProof can be made and we
        // need to store the last known balance proof data
        require(nonce > participant_state.nonce);

        participant_state.nonce = nonce;
        participant_state.balance_hash = balance_hash;
    }

    function storeUnlockData(
        uint256 channel_identifier,
        address participant,
        address partner,
        uint256 locked_amount,
        bytes32 locksroot
    )
        internal
    {
        // If there are transfers to unlock, store the locksroot and total
        // amount of tokens
        if (locked_amount == 0 || locksroot == 0) {
            return;
        }

        bytes32 key = getUnlockIdentifier(channel_identifier, participant, partner);
        UnlockData storage unlock_data = unlock_identifier_to_unlock_data[key];
        unlock_data.locksroot = locksroot;
        unlock_data.locked_amount = locked_amount;
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

    /// @dev Function that calculates the amount of tokens that the participants
    /// will receive when calling settleChannel.
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
        // Cases that require attention:
        // case1. If participant1 does NOT provide a balance proof or provides
        // an old balance proof.  participant2_transferred_amount can be [0,
        // real_participant2_transferred_amount) We need to punish
        // participant1.
        // case2. If participant2 does NOT provide a balance proof or provides
        // an old balance proof.  participant1_transferred_amount can be [0,
        // real_participant1_transferred_amount) We need to punish
        // participant2.
        // case3. If neither participants provide a balance proof, we just
        // subtract their withdrawn amounts from their deposits.

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

        // This amount is the maximum possible amount that participant1 can
        // receive and also contains the entire locked amount of the pending
        // transfers from participant2 to participant1.
        participant1_amount = getMaxPossibleReceivableAmount(
            participant1_settlement,
            participant2_settlement
        );

        // We need to bound this to the available channel deposit
        participant1_amount = min(participant1_amount, total_available_deposit);

        // Now it is safe to subtract without underflow
        participant2_amount = total_available_deposit - participant1_amount;

        // We take out the pending transfers locked amount, bounding it by the
        // maximum receivable amount.
        (participant1_amount, participant2_locked_amount) = failsafe_subtract(
            participant1_amount,
            participant2_locked_amount
        );

        // We take out the pending transfers locked amount, bounding it by the
        // maximum receivable amount.
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

        // We enforce this check artificially, in order to get rid of some hard
        // to deal with cases This means settleChannel must be called with
        // ordered values
        require(participant2_max_transferred >= participant1_max_transferred);

        assert(participant1_max_transferred >= participant1_settlement.transferred);
        assert(participant2_max_transferred >= participant2_settlement.transferred);

        // This is the maximum amount that participant2 can receive from
        // participant1, after we take into account all the transferred or
        // pending amounts
        participant1_net_max_transferred = (
            participant2_max_transferred -
            participant1_max_transferred
        );

        // Next, we add the participant1's deposit and subtract the already
        // withdrawn amount
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
        // When no balance proof has been provided, we need to check this
        // separately because hashing values of 0 outputs a value != 0
        if (participant.balance_hash == 0 &&
            transferred_amount == 0 &&
            locked_amount == 0 &&
            locksroot == 0
        ) {
            return true;
        }

        // Make sure the hash of the provided state is the same as the stored
        // balance_hash
        return participant.balance_hash == keccak256(abi.encodePacked(
            transferred_amount,
            locked_amount,
            locksroot
        ));
    }

    function recoverAddressFromBalanceProof(
        uint256 channel_identifier,
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
        uint256 channel_identifier,
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
        uint256 channel_identifier,
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
        uint256 channel_identifier,
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

    /// @dev Calculates the merkle root for the pending transfers data and
    //calculates the amount / of tokens that can be unlocked because the secret
    //was registered on-chain.
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

        // Check if the lock's secret was revealed in the SecretRegistry The
        // secret must have been revealed in the SecretRegistry contract before
        // the lock's expiration_block in order for the hash time lock transfer
        // to be successful.
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
        uint256 sum = a + b;
        return sum >= a ? sum : MAX_SAFE_UINT256;
    }
}
