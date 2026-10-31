# Software and services

Software and Services in the dashboard talk to the Ubuntu agent. The agent reports package and systemd state itself. Install, remove, update, and service changes run only through `/opt/serverpilot-agent/serverpilot-helper`.

The helper accepts a fixed list of packages and `systemctl` actions. It does not run a shell. sudo is limited to that one program.

## One-time root install

On the Ubuntu server, from the agent directory:

```bash
sudo bash ~/serverpilot-agent/install-helper.sh
```

That copies the helper to `/opt/serverpilot-agent` and writes a sudoers rule for the user who invoked sudo. It does not grant unrestricted sudo.

Until that command has been run, **Check installed** and **Discover services** still work. Install, remove, and service buttons return a clear error.

## Using the UI

1. Sign in and open **Software** or **Services**.
2. Choose the server.
3. **Check installed** or **Discover services**.
4. Confirm install, update, remove, restart, enable, or disable. The page shows the job and its log, and the same record is under **Jobs** and **Audit**.

Services can be restarted, enabled, or disabled. Stop and delete are not offered. `ssh` and the core systemd units cannot be disabled. Python cannot be removed. A second package or service change on the same server waits until the first one finishes. If APT is locked, the job fails and tells you to retry.

Package changes are not cancelled while apt is running.
