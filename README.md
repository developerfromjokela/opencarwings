# OpenCARWINGS
[![](https://img.shields.io/github/sponsors/developerfromjokela?label=Sponsor&logo=GitHub)](https://github.com/sponsors/developerfromjokela)
[![BuyMeACoffee](https://raw.githubusercontent.com/pachadotdev/buymeacoffee-badges/main/bmc-donate-yellow.svg)](https://www.buymeacoffee.com/developerfromjokela)
[![Patreon](https://img.shields.io/endpoint.svg?url=https%3A%2F%2Fshieldsio-patreon.vercel.app%2Fapi%3Fusername%3Ddeveloperfromjokela%26type%3Dpatrons)](https://patreom.com/developerfromjokela)
[![Liberapay patrons](https://img.shields.io/liberapay/patrons/developerfromjokela?style=plastic&logo=liberapay&label=liberapay&link=https%3A%2F%2Fliberapay.com%2Fdeveloperfromjokela%2F)](https://liberapay.com/developerfromjokela/)

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
