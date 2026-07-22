#!/data/data/com.termux/files/usr/bin/bash
# urirun Android node bootstrap — runs inside Termux on Android
# Usage: curl -fsSL http://HOST:8195/bootstrap.sh | bash
# Or with options: URIRUN_NODE_PORT=8765 URIRUN_NODE_NAME=nexus7 bash bootstrap-termux.sh

set -Eeuo pipefail

URIRUN_PORT="${URIRUN_NODE_PORT:-8765}"
URIRUN_NAME="${URIRUN_NODE_NAME:-}"
INSTALL_DIR="${URIRUN_NODE_DIR:-$HOME/.urirun-node}"
URIRUN_VERSION="${URIRUN_VERSION:-}"  # pin version if needed, e.g. "==0.4.21"
HOST_URL="${URIRUN_HOST_URL:-}"       # optional: register with host on completion

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}==> $*${NC}"; }
success() { echo -e "${GREEN}==> $*${NC}"; }
warn()    { echo -e "${YELLOW}==> $*${NC}"; }
error()   { echo -e "${RED}==> ERROR: $*${NC}" >&2; }

# ---- device name ----------------------------------------------------------
if [[ -z "$URIRUN_NAME" ]]; then
    raw_model="$(getprop ro.product.model 2>/dev/null || echo "")"
    if [[ -n "$raw_model" ]]; then
        URIRUN_NAME="$(echo "$raw_model" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')"
    else
        URIRUN_NAME="android"
    fi
fi

# ---- get LAN IP -----------------------------------------------------------
get_lan_ip() {
    ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}' || \
    ip addr show wlan0 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -1 || \
    echo "unknown"
}

# ---- step 1: update packages ----------------------------------------------
info "Updating Termux packages..."
pkg update -y 2>&1 | tail -3 || warn "pkg update had warnings (continuing)"
pkg upgrade -y 2>&1 | tail -3 || warn "pkg upgrade had warnings (continuing)"

# ---- step 2: install dependencies -----------------------------------------
info "Installing Python and tools..."
pkg install -y python git curl openssh 2>&1 | tail -5

# ---- step 3: install urirun -----------------------------------------------
info "Installing urirun..."
PIPSPEC="urirun${URIRUN_VERSION:+[keyauth]$URIRUN_VERSION}"
[[ -z "$URIRUN_VERSION" ]] && PIPSPEC="urirun[keyauth]>=0.4.21"
python -m pip install --upgrade pip --quiet
python -m pip install --upgrade "$PIPSPEC" --quiet
success "urirun installed: $(urirun --version 2>/dev/null || echo 'ok')"

# ---- step 4: create node venv & install -----------------------------------
info "Creating node environment at $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
python -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/.venv/bin/pip" install --upgrade "$PIPSPEC" --quiet

# ---- step 5: install node-side connectors & build registry ----------------
info "Installing node-side connectors..."
NODE_URIRUN="$INSTALL_DIR/.venv/bin/urirun"
NODE_PIP="$INSTALL_DIR/.venv/bin/pip"

# Connectors that expose the device's own filesystem/system over the mesh.
# Extra connectors can be passed via URIRUN_NODE_CONNECTORS="a,b,c".
DEFAULT_CONNECTORS="urirun-connector-mcp-filesystem"
EXTRA_CONNECTORS="${URIRUN_NODE_CONNECTORS:-}"
for spec in ${DEFAULT_CONNECTORS//,/ } ${EXTRA_CONNECTORS//,/ }; do
    [[ -z "$spec" ]] && continue
    info "  pip install $spec"
    "$NODE_PIP" install --upgrade "$spec" --quiet || warn "could not install $spec (skipping)"
done

# Discover installed connector entry points and compile a registry in one step.
info "Building node registry from installed connectors..."
REGISTRY="$INSTALL_DIR/registry.json"
"$NODE_URIRUN" discover --registry-out "$REGISTRY" >/dev/null 2>&1 || {
    warn "discover produced no registry; writing empty registry"
    echo '{"version":"urirun.bindings.v2","routes":{}}' > "$REGISTRY"
}
ROUTE_COUNT="$("$INSTALL_DIR/.venv/bin/python" -c "import json;r=json.load(open('$REGISTRY'));print(len(r.get('routes') or r.get('index') or {}))" 2>/dev/null || echo '?')"
success "Registry built at $REGISTRY ($ROUTE_COUNT routes)"

# ---- step 6: write node config & run script --------------------------------
info "Writing node config..."
ANDROID_VERSION="$(getprop ro.build.version.release 2>/dev/null || echo 'unknown')"
SDK_VERSION="$(getprop ro.build.version.sdk 2>/dev/null || echo 'unknown')"
MANUFACTURER="$(getprop ro.product.manufacturer 2>/dev/null || echo 'unknown')"

# device-info.json is informational metadata (not the urirun node config schema).
cat > "$INSTALL_DIR/device-info.json" <<NODE_JSON
{
  "name": "$URIRUN_NAME",
  "port": $URIRUN_PORT,
  "platform": "android",
  "androidVersion": "$ANDROID_VERSION",
  "sdkVersion": "$SDK_VERSION",
  "manufacturer": "$MANUFACTURER",
  "installDir": "$INSTALL_DIR"
}
NODE_JSON

# --allow globs are the node's security boundary: only matching routes execute.
# Override with URIRUN_NODE_ALLOW="scheme://*,other://*".
NODE_ALLOW="${URIRUN_NODE_ALLOW:-fs://*,sys://*,node://*,hash://*,uuid://*}"
ALLOW_ARGS=""
for glob in ${NODE_ALLOW//,/ }; do
    ALLOW_ARGS="$ALLOW_ARGS --allow '$glob'"
done

cat > "$INSTALL_DIR/run-node.sh" <<RUN_NODE
#!/data/data/com.termux/files/usr/bin/bash
# Generated by urirun android-node bootstrap.
INSTALL_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
exec "\$INSTALL_DIR/.venv/bin/urirun" node serve \\
    --name "$URIRUN_NAME" \\
    --registry "\$INSTALL_DIR/registry.json" \\
    --host 0.0.0.0 \\
    --port $URIRUN_PORT \\
    --execute $ALLOW_ARGS
RUN_NODE
chmod +x "$INSTALL_DIR/run-node.sh"

# ---- step 7: Termux:Boot integration -------------------------------------
BOOT_DIR="$HOME/.termux/boot"
if mkdir -p "$BOOT_DIR" 2>/dev/null; then
    cat > "$BOOT_DIR/start-urirun.sh" <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
exec $INSTALL_DIR/run-node.sh >> $INSTALL_DIR/node.log 2>&1
BOOT
    chmod +x "$BOOT_DIR/start-urirun.sh"
    success "Termux:Boot entry created (install Termux:Boot from F-Droid for auto-start)"
else
    warn "Could not create Termux:Boot entry"
fi

# ---- step 8: start the node now -------------------------------------------
info "Starting urirun node in background..."
nohup "$INSTALL_DIR/run-node.sh" >> "$INSTALL_DIR/node.log" 2>&1 &
NODE_PID=$!
sleep 2

LAN_IP="$(get_lan_ip)"
NODE_URL="http://${LAN_IP}:${URIRUN_PORT}"

# Quick health check
if curl -sf "${NODE_URL}/health" >/dev/null 2>&1; then
    success "Node is running at $NODE_URL"
else
    warn "Node may still be starting. Check: $INSTALL_DIR/node.log"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  urirun node '${URIRUN_NAME}' is ready!${NC}"
echo -e "${GREEN}  URL: ${NODE_URL}${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  On your computer, add this node:"
echo -e "  ${CYAN}urirun host add-node $URIRUN_NAME $NODE_URL${NC}"
echo ""
echo "  Logs: $INSTALL_DIR/node.log"
echo "  Stop: kill $NODE_PID"
