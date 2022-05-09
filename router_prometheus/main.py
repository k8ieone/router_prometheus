import os
import sys
import logging
import signal
import socket

import yaml
import paramiko
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
# Todo: Figure out how to unregister the default collectors

# Custom modules import
from . import router
from . import exceptions

DATA_DIRECTORY = os.getcwd()
if os.getcwd() != "/":
    DATA_DIRECTORY = os.getcwd() + "/"
MAIN_CONFIG_LOCATION = DATA_DIRECTORY + "config/config.yml"
ROUTERS_CONFIG_LOCATION = DATA_DIRECTORY + "config/routers.yml"
MAPPING_CONFIG_LOCATION = DATA_DIRECTORY + "config/mapping.yml"


def load_main_config():
    """Tries to create a config directory first
    if it can't find the main config in the config directory,
    it executes create_main_config()
    if it finds it, it reads it and returns it as a dict"""
    try:
        os.mkdir(os.getcwd() + "config")
    except FileExistsError:
        print("Config directory already exists")
    except OSError([30]):
        print("Config directory couldn't be created because the filesystem is read-only")
        sys.exit(1)
    except OSError:
        print("Config directory couldn't be created because of a different error")
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
        with open(ROUTERS_CONFIG_LOCATION, "r", encoding="utf-8") as routers_config:
            return yaml.safe_load(routers_config)
    except FileNotFoundError:
        create_routers_config()
        return None


def load_mapping_config():
    """Same as load_routers_config() but with the mapping config and without
    creating the file"""
    try:
        with open(MAPPING_CONFIG_LOCATION, "r", encoding="utf-8") as mapping_config:
            return yaml.safe_load(mapping_config)
    except FileNotFoundError:
        return None


def create_main_config():
    """Creates an example main config file"""
    print("Creating an example main config file...")
    config = {"interval": 5, "port": 8080,
              "address": "127.0.0.1", "debug": False}
    try:
        with open(MAIN_CONFIG_LOCATION, "w", encoding="utf-8") as main_config:
            yaml.dump(config, main_config)
    except:
        print("Main config file creation failed!")
        sys.exit(1)
    print("Config file created in: " + MAIN_CONFIG_LOCATION)
    print("Exitting...")
    sys.exit()


def create_routers_config():
    """Creates an example routers config file"""
    print("Creating an example routers config file...")
    routers = {'router1': {'address': 'ip', 'backend': 'dsl-ac55U', 'transport': {'protocol': 'telnet', 'username': 'admin', 'password': 'admin'}}, 'router2': {'address': 'ip', 'backend': 'dd-wrt', 'transport': {'protocol': 'ssh', 'username': 'root', 'password': 'admin'}}, 'router3': {'address': 'ip', 'backend': 'dd-wrt', 'transport': {'protocol': 'ssh', 'username': 'root', 'use_keys': True}}}
    try:
        with open(ROUTERS_CONFIG_LOCATION, "w", encoding="utf-8") as routers_config:
            yaml.dump(routers, routers_config)
    except:
        print("Routers config file creation failed!")
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
        elif routers_dict[rtr]["backend"] == "dsl-ac55U":
            router_class = router.Dslac55uRouter
        try:
            router_object = router_class({rtr: routers_dict[rtr]})
        except paramiko.ssh_exception.NoValidConnectionsError:
            print("Error connecting to router " + rtr)
        except socket.gaierror:
            print("Could not resolve address: " + routers_dict[rtr]["address"])
        except exceptions.UnsupportedProtocol:
            print("Router " + rtr + " does not support the " + routers_dict[rtr]["transport"]["protocol"] + " protocol")
        except exceptions.MissingCommand:
            print(rtr + " is missing both the 'wl' and 'wl_atheros' commands")
        except TimeoutError:
            print("Connecting to " + rtr + " timed out")
        else:
            routers.append(router_object)
    return routers


def translate_macs(rssi_dict):
    """Takes the mapping dict and RSSI dict and replaces
    known MAC addresses with nicknames from mapping
    returns another dict"""
    mapping = load_mapping_config()
    translated_dict = {}
    if rssi_dict is not None:
        for mac in rssi_dict.keys():
            if mac in mapping:
                translated_dict.update({mapping[mac]: rssi_dict[mac]})
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
        for index, interface in enumerate(self.rtr.wireless_interfaces):
            hosts = translate_macs(self.rtr.ss_dicts[index])
            yield GaugeMetricFamily(self.rtr.name.replace("-", "_").lower() + '_clients_' + interface, 'Number of connected clients', value=len(hosts.keys()))
            if self.rtr.channels[index] is not None:
                yield GaugeMetricFamily(self.rtr.name.replace("-", "_").lower() + '_channel_' + interface, 'Current wireless channel', value=self.rtr.channels[index])
            ss_gauge = GaugeMetricFamily(self.rtr.name.replace("-", "_").lower() + '_client_signal_' + interface, 'Client Signal Strength', labels=["address"])
            for host in list(hosts.keys()):
                # These try-except-else blocks are only necessary because of
                # prometheus disallowing the first character to be a number
                try:
                    int(host[0])
                except ValueError:
                    name = host.replace(":", "_")
                else:
                    name = "m_" +  host.replace(":", "_")
                ss_gauge.add_metric(labels=[name], value=hosts[host])
            yield ss_gauge
        # i = InfoMetricFamily(self.rtr.name.replace("-", "_").lower() + '_clients_rssi', 'List of clients and their RSSIs')
        # i.add_metric(value={name: hosts[host]}, labels="signal")
        # yield i


def main():
    config = load_main_config()
    if config["debug"]:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debug output enabled!")
    routers = create_router_list(load_routers_config())
    collectors = []
    for rtr in routers:
        print("Adding collector for " + rtr.name)
        collectors.append(RouterCollector(rtr))
    for collector in collectors:
        REGISTRY.register(collector)
    start_http_server(config["port"], config["address"])
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nCaught CTRL+C, stopping program...")
        for collector in collectors:
            REGISTRY.unregister(collector)


if __name__ == "__main__":
    main()
