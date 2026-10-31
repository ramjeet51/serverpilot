# Ubuntu agent

The agent is `agent/agent.py`. It uses only the Python standard library. It connects outbound, registers once, then sends a health report every 15 seconds. It does not accept shell commands.

## When the server can reach the Mac

1. In the UI, open Servers and add the host. Copy the registration token and gateway URL.
2. On Ubuntu, as a user that should run the agent:

```bash
mkdir -p ~/serverpilot-agent/state
# copy agent/agent.py and agent/run.sh into ~/serverpilot-agent
chmod 700 ~/serverpilot-agent/state
AGENT_SERVER_URL='ws://<mac-lan-ip>:8001/v1/connect' \
AGENT_REGISTRATION_TOKEN='<token from the UI>' \
~/serverpilot-agent/run.sh
```

The agent stores its long-lived token in `state/agent.json` (mode 0600) and reconnects by itself.

To start it on boot as root, install `agent/serverpilot-agent.service` to `/etc/systemd/system/`, copy the files to `/opt/serverpilot-agent`, and enable the unit. That needs sudo on the Ubuntu host.

## When the server cannot reach the Mac

`k8s-worker` (172.16.17.59) can be reached by SSH from this Mac, but it cannot open a connection back to the Mac. For that host:

- `AGENT_TUNNEL_SSH` in the root `.env` makes PM2 keep `ssh -R`, so port 8001 on the Ubuntu host forwards to the gateway on the Mac.
- `AGENT_ADVERTISED_URL` is `ws://127.0.0.1:8001/v1/connect`. That address only works on the Ubuntu host, through the tunnel.
- The gateway itself stays on `127.0.0.1`.

The UI shows the token once, under Servers. New token replaces the old one and the agent must register again.
