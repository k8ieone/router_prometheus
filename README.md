# router_prometheus

## Project goals
 - [X] YML configuration file for defining global options and routers
 - [ ] Different backends to get metrics from different routers (currently DD-WRT Broadcom, DD-WRT Atheros and DSL-AC55U) so that the project is extendable to more brands and systems
 - [ ] Using public key authentication in SSH
 - [ ] Expose a Prometheus endpoint so metrics can be scraped by Prometheus scrapers
 - [ ] Docker container

## Collected metrics
 - [ ] Connected WiFi clients' MAC addresses

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
   backend: dd-wrt_broadcom
   transport:
      protocol: ssh
      username: root
      password: admin
TL-WR1043ND:
   address: 10.0.0.3
   backend: dd-wrt_atheros
   transport:
      protocol: ssh
      username: root
      use_keys: True
```
