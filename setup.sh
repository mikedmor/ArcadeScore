#!/bin/bash

echo "🔧 Setting up and starting ArcadeScore..."

# Detect if running inside Docker
if [[ -f /.dockerenv ]]; then
    echo "🛠 Running inside Docker container"
    IS_DOCKER=1
else
    echo "🖥 Running on local system"
    IS_DOCKER=0
fi

# Step 1: Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python3 and try again."
    exit 1
fi

# Step 2: Create virtual environment if missing
if [ ! -d "venv" ]; then
    echo "🔄 Creating virtual environment..."
    python3 -m venv venv
fi

# Step 3: Activate virtual environment & install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Install 7-Zip if missing (only for Linux/Mac)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if ! command -v 7z &> /dev/null; then
        echo "🔄 Installing 7-Zip..."
        sudo apt update && sudo apt install -y p7zip-full || sudo yum install -y p7zip p7zip-plugins
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v 7z &> /dev/null; then
        echo "🔄 Installing 7-Zip..."
        brew install p7zip
    fi
fi

# Step 5: Nginx Configuration (Only in Docker)
if [[ $IS_DOCKER -eq 1 ]]; then
    echo "⚙️ Configuring Nginx for Docker..."

    # Define default values
    ARCADESCORE_HTTP_PORT=${ARCADESCORE_HTTP_PORT:-"8080"}
    SERVER_NAME=${SERVER_NAME:-"localhost"}
    SSL_PEM=${SSL_PEM:-"selfsigned.pem"}
    SSL_KEY=${SSL_KEY:-"selfsigned.key"}

    CERT_PATH="/etc/ssl/certs/$SSL_PEM"
    KEY_PATH="/etc/ssl/certs/$SSL_KEY"

    # Check if valid certificates exist; if not, generate self-signed certificates
    if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
        echo "Generating self-signed SSL certificate..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$KEY_PATH" -out "$CERT_PATH" \
            -subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=$SERVER_NAME"
    fi

    # Apply Nginx Configuration
    echo "Applying Nginx configuration..."
    envsubst '$SERVER_NAME $SSL_PEM $SSL_KEY $ARCADESCORE_HTTP_PORT' < /etc/nginx/nginx.template.conf > /etc/nginx/sites-available/default

    # Ensure Nginx config is enabled properly
    ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

    # Restart Nginx properly
    echo "Restarting Nginx..."
    service nginx restart || nginx -g "daemon off;" &
fi

# Step 6: Start the ArcadeScore server
echo "🚀 Starting ArcadeScore..."
python run.py
