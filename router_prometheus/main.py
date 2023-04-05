import os
import sys
import logging
import signal
import socket

import yaml  # type: ignore
import paramiko  # type: ignore
from prometheus_client import start_http_server  # type: ignore
from prometheus_client import PLATFORM_COLLECTOR  # type: ignore
from prometheus_client import PROCESS_COLLECTOR  # type: ignore
from prometheus_client.core import GaugeMetricFamily, REGISTRY  # type: ignore

# Custom modules import
from . import router
from . import exceptions

CONFIG_DIRECTORY = os.getcwd() + "/config/"
if os.getcwd() == "/":
    CONFIG_DIRECTORY = "/config/"
MAIN_CONFIG_LOCATION = CONFIG_DIRECTORY + "config.yml"
ROUTERS_CONFIG_LOCATION = CONFIG_DIRECTORY + "routers.yml"
MAPPING_CONFIG_LOCATION = CONFIG_DIRECTORY + "mapping.yml"


def load_main_config():
    """Tries to create a config directory first
    if it can't find the main config in the config directory,
    it executes create_main_config()
    if it finds it, it reads it and returns it as a dict"""
    try:
        os.mkdir(CONFIG_DIRECTORY)
    except FileExistsError:
        print("Config directory already exists")
    except PermissionError:
        print("Can't create the config directory - premission denied")
        sys.exit(1)
    except OSError:
        print("Config directory creation failed because of a different error")
        sys.exit(1)
    try:
        with open(MAIN_CONFIG_LOCATION, "r", encoding="utf-8") as main_config:
            return yaml.safe_load(main_config)
    except FileNotFoundError:
        print("Main config not found!")
        create_main_config()


def load_routers_config():
    """Same as load_main_config() but with the routers config and without
    trying to create the config directory"""
    try:
        with open(ROUTERS_CONFIG_LOCATION,
                  "r",
                  encoding="utf-8") as routers_config:
            return yaml.safe_load(routers_config)
    except FileNotFoundError:
        create_routers_config()
        return None


def load_mapping_config():
    """Same as load_routers_config() but with the mapping config and without
    creating the file"""
    try:
        with open(MAPPING_CONFIG_LOCATION,
                  "r",
                  encoding="utf-8") as mapping_config:
            return yaml.safe_load(mapping_config)
    except FileNotFoundError:
        print("Mapping config does not exist, mapping disabled...")
        return None


def create_main_config():
    """Creates an example main config file"""
    print("Creating an example main config file...")
    config = {"cpython_metrics": False, "port": 9000,
              "address": "127.0.0.1", "debug": False}
    try:
        with open(MAIN_CONFIG_LOCATION, "w", encoding="utf-8") as main_config:
            yaml.dump(config, main_config)
    except FileNotFoundError:
        print("Config directory not found. Couldn't create the main config")
        sys.exit(1)
    print("Config file created in: " + MAIN_CONFIG_LOCATION)
    print("Exitting...")
    sys.exit()


def create_routers_config():
    """Creates an example routers config file"""
    print("Creating an example routers config file...")
    routers = {'router1':
               {'address': 'ip',
                'backend': 'dsl-ac55U',
                'transport':
                {'username': 'admin',
                 'password': 'admin'}},
               'router2':
               {'address': 'ip',
                'backend': 'dd-wrt',
                'transport':
                {'username': 'root',
                 'password': 'admin'}},
               'router3':
               {'address': 'ip',
                'backend': 'dd-wrt',
                'transport':
                {'username': 'root',
                 'use_keys': True}}}
    try:
        with open(ROUTERS_CONFIG_LOCATION,
                  "w",
                  encoding="utf-8") as routers_config:
            yaml.dump(routers, routers_config)
    except FileNotFoundError:
        print("Config directory not found. Couldn't create the routers config")
        sys.exit(1)
    print("Config file created in: " + ROUTERS_CONFIG_LOCATION)
    print("Exitting...")
    sys.exit()


def create_router_list(routers_dict):
    """Returns a list of router objects"""
    routers = []
    for rtr in routers_dict:
        if routers_dict[rtr]["backend"] == "dd-wrt":
            router_class = router.DdwrtRouter
        elif routers_dict[rtr]["backend"] == "ubnt":
            router_class = router.UbntRouter
        elif routers_dict[rtr]["backend"] == "dsl-ac55U":
            router_class = router.Dslac55uRouter
        try:
            router_object = router_class({rtr: routers_dict[rtr]})
        except paramiko.ssh_exception.NoValidConnectionsError:
            print("Error connecting to router " + rtr)
        except socket.gaierror:
            print("Could not resolve address: " + routers_dict[rtr]["address"])
        except exceptions.MissingCommand:
            print(rtr + " is missing both the 'wl' and 'wl_atheros' commands")
        except TimeoutError:
            print("Connecting to " + rtr + " timed out")
        else:
            routers.append(router_object)
    return routers


def translate_macs(rssi_dict):
    """Uses the mapping dict and replaces known MAC addresses in rssi_dict
    with nicknames from mapping
    returns the modified dict"""
    translated_dict = {}
    if rssi_dict is not None and MAPPING is not None:
        for mac in rssi_dict.keys():
            if mac in MAPPING:
                translated_dict.update({MAPPING[mac]: rssi_dict[mac]})
            else:
                translated_dict.update({mac: rssi_dict[mac]})
        return translated_dict
    else:
        return rssi_dict


class RouterCollector:
    """Custom collector class for prometheus_client"""

    def __init__(self, rtr):
        self.rtr = rtr

    def collect(self):
        """This is the function internally called by prometheus_client"""
        self.rtr.update()
        router_name = self.rtr.name.replace("-", "_").lower()
        if "proc" in self.rtr.supported_features:
            yield GaugeMetricFamily(router_name + '_mem_percent_used',
                                    'Percent of memory used',
                                    value=self.rtr.mem_used)
            load_gauge = GaugeMetricFamily(router_name + '_load',
                                           'Average load',
                                           labels=["t"])
            for i, l in enumerate(["1", "5", "15"]):
                load_gauge.add_metric(labels=[l + "m"],
                                      value=self.rtr.loads[i])
            yield load_gauge
        if "dmu_temp" in self.rtr.supported_features:
            yield GaugeMetricFamily(router_name + '_cpu_temp',
                                    'CPU temperature',
                                    value=self.rtr.dmu_temp)
        for index, interface in enumerate(self.rtr.wireless_interfaces):
            if "." in interface:
                interface = interface.replace(".", "_")
            if "signal" in self.rtr.supported_features:
                clients = translate_macs(self.rtr.ss_dicts[index])
                yield GaugeMetricFamily(router_name + '_clients_connected_'
                                        + interface,
                                        'Number of connected clients',
                                        value=len(clients.keys()))
                signal_gauge = GaugeMetricFamily(router_name
                                                 + '_client_signal_'
                                                 + interface,
                                                 'Client Signal Strength',
                                                 labels=["address"])
                for client in list(clients.keys()):
                    # This cleans the addresses for prometheus_client
                    # prometheus disallows the first character to be a number
                    if client[0].isnumeric():
                        name = "m_" + client.replace(":", "_")
                    else:
                        name = client.replace(":", "_")
                    signal_gauge.add_metric(labels=[name],
                                            value=clients[client])
                yield signal_gauge
            if "channel" in self.rtr.supported_features and \
               self.rtr.channels[index] is not None:
                yield GaugeMetricFamily(router_name + '_channel_' + interface,
                                        'Current wireless channel',
                                        value=self.rtr.channels[index])
            if "rxtx" in self.rtr.supported_features:
                yield GaugeMetricFamily(router_name + '_rx_' + interface,
                                        'Bytes received',
                                        value=self.rtr.interface_rx[index])
                yield GaugeMetricFamily(router_name + '_tx_' + interface,
                                        'Bytes transmitted',
                                        value=self.rtr.interface_tx[index])
            if "int_temp" in self.rtr.supported_features:
                yield GaugeMetricFamily(router_name + '_temp_' + interface,
                                        'Interface temperature',
                                        value=self.rtr.int_temperatures[index])


def main():
    config = load_main_config()
    if config["debug"]:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debug output enabled!")
    routers = create_router_list(load_routers_config())
    global MAPPING
    MAPPING = load_mapping_config()
    collectors = []
    for rtr in routers:
        print("Adding collector for " + rtr.name)
        collectors.append(RouterCollector(rtr))
    for collector in collectors:
        REGISTRY.register(collector)
    if not config["cpython_metrics"]:
        REGISTRY.unregister(PROCESS_COLLECTOR)
        REGISTRY.unregister(PLATFORM_COLLECTOR)
        REGISTRY.unregister(REGISTRY._names_to_collectors[
            'python_gc_objects_collected_total'
            ])
    start_http_server(config["port"], config["address"])
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nCaught CTRL+C, stopping program...")
        for collector in collectors:
            REGISTRY.unregister(collector)


if __name__ == "__main__":
    main()
