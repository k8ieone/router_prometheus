import fabric  # type: ignore
import invoke  # type: ignore
import paramiko  # type: ignore

from . import exceptions


class Router:
    """Generic router class"""

    def __init__(self, routerconfig):
        self.name = list(routerconfig)[0]
        self.address = routerconfig[self.name]["address"]
        self.username = routerconfig[self.name]["transport"]["username"]
        self.connection = None
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
        self.supported_features = ["signal", "channel", "rxtx"]

    def __del__(self):
        print("Called " + self.name + "'s destructor")
        if self.connection.is_connected:
            print("Closing SSH connection to " + self.name)
            self.connection.close()

    def __str__(self):
        return "router " + self.name + " at " + self.address

    def update(self):
        if "signal" in self.supported_features:
            self.ss_dicts = []
        if "channel" in self.supported_features:
            self.channels = []
        if "rxtx" in self.supported_features:
            self.interface_rx = []
            self.interface_tx = []
        for interface in self.wireless_interfaces:
            if "signal" in self.supported_features:
                self.ss_dicts.append(self.get_ss_dict(interface))
            if "channel" in self.supported_features:
                self.channels.append(self.get_channel(interface))
            if "rxtx" in self.supported_features:
                self.interface_rx.append(self.get_interface_rxtx(interface, "rx"))
                self.interface_tx.append(self.get_interface_rxtx(interface, "tx"))

    def get_interface_rxtx(self, interface, selector):
        """Takes an interface and selector (either rx or tx)
        Returns the number of bytes received/transmitted (taken from sysfs)"""
        return self.connection.run("cat /sys/class/net/" + interface + "/statistics/" + selector + "_bytes", hide=True).stdout.strip()

    def connect(self):
        """Connects to the router, throws exceptions if it fails somehow"""
        print("Connecting to " + str(self))
        if self.connection is None:
            print(self.name + ": This is a new connection")
            self.connection = fabric.Connection(host=self.address, user=self.username, connect_kwargs={"password": self.password, "timeout": 30.0})
            # self.connection.transport.set_keepalive(5)
        else:
            print(self.name + ": Closing and opening connection...")
            self.connection.close()
            self.connection.open()
        result = self.connection.run("hostname", hide=True)
        if result.ok:
            print(self.name + ": Connection is OK, got hostname " + result.stdout.strip())
        else:
            raise Exception("Unable to connect using SSH")


class DdwrtRouter(Router):
    """Inherits from the generic router class and adds DD-WRT-specific stuff"""

    def __init__(self, routerconfig):
        Router.__init__(self, routerconfig)
        self.connect()
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
        self.wireless_interfaces = self.get_interfaces()

    def __str__(self):
        return "DD-WRT " + Router.__str__(self)

    def get_channel(self, interface):
        """Returns the interface's current channel"""
        if self.wl_command == "wl":
            radio_on = self.connection.run(self.wl_command + " -i " + interface + " radio", hide=True).stdout.strip()
            if radio_on == "0x0001":
                return None
            lines = self.connection.run(self.wl_command + " -i " + interface + " channel", hide=True).stdout.strip().splitlines()
            for line in lines:
                if "current" in line:
                    return line.split()[-1]
        elif self.wl_command == "wl_atheros":
            lines = self.connection.run("iw " + interface + " info", hide=True).stdout.strip().splitlines()
            for line in lines:
                if "channel" in line:
                    return line.split()[1]
            return None

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
        self.wireless_interfaces = ["ra0", "rai0"]
        self.connect()

    def __str__(self):
        return "DSL-AC55U " + Router.__str__(self)

    def get_ss_dict(self, interface):
        self.ate_output = self.connection.run("ATE show_stainfo", hide=True, warn=True).stdout
        return self.ate_output_ss(self.ate_output, interface)

    def get_channel(self, interface):
        return self.ate_output_channel(self.ate_output, interface)

    def ate_output_ss(self, ate_output, interface):
        if interface == "ra0":
            band = "2g"
        elif interface == "rai0":
            band = "5g"
        """Returns a dict with a MAC and its signal strength"""
        lines = ate_output.strip().splitlines()
        if "2.4 GHz radio is disabled" in lines and band == "2g":
            return {}
        elif "5 GHz radio is disabled" in lines and band == "5g":
            return {}
        else:
            # print(lines)
            # print("^^^^^^^^^^^^^^^^^^^^^^^ raw lines for " + band)
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

    def ate_output_channel(self, ate_output, interface):
        if interface == "ra0":
            band = "2g"
        elif interface == "rai0":
            band = "5g"
        """Returns a string containing the current channel"""
        lines = ate_output.strip().splitlines()
        if "2.4 GHz radio is disabled" in lines and band == "2g":
            return None
        elif "5 GHz radio is disabled" in lines and band == "5g":
            return None
        channel_lines = []
        for line in lines:
            if "Channel" in line:
                channel_lines.append(line)
        if band == "2g":
            return channel_lines[0].split()[-1]
        elif band == "5g":
            return channel_lines[-1].split()[-1]
