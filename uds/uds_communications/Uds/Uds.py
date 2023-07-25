#!/usr/bin/env python

__author__ = "Richard Clubb"
__copyrights__ = "Copyright 2018, the python-uds project"
__credits__ = ["Richard Clubb"]

__license__ = "MIT"
__maintainer__ = "Richard Clubb"
__email__ = "richard.clubb@embeduk.com"
__status__ = "Development"

import time
import threading
from pathlib import Path
from typing import Callable
import logging

from uds.config import Config
from uds.factories import TpFactory
from uds.uds_config_tool.IHexFunctions import ihexFile as ihexFileParser
from uds.uds_config_tool.ISOStandard.ISOStandard import IsoDataFormatIdentifier
from uds.uds_config_tool.UdsConfigTool import UdsTool


##
# @brief a description is needed
class Uds(object):

    ##
    # @brief a constructor
    # @param [in] reqId The request ID used by the UDS connection, defaults to None if not used
    # @param [in] resId The response Id used by the UDS connection, defaults to None if not used
    def __init__(self, odx=None, ihexFile=None, **kwargs):

        self.__transportProtocol = Config.uds.transport_protocol
        self.__P2_CAN_Client = Config.uds.p2_can_client
        self.__P2_CAN_Server = Config.uds.p2_can_server

        self.tp = TpFactory.select_transport_protocol(
            self.__transportProtocol, **kwargs
        )

        # used as a semaphore for the tester present
        self.__transmissionActive_flag = False

        # The above flag should prevent testerPresent operation, but in case of race conditions, this lock prevents actual overlapo in the sending
        self.sendLock = threading.Lock()

        # Process any ihex file that has been associated with the ecu at initialisation
        self.__ihexFile = ihexFileParser(ihexFile) if ihexFile is not None else None
        self.load_odx(odx)

    def load_odx(self, odx_file: Path) -> None:
        """Load the given odx file and create the associated UDS
        diagnostic services:

        :param odx_file: idx file full path
        """
        if odx_file is None:
            return
        UdsTool.create_service_containers(odx_file)
        UdsTool.bind_containers(self)

    def overwrite_transmit_method(self, func: Callable):
        """override transmit method from the asscociated __connection

        :param func: callable use to replace the current configured
            transmit method
        """
        self.tp.connection.transmit = func

    def overwrite_receive_method(self, func: Callable):
        """override the TP reception method

        :param func: callable use to replace the current
            getNextBufferedMessage method
        """
        self.tp.getNextBufferedMessage = func

    @property
    def ihexFile(self):
        return self.__ihexFile

    @ihexFile.setter
    def ihexFile(self, value):
        if value is not None:
            self.__ihexFile = ihexFileParser(value)

    ##
    # @brief Currently only called from transferFile to transfer ihex files
    def transferIHexFile(self, transmitChunkSize=None, compressionMethod=None):
        if transmitChunkSize is not None:
            self.__ihexFile.transmitChunksize = transmitChunkSize
        if compressionMethod is None:
            compressionMethod = IsoDataFormatIdentifier.noCompressionMethod
        self.requestDownload(
            [compressionMethod],
            self.__ihexFile.transmitAddress,
            self.__ihexFile.transmitLength,
        )
        self.transferData(transferBlocks=self.__ihexFile)
        return self.transferExit()

    ##
    # @brief This will eventually support more than one file type, but for now is limited to ihex only
    def transferFile(
        self, fileName=None, transmitChunkSize=None, compressionMethod=None
    ):
        if fileName is None and self.__ihexFile is None:
            raise FileNotFoundError("file to transfer has not been specified")

        # Currently only ihex is recognised and supported
        if fileName[-4:] == ".hex" or fileName[-5:] == ".ihex":
            self.__ihexFile = ihexFileParser(fileName)
            return self.transferIHexFile(transmitChunkSize, compressionMethod)
        else:
            raise FileNotFoundError(
                "file to transfer has not been recognised as a supported type ['.hex','.ihex']"
            )

    ##
    # @brief
    def send(self, msg, responseRequired=True, functionalReq=False, tpWaitTime=0.01):
        # sets a current transmission in progress - tester present (if running) will not send if this flag is set to true
        self.__transmissionActive_flag = True

        # We're moving to threaded operation, so putting a lock around the send operation.
        with self.sendLock:
            self.tp.send(msg, functionalReq, tpWaitTime)

        if functionalReq is True:
            responseRequired = False

        # Note: in automated mode (unlikely to be used any other way), there is no response from tester present, so threading is not an issue here.
        response = None

        #used for counting number of messages
        count = 0
        #timer used of receiving 0x78 messages ()
        elapsed = 0 ##TODO not defined a constant value
        # total time to receive response pending messages
        total_time = 0
        #modified code to get the response pending messages and checks interval does not exceed 3.5sec 
        while responseRequired and elapsed < 20:
            response = self.tp.recv(self.__P2_CAN_Client)
            if ((response[0] == 0x7F) and (response[2] == 0x78)):
                total_time =  time.perf_counter() - t1
                count = count + 1
                logging.info(f"UDS response pending message received {['0x{:02X}'.format(i) for i in response]}")
                if total_time/count > 3.5:
                    logging.exception("response pending took more than 3.5 sec") 
            else:
                return response
            elapsed = time.perf_counter() - t1

        # If the diagnostic session control service is supported, record the sending time for possible use by the tester present functionality (again, if present) ...
        if hasattr(self, "sessionSetLastSend"):
            self.sessionSetLastSend()

        # Lets go of the hold on transmissions - allows test present to resume operation (if it's running)
        self.__transmissionActive_flag = False
        return response

    ##
    # @brief
    def isTransmitting(self):
        return self.__transmissionActive_flag
