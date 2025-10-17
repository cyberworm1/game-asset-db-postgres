# Performance Tuning Guide for Ansible-Deployed Linux Servers

This guide focuses on optimizing servers for games industry loads, like running build agents or multiplayer tests.

## 1. Ansible Optimization
- Use `--forks 10` for parallel runs on multiple hosts.
- Enable pipelining in ansible.cfg: `pipelining = True` to reduce SSH overhead.

## 2. Server Resource Tuning
- Sysctl tweaks: Edit /etc/sysctl.conf with `net.core.somaxconn = 1024` for high connections.
- LimitSwap: Use `systemd` to cap memory for services.

## 3. Monitoring and Scaling
- Use node exporter metrics: Query CPU/IO via Prometheus.
- Auto-scaling: Integrate with cloud providers (e.g., AWS EC2 tags in inventory).

## 4. Benchmarking
- Stress test: `stress --cpu 8 --io 4 --vm 2 --vm-bytes 128M --timeout 10s`
- Tune kernel: `sysctl -w vm.swappiness=10` for low swap.

Regularly review logs with `journalctl` for bottlenecks.
