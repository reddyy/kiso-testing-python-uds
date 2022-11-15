from typing import Dict, List

from uds.uds_config_tool import DecodeFunctions
from uds.uds_config_tool.odx.param import Param


class PosResponse():
    """encapsulates PARAMs and DID + SID information for parsing and decoding a positive uds response
    """

    def __init__(self, params: List[Param], didLength: int, DID: int, sidLength: int, SID: int) -> None:
        """initialize attributes

        :param params: List of Params that are defined in the POS-RESPONSE for a DID
        :param didLength: byte length of the PosResponse's DID
        :param DID: the DID value
        :param sidLength: byte length of the PosResponse's SID
        :SID: the SID value
        """
        self.params = params
        self.didLength = didLength
        self.DID = DID
        self.sidLength = sidLength
        self.SID = SID

    def decode(self) -> Dict[str, str]:
        """Decode the data stored in this PosResponses params

        :raises ValueError: if no data to decode in a param
        :return: dictionary with the params short name as key and the decoded data as value
        """
        result = {}
        for param in self.params:
            result[param.shortName] = param.decode()
        return result

    def parseDIDResponseLength(self, udsResponse: List[int]) -> int:
        """parses the response component that contains this PosResponses (DID) data of the front of the
        passed udsResponse

        stores the data parsed for each PARAM as that PARAM's data

        :param udsResponse: the (remaining) uds response
        :return: byte length of this DIDs part of the response
        """
        self.checkDIDInResponse(udsResponse)
        startPosition = self.didLength
        endPosition = self.didLength
        for param in self.params:
            toParse = udsResponse[startPosition:]
            paramLength = param.calculateLength(toParse)
            endPosition += paramLength
            data = udsResponse[startPosition: endPosition]
            # store data in param for decoding
            param.data = data
            startPosition = endPosition
        return endPosition  # this is the total length

    def checkDIDInResponse(self, didResponse: List[int]) -> None:
        """compare PosResponse's DID with the DID at beginning of a response

        :param didResponse: uds response to take the DID from
        :raises AttributeError: if DID does not match the expected DID
        """
        actualDID = DecodeFunctions.buildIntFromList(didResponse[:self.didLength])
        if self.DID != actualDID:
            raise AttributeError(f"The expected DID {self.DID} does not match the received DID {actualDID}")

    def checkSIDInResponse(self, response: List[int]) -> None:
        """compare PosResponse's SID with the SID at beginning of a response

        :param response: uds response to take the SID from
        :raises AttributeError: if SID does not match the expected SID
        """
        actualSID = DecodeFunctions.buildIntFromList(response[:self.sidLength])
        if self.SID != actualSID:
            raise AttributeError(f"The expected SID {self.SID} does not match the received SID {actualSID}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: param={self.params}, didLength={self.didLength}, DID={self.DID}"
