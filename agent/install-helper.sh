#!/bin/bash
# Install the restricted root helper and one sudoers rule for the agent user.
# Run on the Ubuntu server: sudo bash install-helper.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this as root: sudo bash $0" >&2
  exit 1
fi

SOURCE="$(cd "$(dirname "$0")" && pwd)"
AGENT_USER="${SUDO_USER:-evervent}"
TARGET="/opt/serverpilot-agent"

install -d -o root -g root -m 755 "$TARGET"
install -d -o root -g root -m 755 "$TARGET/modules"
install -m 644 "$SOURCE/modules/__init__.py" "$TARGET/modules/__init__.py"
install -m 644 "$SOURCE/modules/catalogue.py" "$TARGET/modules/catalogue.py"
install -m 644 "$SOURCE/modules/sanitize.py" "$TARGET/modules/sanitize.py"
install -m 644 "$SOURCE/modules/helper_ops.py" "$TARGET/modules/helper_ops.py"
cat > "$TARGET/serverpilot-helper" << 'EOF'
#!/usr/bin/env python3
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent / "modules" / "helper_ops.py"), run_name="__main__")
EOF
chown root:root "$TARGET/serverpilot-helper"
chmod 755 "$TARGET/serverpilot-helper"

RULE="$AGENT_USER ALL=(root) NOPASSWD: /opt/serverpilot-agent/serverpilot-helper"
printf '%s\n' "$RULE" > /etc/sudoers.d/serverpilot-agent
chown root:root /etc/sudoers.d/serverpilot-agent
chmod 440 /etc/sudoers.d/serverpilot-agent
visudo -cf /etc/sudoers.d/serverpilot-agent
echo "Helper installed for ${AGENT_USER}. sudo is limited to /opt/serverpilot-agent/serverpilot-helper."
