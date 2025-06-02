#!/bin/bash
set -eu

# Start BOINC client in background
BOINC_DIR="/root/boinc_client"
mkdir -p "$BOINC_DIR"
boinc --dir "$BOINC_DIR" &
BOINC_PID=$!
cd "$BOINC_DIR"


# Wait for BOINC client to be ready
CLIENT_TIMEOUT=5
echo "[Client] Waiting for BOINC client to be ready..."
until boinccmd --get_state > /dev/null 2>&1; do
  echo "[Client] BOINC client is not ready yet, retrying in $CLIENT_TIMEOUT seconds..."
  sleep "$CLIENT_TIMEOUT"
done
echo "[Client] BOINC client is ready!"


# Wait for project server
SERVER_TIMEOUT=10
echo "[Server] Waiting for project server at $PROJECT_URL..."
until curl -fsSL --connect-timeout 1 "$PROJECT_URL" > /dev/null; do
  echo "[Server] Project is not available yet, retrying in $SERVER_TIMEOUT seconds..."
  sleep "$SERVER_TIMEOUT"
done
echo "[Server] Project is available!"


# Generate credentials if not generated yet
if [ ! -f /root/credentials.sh ]; then
  HOSTNAME=$(hostname)
  ACCOUNT_NAME="${HOSTNAME}"
  ACCOUNT_EMAIL="${HOSTNAME}@example.com"
  ACCOUNT_PASSWORD="${HOSTNAME}"

  cat > /root/credentials.sh <<EOF
ACCOUNT_NAME="$ACCOUNT_NAME"
ACCOUNT_EMAIL="$ACCOUNT_EMAIL"
ACCOUNT_PASSWORD="$ACCOUNT_PASSWORD"
EOF
fi
# And load credentials
source /root/credentials.sh
echo "Credentials are following: name=$ACCOUNT_NAME, email=$ACCOUNT_EMAIL, password=$ACCOUNT_PASSWORD"


# Checking the project attachment and fix if needed
echo "Checking the account on the project..."
boinccmd --lookup_account "$PROJECT_URL" "$ACCOUNT_EMAIL" "$ACCOUNT_PASSWORD" > /root/raw.txt
if ! grep -qF "account key:" /root/raw.txt; then
  echo "Account not found, detaching just in case..."
  boinccmd --project "$PROJECT_URL" detach || true
  echo "Account not found, creating a new one..."
  boinccmd --create_account "$PROJECT_URL" "$ACCOUNT_EMAIL" "$ACCOUNT_PASSWORD" "$ACCOUNT_NAME" > /root/raw.txt
  if ! grep -qF "account key:" /root/raw.txt; then
    echo "Expected successful account creation"
    exit 1
  fi
  ACCOUNT_KEY=$(grep "account key:" /root/raw.txt | awk -F': ' '{print $2}')
  cat > /root/account_key.sh <<EOF
ACCOUNT_KEY="$ACCOUNT_KEY"
EOF
  echo "Account created, attaching..."
  boinccmd --project_attach "$PROJECT_URL" "$ACCOUNT_KEY"
fi
# And load account key (just for convenience)
source /root/account_key.sh
echo "Account key is following: $ACCOUNT_KEY"


# Setup periodic force updates if configured
if [ "${FORCE_UPDATE_INTERVAL:-0}" -ne 0 ]; then
  (
    while true; do
      ts="$(date '+%Y-%m-%d %H:%M:%S')"
      echo "[$ts] Running boinccmd project update"
      boinccmd --project "$PROJECT_URL" update || true
      sleep "$FORCE_UPDATE_INTERVAL"
    done
  ) &
fi


# Wait for BOINC client process
wait $BOINC_PID
