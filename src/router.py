#!/bin/env python3

import logging

class Router:
    """Generic router class"""

    def __init__(self, routerconfig):
        self.name = list(routerconfig)[0]
        self.address = routerconfig[self.name]["address"]
        self.protocol = routerconfig[self.name]["transport"]["protocol"]
        self.username = routerconfig[self.name]["transport"]["username"]
        try:
            self.password = routerconfig["transport"]["password"]
        except KeyError:
            self.password = None
        else:
            self.password = routerconfig["transport"]["password"]
        try:
            self.use_keys = routerconfig["transport"]["use_keys"]
        except KeyError:
            self.use_keys = False
        else:
            self.use_keys = routerconfig["transport"]["use_keys"]
        self.supported_protocols = ["telnet", "ssh", "http"]

    def __str__(self):
        return "router " + self.name + " at " + self.address + " connecting using " + self.protocol

    def connection_test(self):
        """Throws exception if protocol is not supported, tests the connection otherwise """
        if self.protocol not in self.supported_protocols:
            raise Exception("Unsupported protocol")
        if self.protocol == "telnet":
            pass
        elif self.protocol == "ssh":
            pass
        elif self.protocol == "http":
            pass

class DdwrtRouter(Router):
    def __init__(self, routerconfig):
        Router.__init__(self, routerconfig)
        self.supported_protocols.remove("ssh")
        self.connection_test()

    def __str__(self):
        return "DD-WRT " + Router.__str__(self)
