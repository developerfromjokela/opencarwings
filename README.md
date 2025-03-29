# OpenCARWINGS

Server for running CARWINGS services for Nissan LEAF.

## Features

- [x] Remote control A/C
- [x] Remote control charging
- [x] Notifications

## Self-hosting with docker

1. Copy settings.docker.py and edit parameters
2. Copy .example.env to .env and edit parameters if necessary
3. Start up with docker-compose
4. Open port 55230 for TCU
5. Write your server URL to TCU using OBD
