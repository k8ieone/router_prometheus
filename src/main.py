#!/bin/env python3

import yaml
import os
import sys
import logging

DATA_DIRECTORY = os.getcwd()
MAIN_CONFIG_LOCATION = DATA_DIRECTORY + "/config/config.yml"
ROUTERS_CONFIG_LOCATION = DATA_DIRECTORY + "/config/routers.yml"


def load_main_config():
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
        with open(MAIN_CONFIG_LOCATION, "r") as main_config:
            return yaml.safe_load(main_config)
    except FileNotFoundError:
        print("Main config not found!")
        create_main_config()


def load_routers_config():
    try:
        with open(ROUTERS_CONFIG_LOCATION, "r") as routers_config:
            return yaml.safe_load(routers_config)
    except FileNotFoundError:
        create_routers_config()


def create_main_config():
    print("Creating an example main config file...")
    config = {"interval": 5, "port": 8080,
              "address": "127.0.0.1", "debug": True}
    try:
        with open(MAIN_CONFIG_LOCATION, "w") as main_config:
            yaml.dump(config, main_config)
    except:
        print("Main config file creation failed!")
        sys.exit(1)
    print("Config file created in: " + MAIN_CONFIG_LOCATION)
    print("Exitting...")
    sys.exit()


def create_routers_config():
    print("Creating an example routers config file...")
    routers = {"router1": {"address": "ip", "backend": "dd-wrt_atheros"}, "router2": {"address": "ip", "backend": "dd-wrt_broadcom"}}
    try:
        with open(ROUTERS_CONFIG_LOCATION, "w") as routers_config:
            yaml.dump(routers, routers_config)
    except:
        print("Routers config file creation failed!")
        sys.exit(1)
    print("Config file created in: " + ROUTERS_CONFIG_LOCATION)
    print("Exitting...")
    sys.exit()


def main():
    config = load_main_config()
    routers = load_routers_config()
    print(config)
    print(routers)


if __name__ == "__main__":
    main()

# Read the config files
# Connect to each router
# Print connected clients
