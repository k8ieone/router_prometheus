# router_prometheus

## Project goals
 - [X] YML configuration file for defining global options and routers
 - [X] Have different backends to get metrics from different routers so that the project is extendable to more router brands and systems
 - [ ] Using public key authentication in SSH
 - [X] Expose a Prometheus endpoint so metrics can be scraped by Prometheus scrapers
 - [X] Docker container

## Collected metrics
 - [X] Number of connected WiFi clients
 - [X] Clients' MAC addresses (can be mapped to names) and their signal strength
   - [X] DSL-AC55U reports bands (2.4 GHz and 5 GHz) separately
   - [ ] DD-WRT reports bands separately (I don't have a multiband router to do this with)
 - [ ] Current channel (or radio off)

## Known issues
 - When a command gets stuck, it hangs the whole progam indeffinitely (caused by [this issue](https://github.com/fabric/fabric/issues/2197))
 - I should figure out a way to have the number of devices metric be separate for each band without having one constantly at 0 for 2.4 GHz routers only

## Config file markup

config.yml:
```yml
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
