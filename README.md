# OpenCARWINGS

Server for running CARWINGS services for Nissan LEAF.

## Implemented features

- [x] Remote control A/C
- [x] Remote control charging
- [x] Notifications
- [x] Read TCU configuration
- [ ] Write TCU configuration
- [ ] CARWINGS in navigation head unit
- [ ] Trip journey & efficiency info

## Public instances

- [opencarwings.viaaq.eu](https://opencarwings.viaaq.eu)

## Self-hosting with docker

1. Copy settings.docker.py and edit parameters
2. Copy .example.env to .env and edit parameters if necessary
3. Start up with docker-compose
4. Open port 55230 for TCU
5. Write your server URL to TCU using OBD

## TCU protocol and misc info
Please check out repo: [nissan-leaf-tcu](https://github.com/developerfromjokela/nissan-leaf-tcu/)
