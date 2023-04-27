import fabric  # type: ignore
import invoke  # type: ignore
# import paramiko  # type: ignore
import json

from . import exceptions

features = {
            "int_detect": "Wireless interface detection",
            "signal": "Client signal strength",
            "channel": "Current interface channel",
            "rxtx": "Bytes sent/received",
            "proc": "Various stats from /proc",
            "int_temp": "Interface temperature",
            "dmu_temp": "CPU temperature"}


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
        self.connect()
        # I have a feeling that there should be a condition here
        self.wireless_interfaces = self.get_interfaces()
        if "proc" in self.supported_features:
            meminfo_output = self.connection.run("cat /proc/meminfo",
                                                 hide=True)\
                                                 .stdout.strip().split()
            self.memtotal_index = meminfo_output.index("MemTotal:")
            if "MemAvailable:" in meminfo_output:
                self.memavailable_index = meminfo_output.index("MemAvailable:")
            else:
                self.rprint(
                    "proc: /proc/meminfo does not report MemAvailable," +
                    " memory stats may not be accurate.")
                self.proc_taint = None
                self.memfree_index = meminfo_output.index("MemFree:")
                self.buffers_index = meminfo_output.index("Buffers:")
                self.cache_index = meminfo_output.index("Cached:")

    def __del__(self):
        self.rprint("Destructor got called")
        if self.connection.is_connected:
            self.rprint("Closing connection...")
            self.connection.close()

    def __str__(self):
        return "router " + self.name + " at " + self.address

    def rprint(self, printstring):
        print(self.name + ": " + printstring)

    def list_features(self):
        alignment_length = len("int_detect") + 1
        self.rprint("int_detect: Wireless interfaces: " +
                    str(self.wireless_interfaces))
        self.rprint("-------------------------------")
        for feature in features:
            feature_aligned = feature
            while len(feature_aligned) != alignment_length:
                feature_aligned += " "
            if feature in self.supported_features:
                if hasattr(self, feature + "_taint"):
                    self.rprint("[\033[93m   PART   \033[00m]  "
                                + feature_aligned
                                + "-   "
                                + features[feature]
                                + "   - see the above messages for details")
                else:
                    self.rprint("[\033[92m   FULL   \033[00m]  "
                                + feature_aligned
                                + "-   "
                                + features[feature])
            elif feature in self.implemented_features:
                self.rprint("[\033[91m DISABLED \033[00m]  "
                            + feature_aligned
                            + "-   "
                            + features[feature])
            else:
                self.rprint("[\033[94m NOT IMPL \033[00m]  "
                            + feature_aligned
                            + "-   "
                            + features[feature])
        self.rprint("-------------------------------")

    def update(self):
        if "signal" in self.supported_features:
            self.ss_dicts = []
        if "channel" in self.supported_features:
            self.channels = []
        if "rxtx" in self.supported_features:
            self.interface_rx = []
            self.interface_tx = []
        if "proc" in self.supported_features:
            self.loads = self.get_system_load()
            self.mem_used = self.get_memory_usage()
        if "int_temp" in self.supported_features:
            self.int_temperatures = []
        if "dmu_temp" in self.supported_features:
            self.dmu_temp = self.get_dmu_temp()
        for interface in self.wireless_interfaces:
            if "int_temp" in self.supported_features:
                self.int_temperatures.append(self.get_int_temp(interface))
            if "signal" in self.supported_features:
                self.ss_dicts.append(self.get_ss_dict(interface))
            if "channel" in self.supported_features:
                self.channels.append(self.get_channel(interface))
            if "rxtx" in self.supported_features:
                self.interface_rx.append(self.get_interface_rxtx(interface,
                                                                 "rx"))
                self.interface_tx.append(self.get_interface_rxtx(interface,
                                                                 "tx"))

    def get_interface_rxtx(self, interface, selector):
        """Takes an interface and selector (either rx or tx)
        Returns the number of bytes received/transmitted (taken from sysfs)"""
        return self.connection.run("cat /sys/class/net/"
                                   + interface
                                   + "/statistics/"
                                   + selector
                                   + "_bytes", hide=True).stdout.strip()

    def get_system_load(self):
        """Returns the contents of /proc/loadavg"""
        return self.connection.run("cat /proc/loadavg",
                                   hide=True).stdout.strip().split()

    def get_memory_usage(self):
        """Returns memory usage in %"""
        meminfo_output = self.connection.run("cat /proc/meminfo",
                                             hide=True).stdout.strip().split()
        mem_total = int(meminfo_output[self.memtotal_index + 1])
        if hasattr(self, "memavailable_index"):
            mem_avail = int(meminfo_output[self.memavailable_index + 1])
        else:
            mem_avail = int(meminfo_output[self.memfree_index + 1]) + \
                        int(meminfo_output[self.buffers_index + 1]) + \
                        int(meminfo_output[self.cache_index + 1])
        return 100 - (mem_avail / mem_total) * 100

    def get_interfaces(self):
        """Returns a list of wireless interfaces"""
        interfaces = self.connection.run("ls /sys/class/net",
                                         hide=True).stdout.strip().split()
        wireless_interfaces = []
        for interface in interfaces:
            if "wireless" in self.connection.run("ls /sys/class/net/"
                                                 + interface,
                                                 hide=True).stdout.strip():
                wireless_interfaces.append(interface)
        return wireless_interfaces

    def connect(self):
        """Connects to the router, throws exceptions if it fails somehow"""
        if self.connection is None:
            self.connection = fabric.Connection(host=self.address,
                                                user=self.username,
                                                connect_kwargs={
                                                    "password": self.password,
                                                    "timeout": 30.0})
            # self.connection.transport.set_keepalive(5)
        else:
            self.rprint("Closing and opening connection...")
            self.connection.close()
            self.connection.open()
        result = self.connection.run("echo", hide=True)
        if result.ok:
            self.rprint("Connection is OK!")
        else:
            raise Exception("Unable to connect using SSH")


class DdwrtRouter(Router):
    """Inherits from the generic router class and adds DD-WRT-specific stuff"""

    def __init__(self, routerconfig):
        self.implemented_features = list(features.keys())
        self.supported_features = self.implemented_features.copy()
        Router.__init__(self, routerconfig)
        wl_test = self.connection.run("which wl", hide=True, warn=True)
        wla_test = self.connection.run("which wl_atheros",
                                       hide=True, warn=True)
        if wla_test.exited == 0:
            self.rprint("Detected as an Atheros router, using 'wl_atheros'")
            self.wl_command = "wl_atheros"
        elif wl_test.exited == 0:
            self.rprint("Detected as a Broadcom router, using 'wl'")
            self.wl_command = "wl"
        else:
            self.rprint("Could not determine wl command!")
            raise exceptions.MissingCommand
        if self.wl_command != "wl":
            self.supported_features.remove("int_temp")
        if self.connection.run("test -f /proc/dmu/temperature",
                               warn=True).exited != 0:
            self.supported_features.remove("dmu_temp")
        self.list_features()

    def __str__(self):
        return "DD-WRT " + Router.__str__(self)

    def get_channel(self, interface):
        """Returns the interface's current channel"""
        if self.wl_command == "wl":
            radio_on = self.connection.run(self.wl_command +
                                           " -i " + interface + " radio",
                                           hide=True).stdout.strip()
            if radio_on == "0x0001":
                return None
            lines = self.connection.run(self.wl_command +
                                        " -i " + interface + " channel",
                                        hide=True).stdout.strip().splitlines()
            for line in lines:
                if "current" in line:
                    return line.split()[-1]
        elif self.wl_command == "wl_atheros":
            out = self.connection.run("iw " + interface + " info",
                                      hide=True, warn=True)
            if out.exited == 0:
                lines = out.stdout.strip().splitlines()
                    for line in lines:
                        if "channel" in line:
                            return line.split()[1]
            return None

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
        Takes the raw output of wl assoclist and
        returns a list of MAC addresses"""

        initial_list = output.stdout.strip().split()
        client_list = []
        if output.stdout.strip() != "":
            for entry in initial_list:
                if entry != "assoclist":
                    client_list.append(entry)
            return client_list
        else:
            return []

    def get_int_temp(self, interface):
        """Returns the interface's temperature"""
        out = self.connection.run(self.wl_command
                                  + " -i " + interface
                                  + " phy_tempsense",
                                  hide=True, warn=True)
        if out.exited == 0:
            return out.stdout.strip().split()[0]
        else:
            return None

    def get_dmu_temp(self):
        """Returns the CPU temperature (only available on Broadcom devices)"""
        out = self.connection.run("cat /proc/dmu/temperature",
                                  hide=True).stdout.strip()
        if out.isdigit():
            out = str(int(out) / 10)
        return out

    def get_ss(self, mac, interface):
        """Only called internally from get_ss_dict
        Takes a MAC address string
        Returns a dict with a MAC and its RSSI value"""

        output = self.connection.run(self.wl_command +
                                     " -i " + interface + " rssi " + mac,
                                     hide=True, warn=True)
        if output.exited == 0:
            return {mac: output.stdout.strip().split()[-1]}
        else:
            return {mac: None}

    def get_clients_list(self, interface):
        """Gets the list of connected clients from the router
        Uses parse_wl_output to turn the wl output to a list"""
        response = self.connection.run(self.wl_command +
                                       " -i " + interface + " assoclist",
                                       hide=True, warn=True)
        if output.exited == 0:
            return self.parse_wl_output(response)
        else:
            return []


class UbntRouter(Router):
    """Inherits from the generic router class and
    adds Ubiquiti-specific stuff"""

    def __init__(self, routerconfig):
        self.implemented_features = ["signal", "channel", "rxtx", "proc",
                                     "int_detect"]
        self.supported_features = self.implemented_features.copy()
        Router.__init__(self, routerconfig)
        if "wifi0" in self.wireless_interfaces:
            self.rprint("int_detect: Workaround - wifi0 is a dummy" +
                        " interface, removing it from the list")
            self.wireless_interfaces.remove("wifi0")
            self.int_detect_taint = None
        self.list_features()

    def __str__(self):
        return "Ubiquiti " + Router.__str__(self)

    def get_channel(self, interface):
        """Returns the interface's current channel"""
        output = self.connection.run("iwgetid -c " + interface,
                                     hide=True).stdout.strip().splitlines()
        return output[0].split(":")[1]

    def get_ss_dict(self, interface):
        """Overrides the generic dummy function for getting
        the signal strength dictionary"""
        wstalist = json.loads(self.connection.run("wstalist",
                              hide=True).stdout)
        ss_dict = {}
        for sta in wstalist:
            ss_dict.update({sta.get("mac"): sta.get("signal")})
        return ss_dict


class Dslac55uRouter(Router):

    def __init__(self, routerconfig):
        self.implemented_features = ["signal", "channel", "rxtx", "proc",
                                     "int_detect"]
        self.supported_features = self.implemented_features.copy()
        Router.__init__(self, routerconfig)
        self.list_features()

    def __str__(self):
        return "DSL-AC55U " + Router.__str__(self)

    def get_interfaces(self):
        """Manual override for wireless interfaces of the DSL-AC55U"""
        self.rprint("int_detect: Workaround - Manually specified" +
                    " wireless interfaces")
        self.supported_features.remove("int_detect")
        return ["ra0", "rai0"]

    def get_ss_dict(self, interface):
        self.ate_output = self.connection.run("ATE show_stainfo",
                                              hide=True, warn=True).stdout
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
                    if len(line.split()) >= 1:
                        ss_dict.update({
                            line.split()[0]: line.split()[1].replace("dBm", "")
                            })
                    else:
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
