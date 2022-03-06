#!/usr/bin/env python3
"""

Usage
-----
host = "localhost"
port = logging.handlers.DEFAULT_TCP_LOGGING_PORT
config = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'filters': {},
    'handlers': {
        'null': {
            'level':'DEBUG',
            'class':'logging.NullHandler',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'verbose',
            'filename': 'log.log',
            'when': 'midnight',
        },
    },
    'loggers': {
        'root': {
            'level': 'DEBUG',
            'handlers': ['console', 'file']
        },
    }
}
server = LoggingServer(host, port, config=config)

try:
    server.start()

    while True:
        if input("Stop server to input ['stop'] > ") == 'stop':
            break
finally:
    server.shutdown()
    server.join()
"""

import logging
import logging.config
import multiprocessing
from multiprocessing import Event, Process
from multiprocessing.synchronize import Event as EventType
from select import select
from socket import AF_INET, SOCK_STREAM, socket
from typing import Any, Dict, List, Optional

from logging_worker_thread import LoggingWorkerThread


class LoggingServer(Process):
    """
    Logging server process.

    Usage
    -----
    ```
    import logging.handlers

    # Initialize process.
    host = "localhost"
    port = logging.handlers.DEFAULT_TCP_LOGGING_PORT
    logging_server = LoggingServer(host, port)

    # Start process.
    logging_server.start()

    # Shutdow.
    logging_server.shutdown()

    # Logging server work until all connection closed.
    while logging_server.is_alive():
        logging_server.join(timeout=10)

    # Force shutdown.
    logging_server.shutdown(force=True)
    logging_server.join()
    ```
    """

    def __init__(
                self,
                host: str,
                port: int,
                config: Dict[str, Any],
                *,
                timeout: float = 1,
                name: Optional[str] = None,
                daemon: Optional[bool] = None
            ) -> None:
        """
        Initialize LoggingServer.

        Parameters
        ----------
        host : str
        port : int
        config : Dict[str, Any]
            Argument of logging.config.dictConfig.
        timeout : float, default 1 [sec]
        name, daemon
            Arguments of multiprocessing.Process
        """
        super().__init__(name=name, daemon=daemon)
        self._host: str = host
        self._port: int = port
        self._config: Dict[str, Any] = config
        self._timeout: float = timeout
        self._shutdown_event: EventType = Event()
        self._force_shutdown_event: EventType = Event()

    def run(self) -> None:
        """Start logging procedure."""
        # Set logging configure to this process.
        logging.config.dictConfig(self._config)
        # Initialize server socket.
        serversocket: socket = socket(AF_INET, SOCK_STREAM)
        # List of LoggingWorkerThread.
        workers: List[LoggingWorkerThread] = []
        with serversocket:
            # Bind and listen.
            serversocket.bind((self._host, self._port))
            serversocket.listen(0)
            # Continue until shutdown request.
            while not self._shutdown_event.is_set():
                # Poll server socket.
                if select([serversocket], [], [], self._timeout)[0]:
                    # Accept connection.
                    (sock, addr) = serversocket.accept()
                    wk = LoggingWorkerThread(sock, addr, timeout=self._timeout)
                    wk.start()
                    workers.append(wk)
                # Join workers.
                for wk in workers:
                    wk.join(0)
                # Collect alive thread.
                workers = [wk for wk in workers if wk.is_alive()]
            # Shutdown
            while workers:
                if self._force_shutdown_event.wait(self._timeout):
                    for wk in workers:
                        wk.force_shutdown()
                    break
                for wk in workers:
                    wk.join(0)
                # Collect alive thread.
                workers = [wk for wk in workers if wk.is_alive()]
            for wk in workers:
                wk.join()

    def shutdown(self, force: bool = False) -> None:
        """
        Request stop logging server.

        Parameters
        ----------
        force : bool, default False
            If force=False, continue logging until connected socket is closed.
        """
        self._shutdown_event.set()
        if force:
            self._force_shutdown_event.set()
