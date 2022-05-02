#!/bin/env python3

import os
import sys
import logging
import signal
import yaml

from prometheus_client import start_http_server, Gauge
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily, REGISTRY
# Todo: Figure out how to unregister the default collectors
# from prometheus_client.core import REGISTRY

# Custom modules import
from .router import *
from .exceptions import *

DATA_DIRECTORY = os.getcwd()
MAIN_CONFIG_LOCATION = DATA_DIRECTORY + "/config/config.yml"
ROUTERS_CONFIG_LOCATION = DATA_DIRECTORY + "/config/routers.yml"
MAPPING_CONFIG_LOCATION = DATA_DIRECTORY + "/config/mapping.yml"

def load_main_config():
    """Tries to create a config directory first
    if it can't find the main config in the config directory,
    it executes create_main_config()
    if it finds it, it reads it and returns it as a dict"""
    try:
        os.mkdir(os.getcwd() + "/config")
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
              "address": "127.0.0.1", "debug": True}
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

def create_router_list(routers_dict, mapping):
    """Returns a list of router objects"""
    routers = []
    for r in routers_dict:
        if routers_dict[r]["backend"] == "dd-wrt":
            try:
                router_object = router.DdwrtRouter({r: routers_dict[r]}, mapping)
            except exceptions.ConnectionFailed:
                print("Error connecting to router " + r)
            except exceptions.UnsupportedProtocol:
                print("Router " + r + " does not support the " + routers_dict[r]["transport"]["protocol"] + " protocol")
            except exceptions.MissingCommand:
                print(r + " is missing both wl and wl_atheros")
            else:
                routers.append(router_object)
    return routers


def threaded_loop(r):
    connection = "c"

def start_threads(routers):
    for r in routers:
        threaded_loop(r)

class RouterCollector:
    def __init__(self, r):
        self.r = r

    def collect(self):
        self.r.update()
        hosts = self.r.translate_macs()
        yield GaugeMetricFamily(self.r.name.replace("-", "_").lower() + '_clients', 'Number of connected clients', value=len(self.r.clients_list))
        m = GaugeMetricFamily(self.r.name.replace("-", "_").lower() + '_client_rssi', 'Client RSSI', labels=["address"])
        #i = InfoMetricFamily(self.r.name.replace("-", "_").lower() + '_clients_rssi', 'List of clients and their RSSIs')
        for host in hosts:
            try:
                int(host[0])
            except:
                name = host.replace(":", "_")
            else:
                name = "m_" +  host.replace(":", "_")
            #i.add_metric(value={name: hosts[host]}, labels="signal")
            m.add_metric(labels=[name], value=hosts[host])
        yield m
        #yield i


def main():
    config = load_main_config()
    if config["debug"]:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug("Debug output enabled!")
    routers = create_router_list(load_routers_config(), load_mapping_config())
    collectors = []
    for r in routers:
        collectors.append(RouterCollector(r))
    for c in collectors:
        REGISTRY.register(c)
    start_http_server(config["port"], config["address"])
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nCaught CTRL+C, clsing connections")
        for c in collectors:
            REGISTRY.unregister(c)
        for r in routers:
            r.cleanup()

if __name__ == "__main__":
    main()

# Read the config files
# Connect to each router
# Print connected clients
