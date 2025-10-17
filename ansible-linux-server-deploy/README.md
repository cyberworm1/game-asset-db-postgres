# Ansible Playbook for Linux Server Deployment (Games Industry)

This repository contains an Ansible playbook for provisioning Linux servers in a games industry context, such as for build pipelines or staging environments during title releases. It demonstrates automation skills with roles for setup, security, monitoring, and automated Postgres failover orchestration.

## Features
- **Modular Roles**: Base setup, security hardening, observability stack deployment, and repmgr-backed failover automation.
- **Idempotent**: Safe to rerun.
- **Customization**: Via vars files.
- **Tuning Guide**: For performance in high-load game server scenarios.

## Prerequisites
- Ansible 2.10+ installed.
- SSH access to target hosts (key-based recommended).
- Sudo privileges on targets.

## Setup Instructions
1. Clone the repo: `git clone https://github.com/yourusername/ansible-linux-server-deploy.git`
2. Edit `inventory.ini` with your host IPs/groups.
3. Run the playbook: `ansible-playbook -i inventory.ini deploy.yml --ask-become-pass`
4. For dry-run: Add `--check`.

## Inventory Example
See `inventory.ini` for groups like [gameservers].

## Roles Overview
- **base-setup**: Installs packages, sets timezone, MOTD.
- **security**: Configures UFW, fail2ban, hardens SSH.
- **monitoring**: Installs Prometheus, node exporter, optional Grafana, and provisions a textfile collector for automation metrics.
- **failover**: Installs `repmgr`, deploys the automated failover controller, and schedules a systemd timer for replica promotion drills.

## Usage in Title Releases
Use this to spin up servers for testing builds: Group hosts in inventory and run selectively with `--tags base-setup`.

See `docs/performance-tuning.md` for optimization.

## Contributing
PRs welcome for additional roles (e.g., game engine installs).

## License
MIT
