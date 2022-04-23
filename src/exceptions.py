#!Pbin/env python3

class ConnectionFailed(Exception):
    pass

class UnsupportedProtocol(Exception):
    pass

class MissingCommand(Exception):
    pass
