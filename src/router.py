#!/bin/env python3

import fabric
import invoke

import exceptions

class Router:
    """Generic router class"""

    def __init__(self, routerconfig, mapping):
        self.name = list(routerconfig)[0]
        self.address = routerconfig[self.name]["address"]
        self.protocol = routerconfig[self.name]["transport"]["protocol"]
        self.username = routerconfig[self.name]["transport"]["username"]
        try:
            self.password = routerconfig[self.name]["transport"]["password"]
        except KeyError:
            self.password = None
        else:
            self.password = routerconfig[self.name]["transport"]["password"]
        try:
            self.use_keys = routerconfig[self.name]["transport"]["use_keys"]
        except KeyError:
            self.use_keys = False
        else:
            self.use_keys = routerconfig["transport"]["use_keys"]
        self.supported_protocols = ["telnet", "ssh", "http"]
        self.mapping = mapping
        self.clients_list = []
        self.rssi_dict = {}

    def __str__(self):
        return "router " + self.name + " at " + self.address + " connecting using " + self.protocol

    def get_clients_list_ssh(self):

        return ["dummy"]

    def get_rssi_ssh(self, mac):
        """Dummy RSSI function"""

        return {mac: "dummy"}

    def get_rssi_telnet(self, mac):

        return {mac: "dummy"}

    def get_rssi_http(self, mac):

        return {mac: "dummy"}

    def update(self):
        if self.protocol == "ssh":
            if self.connection.is_connected:
                pass
            else:
                self.establish_connection()
            self.clients_list_method = self.get_clients_list_ssh
            self.rssi_method = self.get_rssi_ssh
        elif self.protocol == "telnet":
            self.clients_list_method = self.get_clients_list_telnet
            self.rssi_method = self.get_rssi_telnet
        elif self.protocol == "http":
            self.clients_list_method = self.get_clients_list_http
            self.rssi_method = self.get_rssi_http
        self.clients_list = self.clients_list_method()
        if self.clients_list is None:
            self.clients_list = []
        self.rssi_dict = self.get_rssi_dict()

    def get_rssi_dict(self):
        """Takes a list of clients and queries the router
        for their RSSI values, returns a dict"""

        rssi_dict = {}
        if self.clients_list is not None:
            for client in self.clients_list:
                new_value = self.rssi_method(client)
                rssi_dict.update(new_value)
            return rssi_dict
        else:
            return self.clients_list

    def translate_macs(self):
        """Takes the mapping dict and RSSI dict and replaces
        known MAC addresses with nicknames from mapping
        returns another dict"""

        translated_dict = {}
        if self.rssi_dict is not None:
            for mac in self.rssi_dict.keys():
                if mac in self.mapping:
                    translated_dict.update({self.mapping[mac]: self.rssi_dict[mac]})
                else:
                    translated_dict.update({mac: self.rssi_dict[mac]})
            return translated_dict

    def establish_connection(self):
        """Throws exception if protocol is not supported, tests the connection otherwise"""

        if self.protocol not in self.supported_protocols:
            raise exceptions.UnsupportedProtocol("Unsupported protocol")
        if self.protocol == "telnet":
            pass
        elif self.protocol == "ssh":
            self.connection = fabric.Connection(host=self.address, user=self.username, connect_kwargs={"password": self.password})
            result = self.connection.run("hostname", hide=True)
            if result.ok:
                print(self.name + ": Connection is OK, got hostname " + result.stdout.strip())
            else:
                raise Exception("Unable to connect using SSH")
        elif self.protocol == "http":
            pass

    def cleanup(self):
        if self.protocol == "ssh":
            if self.connection.is_connected:
                self.connection.close()

class DdwrtRouter(Router):
    """Inherits from the generic router class and adds DD-WRT-specific stuff"""

    def __init__(self, routerconfig, mapping):
        Router.__init__(self, routerconfig, mapping)
        self.supported_protocols.remove("telnet")
        self.supported_protocols.remove("http")
        self.establish_connection()
        try:
            self.connection.run("wl", hide=True)
        except invoke.exceptions.UnexpectedExit:
            self.wl_command = "wl_atheros"
        else:
            self.wl_command = "wl"
        try:
            self.connection.run(self.wl_command, hide=True)
        except invoke.exceptions.UnexpectedExit:
            print("Both commands failed")
            raise exceptions.MissingCommand

    def __str__(self):
        return "DD-WRT " + Router.__str__(self)

    def parse_wl_output(self, output):
        """Takes the raw output of wl assoclist and returns a list of MAC addresses"""

        initial_list = output.stdout.strip().split()
        client_list = []
        if output.stdout.strip() != "":
            for entry in initial_list:
                if entry != "assoclist":
                    client_list.append(entry)
            return client_list
        return None

    def get_rssi_ssh(self, mac):
        """Takes a MAC address string
        Returns a dict with a MAC and its RSSI value"""

        return {mac: self.connection.run(self.wl_command + " rssi " + mac, hide=True).stdout.strip().split()[-1]}

    def get_clients_list_ssh(self):
        """Returns list of connected wireless clients"""

        response = self.connection.run(self.wl_command + " assoclist", hide=True)
        return self.parse_wl_output(response)
