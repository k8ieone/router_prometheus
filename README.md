# router_prometheus

![Example Grafana Dashboard](.github/grafana_screenshot.png)


## Features
 - [X] YML configuration file for defining global options and routers
 - [X] Mapping MAC addresses to user-friendly device names
 - [X] Different [backends](#available-backends) for different systems and brands so that the project is easily extendable
 - [ ] Using public key authentication in SSH
 - [X] Expose a Prometheus endpoint so metrics can be scraped by Prometheus scrapers
 - [X] Docker container

Other project goals are tracked with in [issues](https://github.com/a13xie/router_prometheus/issues)

## Collected metrics

| Metric | Description | Required feature |
| :-------------- | :-------------: | -------------: |
| `router_ap_client_signal` | Current [signal strength](https://www.securedgenetworks.com/blog/wifi-signal-strength#what-is-a-good-wifi-signal-stength) (in dBm) for each connected client device | `signal` |
| `router_ap_channel` | Current [channel](https://en.wikipedia.org/wiki/List_of_WLAN_channels) of each interface | `channel` |
| `router_net_sent`, `router_net_recv` | Total number of bytes received/transmitted on a wireless interface, read from `/sys/class/net/INTERFACE/statistics/rx_bytes` | `rxtx` |
| `router_system_load` | Average load (over the last 1, 5 and 15 minutes), read from `/proc/loadavg` | `proc` |
| `router_mem_percent_used` | Used memory in %, calculated from `/proc/meminfo` | `proc` |
| `router_thermal` | Temperature info from the router's temperature probes | `thermal` |

## Available backends

| Backend | Description | Available features |
| :-------------- | :-------------: | -------------: |
| `dd-wrt`    | Should support all routers running [DD-WRT](https://dd-wrt.com/) | `signal`, `channel`, `rxtx`, `proc`, `thermal` |
| `openwrt`    | Should support all routers running [OpenWRT](https://openwrt.org/) | `signal`, `channel`, `rxtx`, `proc` |
| `ubnt`      | Should work on most Ubiquiti bridge devices | `signal`, `channel`, `rxtx`, `proc` |
| `dsl-ac55u` | Only supports the Asus DSL-AC55U | `signal`, `channel`, `rxtx`, `proc` |

## Known issues

Feel free to open a new issue [here](https://github.com/a13xie/router_prometheus/issues), be it a bug report, feature request or just a question.

 - When a command gets stuck, it hangs the whole progam indefinitely (caused by [this issue](https://github.com/fabric/fabric/issues/2197))
   - Same goes for losing connection

## Example config files

config.yml:
```yml
port: 9000
address: 127.0.0.1
debug: true
cpython_metrics: false
```

routers.yml:
```yml
DSL-AC55U:
   address: 10.0.0.1
   backend: dsl-ac55U
   transport:
      username: admin
      password: admin
RT-N18U:
   address: 10.0.0.2
   backend: dd-wrt
   transport:
      username: root
      password: admin
Loco-M5:
   address: 10.0.0.3
   backend: ubnt
   transport:
      username: ubnt
      use_keys: True
```

mapping.yml:
```yml
00:00:00:00:00:00: "Phone"
11:11:11:11:11:11: "Laptop"
```
