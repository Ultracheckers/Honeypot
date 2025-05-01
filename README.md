# Plug-and-Play honeypot solution with a dashboard built using tauri
The honeypot will create a fake ftp, ssh, and http service and anytime someone accesses these services a log will be sent to the dashboard about it. The goal of the project was to make a simple honeypot system that just works with minimal configuration and hastle.

## Techstack
- Tauri (Typescript + Rust + Sveltekit)
- Docker
- Python (opencanary)
- MongoDB

## To build and use anything you need to prodive your own .env file for all three folders in the format
MONGODB_URI= and
DB_NAME=

### To run the honeypot, simply run the docker container using the start.sh script

### To build the Tauri application you can either run as dev with "npm run tauri dev" or build an executable using "npm run tauri build"

[![Screenshot-2025-04-15-213920.png](https://i.postimg.cc/bwFd67PB/Screenshot-2025-04-15-213920.png)](https://postimg.cc/hXTSv3fL)
