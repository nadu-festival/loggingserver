#!/usr/bin/env python3
import logging
import pickle
import struct
import typing
from select import select
from socket import SHUT_RDWR, socket
from threading import Thread


class LoggingWorkerThread(Thread):
    """
    Thread to handling connection of logging.handlers.SocketHandler.

    Usage
    -----
    ```
    import socket
    import logging

    # Connect socket from logging.handlers.SocketHandler.
    host = "localhost"
    port = logging.handlers.DEFAULT_TCP_LOGGING_PORT
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind((host, port))
    serversocket.listen(0)
    (sock, address) = serversocket.accept()
    serversocket.close()

    # Create instance and start.
    handler_thread = LoggingWorkerThread(sock)
    handler_thread.start()

    # Force stop.
    handler_thread.force_shutdown()
    handler_thread.join()
    ```
    """

    def __init__(
                self,
                sock: socket,
                addr,
                timeout: float = 1,
                name: typing.Optional[str] = None,
                daemon: typing.Optional[bool] = None
            ) -> None:
        """
        Initialize LoggingWorkerThread.

        Parameters
        ----------
        sock : socket
        addr : address
        timeout : float, default 1 [sec]
        name, daemon
            Arguments of threading.Thread
        """
        super().__init__(name=name, daemon=daemon)
        self._socket: socket = sock
        self._addr = addr
        self._timeout: float = timeout
        self._force_shutdown: bool = False

    def force_shutdown(self) -> None:
        """Request to stop logging."""
        self._force_shutdown = True

    def run(self) -> None:
        """Logging procedure."""
        with self._socket:
            # Continue logging until force shutdown or socket closed.
            while not self._force_shutdown:
                # Read size of logrecord.
                logdata_size: bytes = self._recv_chunk(4)
                # If socket closed, break.
                if len(logdata_size) == 0:
                    break

                # Convert logrecord size from bytes to int.
                chunk_size: int = struct.unpack('>L', logdata_size)[0]
                # Read logrecord.
                pickled_log: bytes = self._recv_chunk(chunk_size)
                # If socket closed, break.
                if len(pickled_log) == 0:
                    break
                # Convert logrecord from
                record: logging.LogRecord = self._makeLogRecord(pickled_log)
                # Handle log record.
                self._handleLogRecord(record)
            # Shutdown socket.
            self._shutdown_socket()

    def _recv_chunk(self, chunk_size: int) -> bytes:
        """
        Receive chunked-data from socket.

        Parameters
        ----------
        chunk_size : int

        Returns
        -------
        bytes : received data.
            If length==0, socket was closed/broken.
        """
        chunk: bytes = b""
        while (not self._force_shutdown) and (len(chunk) < chunk_size):
            # Poll socket.
            if select([self._socket], [], [], self._timeout)[0]:
                recv_data: bytes = self._socket.recv(chunk_size - len(chunk))
                chunk = chunk + recv_data
                # If len(recv_data)==0, socket was closed/broken.
                if len(recv_data) == 0:
                    break
        if len(chunk) == chunk_size:
            return chunk
        return b""

    def _shutdown_socket(self) -> None:
        """Shutdown socket."""
        self._socket.shutdown(SHUT_RDWR)

    def _makeLogRecord(self, pickled_log: bytes) -> logging.LogRecord:
        """
        Make logging.LogRecord from pickled logrecord.

        Parameters
        ----------
        pickled_log : bytes

        Returns
        -------
        logging.LogRecord
        """
        return logging.makeLogRecord(self._unPickle(pickled_log))

    def _unPickle(self, data: bytes) -> typing.Any:
        """Un-pickle pickled data."""
        return pickle.loads(data)

    def _handleLogRecord(self, record: logging.LogRecord) -> None:
        """
        Handle logrecord.

        Parameters
        ----------
        record : logging.LogRecord
        """
        # if a name is specified, we use the named logger rather than the one
        # implied by the record.
        name: str = record.name
        logger: logging.Logger = logging.getLogger(name)
        # N.B. EVERY record gets logged. This is because Logger.handle
        # is normally called AFTER logger-level filtering. If you want
        # to do filtering, do it at the client end to save wasting
        # cycles and network bandwidth!
        logger.handle(record)

    @property
    def socket(self) -> socket:
        return self._socket
