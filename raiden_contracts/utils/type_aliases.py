from typing import NewType

T_AdditionalHash = bytes
AdditionalHash = NewType("AdditionalHash", T_AdditionalHash)

T_BalanceHash = bytes
BalanceHash = NewType("BalanceHash", T_BalanceHash)

# An absolute number of blocks
T_BlockExpiration = int
BlockExpiration = NewType("BlockExpiration", T_BlockExpiration)

T_ChainID = int
ChainID = NewType("ChainID", T_ChainID)

T_ChannelID = int
ChannelID = NewType("ChannelID", T_ChannelID)

T_Locksroot = bytes
Locksroot = NewType("Locksroot", T_Locksroot)

T_PrivateKey = bytes
PrivateKey = NewType("PrivateKey", T_PrivateKey)

T_Signature = bytes
Signature = NewType("Signature", T_Signature)

T_TokenAmount = int
TokenAmount = NewType("TokenAmount", T_TokenAmount)
