import fabric
import invoke

from . import exceptions

class Router:
    """Generic router class"""

    def __init__(self, routerconfig):
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
            self.use_keys = routerconfig[self.name]["transport"]["use_keys"]
        self.supported_protocols = ["telnet", "ssh", "http"]
        self.ss_dict = {}
        self.wireless_interfaces = []

    def __del__(self):
        print("Called " + self.name + "'s destructor")
        if self.protocol == "ssh":
            if self.connection.is_connected:
                print("Closing SSH connection to " + self.name)
                self.connection.close()

    def __str__(self):
        return "router " + self.name + " at " + self.address + " with protocol " + self.protocol

    def update(self):
        self.ss_dict = {}

    def connect(self):
        """Connects to the router, throws exceptions if it fails somehow"""

        if self.protocol not in self.supported_protocols:
            raise exceptions.UnsupportedProtocol("Unsupported protocol")
        if self.protocol == "telnet":
            pass
        elif self.protocol == "ssh":
            self.connection = fabric.Connection(host=self.address, user=self.username, connect_kwargs={"password": self.password, "timeout": 30.0})
            # self.connection.transport.set_keepalive(5)
            result = self.connection.run("hostname", hide=True)
            if result.ok:
                print(self.name + ": Connection is OK, got hostname " + result.stdout.strip())
            else:
                raise Exception("Unable to connect using SSH")
        elif self.protocol == "http":
            pass


class DdwrtRouter(Router):
    """Inherits from the generic router class and adds DD-WRT-specific stuff"""

    def __init__(self, routerconfig):
        Router.__init__(self, routerconfig)
        self.supported_protocols.remove("telnet")
        self.supported_protocols.remove("http")
        self.connect()
        if self.protocol == "ssh":
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

    def update(self):
        self.ss_dict = {}
        self.wireless_interfaces = self.get_interfaces()
        for interface in self.wireless_interfaces:
            self.ss_dict.update({interface: self.get_ss_dict(interface)})

    def get_interfaces(self):
        """Returns a list of wireless interfaces
        only called internally from the DD-WRT update() method"""
        interfaces = self.connection.run("ls /sys/class/net", hide=True).stdout.strip().split()
        wireless_interfaces = []
        for interface in interfaces:
            if "wireless" in self.connection.run("ls /sys/class/net/" + interface, hide=True).stdout.strip():
                wireless_interfaces.append(interface)
        return wireless_interfaces

    def get_ss_dict(self, interface):
        """Overrides the generic dummy function for getting
        the signal strength dictionary"""
        clients = self.get_clients_list(interface)
        ss_dict = {}
        for client in clients:
            new_value = self.get_ss(client, interface)
            ss_dict.update(new_value)
        return ss_dict

    def parse_wl_output(self, output):
        """Only called internally from get_clients_list
        Takes the raw output of wl assoclist and returns a list of MAC addresses"""

        initial_list = output.stdout.strip().split()
        client_list = []
        if output.stdout.strip() != "":
            for entry in initial_list:
                if entry != "assoclist":
                    client_list.append(entry)
            return client_list
        else:
            return []

    def get_ss(self, mac, interface):
        """Only called internally from get_ss_dict
        Takes a MAC address string
        Returns a dict with a MAC and its RSSI value"""

        try:
            output = self.connection.run(self.wl_command + " -i " + interface + " rssi " + mac, hide=True)
            return {mac: output.stdout.strip().split()[-1]}
        except invoke.exceptions.UnexpectedExit:
            return {mac: None}

    def get_clients_list(self, interface):
        """Gets the list of connected clients from the router
        Uses parse_wl_output to turn the wl output to a list"""
        response = self.connection.run(self.wl_command + " -i " + interface + " assoclist", hide=True)
        return self.parse_wl_output(response)


class Dslac55uRouter(Router):

    def __init__(self, routerconfig):
        Router.__init__(self, routerconfig)
        self.supported_protocols.remove("telnet")
        self.supported_protocols.remove("http")
        self.wireless_interfaces = ["2g", "5g"]
        self.connect()

    def __str__(self):
        return "DSL-AC55U " + Router.__str__(self)

    def update(self):
        ate_output = self.connection.run("ATE show_stainfo", hide=True, warn=True).stdout
        self.ss_dict = {}
        for interface in self.wireless_interfaces:
            self.ss_dict.update({interface: self.ate_output_ss(ate_output, interface)})
        #self.ss_dict.update({"5g": self.ate_output_ss(ate_output, "5")})

    def ate_output_ss(self, ate_output, band):
        """Returns a dict with a MAC and its signal strength"""
        lines = ate_output.strip().splitlines()
        if "2.4 GHz radio is disabled" in lines and band == "2g":
            return {}
        elif "5 GHz radio is disabled" in lines and band == "5g":
            return {}
        else:
            #print(lines)
            #print("^^^^^^^^^^^^^^^^^^^^^^^ raw lines for " + band)
            start = 0
            end = 0
            for index, line in enumerate(lines):
                if line == "----------------------------------------":
                    if index == 6 and band == "2g":
                        start = index + 2
                    elif index > 6 and band == "5g":
                        start = index + 2
                elif line == "" and lines[index + 1] == "" and band == "2g":
                    end = index - 1
                    break
                elif index == len(lines) - 1 and band == "5g":
                    end = index
            devlines = []
            ss_dict = {}
            for index, line in enumerate(lines):
                if index >= start and index <= end:
                    devlines.append(line)
            if len(devlines) != 0:
                for line in devlines:
                    try:
                        ss_dict.update({line.split()[0]: line.split()[1].replace("dBm", "")})
                    except IndexError:
                        print(devlines)
            return ss_dict
