# TODO Plan for Ansible Linux Server Deployment

## Phase 1: Planning and Design
- Define scope: Deploy Ubuntu servers for games (e.g., build farms, test environments).
- Roles: Base setup (packages, users), security (firewall, SSH), monitoring (Prometheus node exporter).
- Inventory: Sample for local/dev testing.
- Best practices: Idempotent tasks, variable overrides.

## Phase 2: Implementation
- Create main playbook: deploy.yml.
- Develop roles:
  - base-setup: Update, install essentials, set hostname.
  - security: UFW, fail2ban, SSH config.
  - monitoring: Install node exporter for metrics.
- Use templates for configs (e.g., MOTD).
- Test with Vagrant or local VM.

## Phase 3: Documentation and Testing
- Write README.md: Setup, running the playbook, customization.
- Create performance-tuning.md: Guide on Ansible optimization and server perf.
- Run ansible-lint for code quality.
- Add LICENSE.

## Phase 4: Enhancements (Future)
- Add roles for game-specific tools (e.g., Unity build agents).
- Integrate with CI/CD for auto-deploys.
- Support multiple distros (e.g., CentOS).

Timeline: 1 week. Focus on reusability for showcasing skills.
