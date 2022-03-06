from source.logging_server import LoggingServer
import logging
import logging.handlers
import signal

if __name__ == '__main__':

    host = "localhost"
    port = logging.handlers.DEFAULT_TCP_LOGGING_PORT
    config = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': '%(levelname)10s %(asctime)s %(module)10s %(process)d %(thread)d %(message)s'
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
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
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
                'handlers': ['console']
            },
        }
    }
    server = LoggingServer(host, port, config=config)

    signal.signal(signal.SIGINT, lambda *argv: server.shutdown(force=True))

    try:
        server.start()

        while True:
            cmd = input("Stop server to input ['stop' / 'force'] > ")
            if cmd in ['stop', 'force']:
                break
        server.shutdown(force=(cmd=="force"))
        while server.is_alive():
            server.join(10)
    finally:
        server.join()
