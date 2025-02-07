#!/bin/bash
set -e

# Define default values if variables are missing
SERVER_NAME=${SERVER_NAME:-"iscored.info www.iscored.info"}
SSL_PEM=${SSL_PEM:-"iscored.info.pem"}
SSL_KEY=${SSL_KEY:-"iscored.info.key"}

CERT_PATH="/etc/ssl/certs/$SSL_PEM"
KEY_PATH="/etc/ssl/certs/$SSL_KEY"

# Check if valid certificates exist; if not, generate self-signed certificates
if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    echo "Valid certificates not found. Generating self-signed certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_PATH" -out "$CERT_PATH" \
        -subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=$SERVER_NAME"
else
    echo "Valid certificates found."
fi

# Replace placeholders in Nginx config before starting Nginx
envsubst '$SERVER_NAME $SSL_PEM $SSL_KEY' < /etc/nginx/nginx.template.conf > /etc/nginx/sites-enabled/default

# Start Nginx
echo "Starting Nginx..."
service nginx start

# Activate the virtual environment
echo "Activating virtual environment..."
source /opt/arcadescore/venv/bin/activate

# Start Gunicorn with logging configuration
echo "Starting Gunicorn..."
exec gunicorn -c /opt/arcadescore/config/gunicorn.conf.py run:app
