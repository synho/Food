#!/usr/bin/env bash
# One-time EC2 setup script for Health Navigation platform.
# Run on a fresh Amazon Linux 2023 / Ubuntu 22.04 instance:
#   chmod +x deploy/setup-ec2.sh && sudo ./deploy/setup-ec2.sh
#
# Prerequisites:
#   - EC2 instance: t3.small (2 vCPU, 2GB RAM) minimum
#   - EBS: 30GB gp3 root volume
#   - Security group: ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
#   - Elastic IP attached

set -euo pipefail

echo "=== Health Navigation — EC2 Setup ==="

# ── 1. Install Docker ────────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    if [ -f /etc/os-release ] && grep -q "amzn" /etc/os-release; then
        # Amazon Linux
        yum update -y
        yum install -y docker git
    else
        # Ubuntu/Debian
        apt-get update -y
        apt-get install -y ca-certificates curl gnupg git
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    fi
else
    echo "Docker already installed."
fi

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Add ec2-user to docker group (Amazon Linux) or ubuntu user (Ubuntu)
if id -u ec2-user &>/dev/null; then
    usermod -aG docker ec2-user
elif id -u ubuntu &>/dev/null; then
    usermod -aG docker ubuntu
fi

# ── 2. Install Docker Compose plugin (if not bundled) ────────────────────────

if ! docker compose version &>/dev/null; then
    echo "Installing Docker Compose plugin..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

echo "Docker Compose version: $(docker compose version)"

# ── 3. Clone repo ────────────────────────────────────────────────────────────

REPO_DIR="/home/ec2-user/Food"
if [ ! -d "$REPO_DIR" ]; then
    echo "Clone the repo manually:"
    echo "  git clone <your-repo-url> $REPO_DIR"
    echo "Then re-run this script."
fi

# ── 4. Setup .env files ─────────────────────────────────────────────────────

echo ""
echo "=== Environment Setup ==="
echo "Create the following .env files before starting:"
echo ""
echo "  $REPO_DIR/kg_pipeline/.env:"
echo "    GEMINI_API_KEY=<your-key>"
echo "    # Or use AWS Bedrock (no key needed if IAM configured)"
echo ""
echo "  $REPO_DIR/server/.env:"
echo "    CONTEXT_ENCRYPTION_KEY=<generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\">"
echo "    CORS_ORIGINS=*"
echo "    MASTER_GRAPH_PATH=/app/data/extracted_triples/master_graph.json"
echo ""

# ── 5. Create data directories ──────────────────────────────────────────────

if [ -d "$REPO_DIR" ]; then
    mkdir -p "$REPO_DIR/data/raw_papers"
    mkdir -p "$REPO_DIR/data/extracted_triples"
    mkdir -p "$REPO_DIR/data/manifests"
    echo "Data directories created."
fi

# ── 6. Setup daily backup cron ───────────────────────────────────────────────

if [ -f "$REPO_DIR/deploy/backup-neo4j.sh" ]; then
    chmod +x "$REPO_DIR/deploy/backup-neo4j.sh"
    # Add cron job for 3 AM daily backup
    CRON_CMD="0 3 * * * $REPO_DIR/deploy/backup-neo4j.sh >> /var/log/neo4j-backup.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "backup-neo4j" ; echo "$CRON_CMD") | crontab -
    echo "Daily Neo4j backup cron installed (3 AM)."
fi

# ── 7. Start services ───────────────────────────────────────────────────────

echo ""
echo "=== To start the stack ==="
echo "  cd $REPO_DIR"
echo "  docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build"
echo ""
echo "=== To verify ==="
echo "  docker compose ps"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8000/api/pipeline/status"
echo "  curl http://localhost:8000/api/kg/stats"
echo ""
echo "Setup complete."
