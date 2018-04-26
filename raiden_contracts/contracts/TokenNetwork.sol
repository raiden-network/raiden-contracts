pragma solidity ^0.4.17;

import "./Token.sol";
import "./Utils.sol";
import "./lib/ECVerify.sol";
import "./SecretRegistry.sol";

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

    // Channel identifier is a uint256, incremented after each new channel
    mapping (uint256 => Channel) public channels;

    // We keep the balance data in a separate mapping to allow channel data structures to be
    // removed when settling the channel. If there are locked transfers, we need to store
    // balance data to be able to unlock them.
    // Key is a hash of the channel_identifier and participant address.
    mapping(bytes32 => BalanceData) balance_data;

    // Used for determining the next channel identifier
    // Start from 1 instead of 0, otherwise the first channel will have an additional
    // 15000 gas cost than the rest
    uint256 public last_channel_index = 0;

    struct Participant {
        // Total amount of token transferred to this smart contract through the
        // `setDeposit` function, note that direct token transfer cannot be
        // tracked and will be burned.
        uint256 deposit;

        // This value is set to true after the channel has been opened.
        // This is an efficient way to mark the channel participants without doing a deposit.
        // This is bytes1 and it gets packed with the rest of the struct data.
        bool initialized;

        // This is a value set to true after the channel has been closed, only if this is the
        // participant who closed the channel.
        // This is bytes1 and it gets packed with the rest of the struct data.
        bool is_the_closer;
    }

    struct BalanceData {
        // This is the balance_hash during the settlement window
        // This can be the locksroot after settlement, if we have locked transfers
        bytes32 balance_hash_or_locksroot;

        // Nonce used in updateNonClosingBalanceProof to compare balance hashes during the
        // settlement window. This is replaced in `settleChannel` by the total amount of tokens
        // locked in pending transfers. This is kept in the contract after settlement and that
        // can be withdrawn by calling `unlock`.
        uint256 nonce_or_locked_amount;
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

    /*
     *  Events
     */

    event ChannelOpened(
        uint256 channel_identifier,
        address participant1,
        address participant2,
        uint256 settle_timeout
    );

    event ChannelNewDeposit(uint256 channel_identifier, address participant, uint256 deposit);

    event ChannelClosed(uint256 channel_identifier, address closing_participant);

    event ChannelUnlocked(
        uint256 channel_identifier,
        address participant,
        uint256 unlocked_amount,
        uint256 returned_tokens
    );

    event NonClosingBalanceProofUpdated(uint256 channel_identifier, address closing_participant);

    event ChannelSettled(uint256 channel_identifier);

    /*
     * Modifiers
     */

    modifier isOpen(uint256 channel_identifier) {
        require(channels[channel_identifier].state == 1);
        _;
    }

    modifier isParticipant(uint256 channel_identifier, address participant) {
        require(channels[channel_identifier].participants[participant].initialized);
        _;
    }

    modifier settleTimeoutValid(uint256 timeout) {
        require(timeout >= 6 && timeout <= 2700000);
        _;
    }

    /*
     *  Constructor
     */

    function TokenNetwork(address _token_address, address _secret_registry, uint256 _chain_id)
        public
    {
        require(_token_address != 0x0);
        require(_secret_registry != 0x0);
        require(_chain_id > 0);
        require(contractExists(_token_address));
        require(contractExists(_secret_registry));

        token = Token(_token_address);

        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);

        secret_registry = SecretRegistry(_secret_registry);
        chain_id = _chain_id;
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
        returns (uint256)
    {
        require(participant1 != 0x0);
        require(participant2 != 0x0);
        require(participant1 != participant2);

        // Increase channel index counter
        last_channel_index += 1;
        Channel storage channel = channels[last_channel_index];

        require(channel.settle_block_number == 0);
        require(channel.state == 0);

        Participant storage participant1_state = channel.participants[participant1];
        Participant storage participant2_state = channel.participants[participant2];

        require(!participant1_state.initialized);
        require(!participant2_state.initialized);

        // Store channel information
        channel.settle_block_number = settle_timeout;
        // Mark channel as opened
        channel.state = 1;

        // Mark the channel participants
        // We use this in other functions to ensure the beneficiary is a channel participant
        participant1_state.initialized = true;
        participant2_state.initialized = true;

        ChannelOpened(last_channel_index, participant1, participant2, settle_timeout);

        return last_channel_index;
    }

    /// @notice Sets the channel participant total deposit value.
    /// Can be called by anyone.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`
    /// @param participant Channel participant whose deposit is being set.
    /// @param total_deposit Idempotent function which sets the total amount of
    /// tokens that the participant will have as a deposit.
    function setDeposit(uint256 channel_identifier, address participant, uint256 total_deposit)
        isOpen(channel_identifier)
        isParticipant(channel_identifier, participant)
        public
    {
        uint256 added_deposit;
        Channel storage channel = channels[channel_identifier];
        Participant storage participant_state = channel.participants[participant];

        require(participant_state.deposit < total_deposit);

        // Calculate the actual amount of tokens that will be transferred
        added_deposit = total_deposit - participant_state.deposit;

        // Update the participant's channel deposit
        participant_state.deposit += added_deposit;

        // Do the transfer
        require(token.transferFrom(msg.sender, address(this), added_deposit));

        ChannelNewDeposit(channel_identifier, participant, participant_state.deposit);
    }

    /// @notice Close a channel between two parties that was used bidirectionally.
    /// Only a participant may close the channel, providing a balance proof
    /// signed by its partner. Callable only once.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`
    /// @param balance_hash Hash of (transferred_amount, locked_amount, locksroot).
    /// @param additional_hash Computed from the message. Used for message authentication.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param signature Partner's signature of the balance proof data.
    function closeChannel(
        uint256 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes signature
    )
        isOpen(channel_identifier)
        isParticipant(channel_identifier, msg.sender)
        public
    {
        address partner_address;

        Channel storage channel = channels[channel_identifier];

        // Mark the channel as closed and mark the closing participant
        channel.state = 2;
        channel.participants[msg.sender].is_the_closer = true;

        // This is the block number at which the channel can be settled.
        channel.settle_block_number += uint256(block.number);

        // An empty value means that the closer never received a transfer, or
        // he is intentionally not providing the latest transfer, in which case
        // the closing party is going to lose the tokens that were transferred
        // to him.
        partner_address = recoverAddressFromBalanceProof(
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            signature
        );

        // Signature must be from the channel partner
        require(msg.sender != partner_address);

        // If there are off-chain transfers, update the participant's state
        if (nonce > 0) {
            require(channel.participants[partner_address].initialized);

            // This is the key for the partner's balance data storage
            bytes32 key = getBalanceDataKey(channel_identifier, partner_address, msg.sender);
            updateBalanceProofData(key, nonce, balance_hash);
        }

        ChannelClosed(channel_identifier, msg.sender);
    }

    /// @notice Called on a closed channel, the function allows the non-closing participant to
    /// provide the last balance proof, which modifies the closing participant's state. Can be
    /// called multiple times by anyone.
    /// @param balance_hash Hash of (transferred_amount, locked_amount, locksroot).
    /// @param additional_hash Computed from the message. Used for message authentication.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @param nonce Strictly monotonic value used to order transfers.
    /// @param closing_signature Closing participant's signature of the balance proof data.
    /// @param non_closing_signature Non-closing participant signature of the balance proof data.
    function updateNonClosingBalanceProof(
        uint256 channel_identifier,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes closing_signature,
        bytes non_closing_signature
    )
        external
    {
        Channel storage channel = channels[channel_identifier];

        // Channel must be closed
        require(channel.state == 2);

        // Channel must be in the settlement window
        require(channel.settle_block_number >= block.number);

        // We need the signature from the non-closing participant to allow anyone
        // to make this transaction. E.g. a monitoring service.
        address non_closing_participant = recoverAddressFromBalanceProofUpdateMessage(
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            non_closing_signature
        );

        Participant storage non_closing_participant_state = channel.participants[
            non_closing_participant
        ];

        // Make sure the signature is from a channel participant
        require(non_closing_participant_state.initialized);

        address closing_participant = recoverAddressFromBalanceProof(
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature
        );

        // Make sure the signatures are from different accounts
        require(closing_participant != non_closing_participant);

        Participant storage closing_participant_state = channel.participants[closing_participant];

        // Make sure address is a channel participant
        require(closing_participant_state.initialized);

        // Make sure the first signature is from the closing participant
        require(closing_participant_state.is_the_closer);

        // This is the key for the closing participant's balance data storage
        bytes32 key = getBalanceDataKey(channel_identifier, closing_participant, non_closing_participant);
        updateBalanceProofData(key, nonce, balance_hash);

        NonClosingBalanceProofUpdated(channel_identifier, closing_participant);
    }

    /// @notice Registers the lock secret in the SecretRegistry contract.
    function registerSecret(bytes32 secret) public {
        require(secret_registry.registerSecret(secret));
    }

    /// @notice Settles the balance between the two parties.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @param participant1 Channel participant.
    /// @param participant1_transferred_amount The latest known amount of tokens transferred
    /// from `participant1` to `participant2`.
    /// @param participant1_locked_amount Amount of tokens owed by `participant1` to
    /// `participant2`, contained in locked transfers that will be retrieved by calling `unlock`
    /// after the channel is settled.
    /// @param participant1_locksroot The latest known merkle root of the pending hash-time locks
    /// of `participant1`, used to validate the unlocked proofs.
    /// @param participant2 Other channel participant.
    /// @param participant2_transferred_amount The latest known amount of tokens transferred
    /// from `participant2` to `participant1`.
    /// @param participant2_locked_amount Amount of tokens owed by `participant2` to
    /// `participant1`, contained in locked transfers that will be retrieved by calling `unlock`
    /// after the channel is settled.
    /// @param participant2_locksroot The latest known merkle root of the pending hash-time locks
    /// of `participant2`, used to validate the unlocked proofs.
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
        Channel storage channel = channels[channel_identifier];

        // Channel must be closed
        require(channel.state == 2);

        // Settlement window must be over
        require(channel.settle_block_number < block.number);

        Participant storage participant1_state = channel.participants[participant1];
        Participant storage participant2_state = channel.participants[participant2];

        // Addresses must be channel participants
        require(participant1_state.initialized);
        require(participant2_state.initialized);

        require(verifyBalanceProofData(
            channel_identifier,
            participant1,
            participant2,
            participant1_transferred_amount,
            participant1_locked_amount,
            participant1_locksroot
        ));

        require(verifyBalanceProofData(
            channel_identifier,
            participant2,
            participant1,
            participant2_transferred_amount,
            participant2_locked_amount,
            participant2_locksroot
        ));

        // `participant2_transferred_amount` is the amount of tokens that `participant1`
        // needs to receive. `participant1_transferred_amount` is the amount of tokens that
        // `participant2` needs to receive
        (
            participant2_transferred_amount,
            participant1_transferred_amount
        ) = getSettleTransferAmounts(
            uint256(participant1_state.deposit),
            uint256(participant1_transferred_amount),
            uint256(participant1_locked_amount),
            uint256(participant2_state.deposit),
            uint256(participant2_transferred_amount),
            uint256(participant2_locked_amount)
        );

        // Remove the channel data from storage
        delete channel.participants[participant1];
        delete channel.participants[participant2];
        delete channels[channel_identifier];

        // Store balance data needed for `unlock`
        updateBalanceUnlockData(
            channel_identifier,
            participant1,
            participant2,
            participant1_locked_amount,
            participant1_locksroot
        );
        updateBalanceUnlockData(
            channel_identifier,
            participant2,
            participant1,
            participant2_locked_amount,
            participant2_locksroot
        );

        // Do the actual token transfers
        if (participant2_transferred_amount > 0) {
            require(token.transfer(participant1, participant2_transferred_amount));
        }

        if (participant1_transferred_amount > 0) {
            require(token.transfer(participant2, participant1_transferred_amount));
        }

        ChannelSettled(channel_identifier);
    }

    function getSettleTransferAmounts(
        uint256 participant1_deposit,
        uint256 participant1_transferred_amount,
        uint256 participant1_locked_amount,
        uint256 participant2_deposit,
        uint256 participant2_transferred_amount,
        uint256 participant2_locked_amount
    )
        pure
        private
        returns (uint256, uint256)
    {
        uint256 participant1_amount;
        uint256 participant2_amount;
        uint256 total_deposit;

        // Direct token transfers done through the token `transfer` function
        // cannot be accounted for, these superfluous tokens will be burned,
        // this is because there is no way to tell which participant (if any)
        // had ownership over the token.

        total_deposit = participant1_deposit + participant2_deposit;

        participant1_amount = (
            participant1_deposit +
            participant2_transferred_amount -
            participant1_transferred_amount
        );

        // To account for cases when participant2 does not provide participant1's balance proof
        // Therefore, participant1's transferred_amount will be lower than in reality
        participant1_amount = min(participant1_amount, total_deposit);

        // To account for cases when participant1 does not provide participant2's balance proof
        // Therefore, participant2's transferred_amount will be lower than in reality
        participant1_amount = max(participant1_amount, 0);

        // At this point `participant1_amount` is between [0, total_deposit_available],
        // so this is safe.
        participant2_amount = total_deposit - participant1_amount;

        // Handle old balance proofs with a high locked_amount
        participant1_amount = max(participant1_amount - participant1_locked_amount, 0);
        participant2_amount = max(participant2_amount - participant2_locked_amount, 0);

        return (participant1_amount, participant2_amount);
    }

    /// @notice Unlocks all locked off-chain transfers and sends the locked tokens to the
    /// participant. Anyone can call unlock on behalf of a channel participant.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @param partner Address of the participant who owes the locked tokens.
    /// @param merkle_tree_leaves The entire merkle tree of pending transfers.
    function unlock(
        uint256 channel_identifier,
        address participant,
        address partner,
        bytes merkle_tree_leaves
    )
        public
    {
        // Channel must be settled and channel data deleted
        require(channels[channel_identifier].state == 0);

        bytes32 computed_locksroot;
        uint256 unlocked_amount;

        // This hashed key makes sure that both participant and partner are channel nodes
        BalanceData storage partner_balance_state = balance_data[
            getBalanceDataKey(channel_identifier, partner, participant)
        ];

        // The partner must have a non-empty locksroot,
        // meaning that there must be pending locks to unlock
        require(partner_balance_state.balance_hash_or_locksroot != 0);

        // There must be a locked amount of tokens in the smart contract, used for withdrawing
        // locked transfers with secrets revealed on chain
        require(partner_balance_state.nonce_or_locked_amount > 0);

        (computed_locksroot, unlocked_amount) = getMerkleRootAndUnlockedAmount(merkle_tree_leaves);

        // Make sure the computed merkle root is same as the one from the provided balance proof
        require(partner_balance_state.balance_hash_or_locksroot == computed_locksroot);

        // Make sure we don't transfer more tokens than previously reserved in the smart contract.
        unlocked_amount = min(unlocked_amount, partner_balance_state.nonce_or_locked_amount);

        // Transfer the rest of the tokens back to the partner
        uint256 returned_tokens = partner_balance_state.nonce_or_locked_amount - unlocked_amount;

        // Remove partner's data structure and clear storage
        delete balance_data[getBalanceDataKey(channel_identifier, partner, participant)];

        // Transfer the unlocked tokens to the participant
        require(token.transfer(participant, unlocked_amount));

        // Transfer the rest of the tokens back to the partner
        if (returned_tokens > 0) {
            require(token.transfer(partner, returned_tokens));
        }

        ChannelUnlocked(channel_identifier, participant, unlocked_amount, returned_tokens);
    }

    function cooperativeSettle(
        uint256 channel_identifier,
        uint256 participant1_balance,
        uint256 participant2_balance,
        bytes participant1_signature,
        bytes participant2_signature)
        public
    {
        address participant1;
        address participant2;
        uint256 total_deposit;
        Channel storage channel = channels[channel_identifier];

        participant1 = recoverAddressFromCooperativeSettleSignature(
            channel_identifier,
            participant1_balance,
            participant2_balance,
            participant1_signature
        );

        participant2 = recoverAddressFromCooperativeSettleSignature(
            channel_identifier,
            participant1_balance,
            participant2_balance,
            participant2_signature
        );

        Participant storage participant1_state = channel.participants[participant1];
        Participant storage participant2_state = channel.participants[participant2];

        total_deposit = participant1_state.deposit + participant2_state.deposit;

        // The channel must be open
        require(channel.state == 1);

        // The participant addresses must be part of the channel
        require(participant1_state.initialized);
        require(participant2_state.initialized);

        // The sum of the provided balances must be equal to the total deposit
        require(total_deposit == (participant1_balance + participant2_balance));

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

        ChannelSettled(channel_identifier);
    }

    /// @dev Returns the unique identifier for the channel participant balance data.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @param participant Address of the channel participant whose balance data
    /// is referenced by the key.
    /// @param partner Address of the channel partner.
    /// @return Unique identifier for the participant's balance data.
    function getBalanceDataKey(uint256 channel_identifier, address participant, address partner)
        pure
        internal
        returns (bytes32 data)
    {
        return keccak256(channel_identifier, participant, partner);
    }

    function updateBalanceProofData(bytes32 key, uint256 nonce, bytes32 balance_hash) internal {
        BalanceData storage balance_state = balance_data[key];

        // Multiple calls to updateNonClosingBalanceProof can be made and we need to store
        // the last known balance proof data
        require(nonce > balance_state.nonce_or_locked_amount);

        balance_state.nonce_or_locked_amount = nonce;
        balance_state.balance_hash_or_locksroot = balance_hash;
    }

    function updateBalanceUnlockData(
        uint256 channel_identifier,
        address participant,
        address partner,
        uint256 locked_amount,
        bytes32 locksroot
    )
        internal
    {
        bytes32 key = getBalanceDataKey(channel_identifier, participant, partner);

        // If there are transfers to unlock, store the locksroot and total amount of tokens
        // locked in pending transfers. Otherwise, clear storage.
        if (locked_amount > 0 && locksroot != 0) {
            BalanceData storage balance_state = balance_data[key];

            balance_state.nonce_or_locked_amount = locked_amount;
            balance_state.balance_hash_or_locksroot = locksroot;
        } else {
            delete balance_data[key];
        }
    }

    function verifyBalanceProofData(
        uint256 channel_identifier,
        address participant,
        address partner,
        uint256 transferred_amount,
        uint256 locked_amount,
        bytes32 locksroot
    )
        view
        internal
        returns (bool balance_data_is_correct)
    {
        BalanceData storage balance_state = balance_data[
            getBalanceDataKey(channel_identifier, participant, partner)
        ];

        // Make sure the hash of the provided state is the same as the stored balance_hash
        balance_data_is_correct = balance_state.balance_hash_or_locksroot == keccak256(
            transferred_amount,
            locked_amount,
            locksroot
        );
    }

    /// @dev Returns the channel specific data.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @return Channel state and settle_block_number.
    function getChannelInfo(uint256 channel_identifier)
        view
        external
        returns (uint256, uint8)
    {
        Channel storage channel = channels[channel_identifier];

        return (
            channel.settle_block_number,
            channel.state
        );
    }

    /// @dev Returns the channel specific data.
    /// @param channel_identifier The channel identifier - mapping key used for `channels`.
    /// @param participant Address of the channel participant whose data will be returned.
    /// @param partner Address of the participant's channel partner.
    /// @return Participant's channel deposit, verification that the participant is part of the
    /// channel, whether the participant has called `closeChannel` or not, balance_hash or
    /// locksroot, nonce or locked_amount.
    function getChannelParticipantInfo(
        uint256 channel_identifier,
        address participant,
        address partner
    )
        view
        external
        returns (uint256, bool, bool, bytes32, uint256)
    {
        Participant storage participant_state = channels[channel_identifier].participants[
            participant
        ];
        BalanceData storage participant_balance_state = balance_data[
            getBalanceDataKey(channel_identifier, participant, partner)
        ];

        return (
            participant_state.deposit,
            participant_state.initialized,
            participant_state.is_the_closer,
            participant_balance_state.balance_hash_or_locksroot,
            participant_balance_state.nonce_or_locked_amount
        );
    }

    /*
     * Internal Functions
     */

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
        bytes32 message_hash = keccak256(
            balance_hash,
            nonce,
            additional_hash,
            channel_identifier,
            address(this),
            chain_id
        );

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
        bytes32 message_hash = keccak256(
            balance_hash,
            nonce,
            additional_hash,
            channel_identifier,
            address(this),
            chain_id,
            closing_signature
        );

        signature_address = ECVerify.ecverify(message_hash, non_closing_signature);
    }

    function recoverAddressFromCooperativeSettleSignature(
        uint256 channel_identifier,
        uint256 participant1_balance,
        uint256 participant2_balance,
        bytes signature
    )
        view
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(
            participant1_balance,
            participant2_balance,
            channel_identifier,
            address(this),
            chain_id
        );

        signature_address = ECVerify.ecverify(message_hash, signature);
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
                    lockhash = keccak256(merkle_layer[i], merkle_layer[i + 1]);
                } else {
                    lockhash = keccak256(merkle_layer[i + 1], merkle_layer[i]);
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
        lockhash = keccak256(expiration_block, locked_amount, secrethash);

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
}
