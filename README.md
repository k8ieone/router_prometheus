# router_prometheus

## Project goals
 - [X] YML configuration file for defining global options and routers
 - [ ] Different backends to get metrics from different routers (currently DD-WRT Broadcom, DD-WRT Atheros and DSL-AC55U) so that the project is extendable to more brands and systems
 - [ ] Using public key authentication in SSH
 - [ ] Expose a Prometheus endpoint so metrics can be scraped by Prometheus scrapers
 - [ ] Docker container

## Collected metrics
 - [ ] Number of connected WiFi clients
 - [ ] Clients' MAC addresses (can be mapped to names)
 - [ ] Clients' RSSI

## Config file markup

config.yml:
```yml
interval: 5
port: 8080
address: 127.0.0.1
debug: yes
```

routers.yml:
```yml
DSL-AC55U:
   address: 10.0.0.1
   backend: dsl-ac55U
   transport:
      protocol: telnet
      username: admin
      password: admin
RT-N18U:
   address: 10.0.0.2
   backend: dd-wrt
   transport:
      protocol: ssh
      username: root
      password: admin
TL-WR1043ND:
   address: 10.0.0.3
   backend: dd-wrt
   transport:
      protocol: ssh
      username: root
      use_keys: True
```

mapping.yml:
```yml
00:00:00:00:00:00: "Phone"
11:11:11:11:11:11: "Laptop"
```
