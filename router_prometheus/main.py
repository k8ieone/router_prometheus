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
            mapping = yaml.safe_load(mapping_config)
        mapping_uppercase = {}
        for mac in mapping:
            mapping_uppercase[mac.upper()] = mapping[mac]
        return mapping_uppercase
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
        elif routers_dict[rtr]["backend"] == "openwrt":
            router_class = router.OwrtRouter
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
            if mac.upper() in MAPPING:
                translated_dict.update({MAPPING[mac.upper()]: rssi_dict[mac]})
            else:
                translated_dict.update({mac.upper(): rssi_dict[mac]})
        return translated_dict
    else:
        return rssi_dict


class RouterCollector:
    """Custom collector class for prometheus_client"""

    def __init__(self, routers):
        self.routers = routers

    def collect(self):
        """This is the function internally called by prometheus_client"""
        gauges = []
        load_gauge = GaugeMetricFamily('router_system_load',
                                       'Average system load',
                                       labels=["router", "t"])
        mem_gauge = GaugeMetricFamily('router_mem_percent_used',
                                      'Percent of memory used',
                                      labels=["router"])
        # TODO: Reimplement temperature monitoring
        temp_gauge = GaugeMetricFamily('router_thermal',
                                       'Router temperature probes',
                                       labels=["router"])
        signal_gauge = GaugeMetricFamily('router_ap_client_signal',
                                         'Client Signal Strength',
                                         labels=["router",
                                                 "clientname", "interface"])
        channgel_gauge = GaugeMetricFamily('router_ap_channel',
                                           'Current wireless channel',
                                           labels=["router", "interface"])
        tx_gauge = GaugeMetricFamily('router_net_sent',
                                     'Bytes sent',
                                     labels=["router", "interface"])
        rx_gauge = GaugeMetricFamily('router_net_recv',
                                     'Bytes received',
                                     labels=["router", "interface"])
        # There has to be a nicer way to append all of these
        gauges.append(load_gauge)
        gauges.append(mem_gauge)
        gauges.append(temp_gauge)
        gauges.append(signal_gauge)
        gauges.append(channgel_gauge)
        gauges.append(tx_gauge)
        gauges.append(rx_gauge)
        for rtr in self.routers:
            rtr.update()
            if "proc" in rtr.supported_features:
                for i, l in enumerate(["1", "5", "15"]):
                    load_gauge.add_metric(labels=[rtr.name, l + "m"],
                                          value=rtr.loads[i])
                mem_gauge.add_metric(labels=[rtr.name],
                                     value=rtr.mem_used)
            if "thermal" in rtr.supported_features:
                pass
            #    yield GaugeMetricFamily('router_cpu_temp',
            #                            'CPU temperature',
            #                            value=rtr.dmu_temp)
            #    yield GaugeMetricFamily(router_name + '_temp_' + interface,
            #                            'Interface temperature',
            #                            value=rtr.int_temperatures[index])
            for index, interface in enumerate(rtr.wireless_interfaces):
                if "signal" in rtr.supported_features:
                    if len(rtr.ss_dicts) == 0:
                        clients = {}
                    else:
                        clients = translate_macs(rtr.ss_dicts[index])
                    for client in list(clients.keys()):
                        signal_gauge.add_metric(labels=[rtr.name, client,
                                                        interface],
                                                value=clients[client])
                if "channel" in rtr.supported_features and \
                   len(rtr.channels) != 0 and \
                   rtr.channels[index] is not None:
                    channgel_gauge.add_metric(labels=[rtr.name, interface],
                                              value=rtr.channels[index])
                if "rxtx" in rtr.supported_features and \
                   len(rtr.interface_rx) > 0 and \
                   len(rtr.interface_tx) > 0:
                    tx_gauge.add_metric(labels=[rtr.name, interface],
                                        value=rtr.interface_tx[index])
                    rx_gauge.add_metric(labels=[rtr.name, interface],
                                        value=rtr.interface_rx[index])
        for gauge in gauges:
            yield gauge


def main():
    config = load_main_config()
    if config["debug"]:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debug output enabled!")
    routers = create_router_list(load_routers_config())
    global MAPPING
    MAPPING = load_mapping_config()
    collectors = []
    collectors.append(RouterCollector(routers))
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
