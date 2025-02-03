#!/bin/bash

CERT_PATH="/etc/ssl/certs/iscored.info.pem"
KEY_PATH="/etc/ssl/certs/iscored.info.key"

# Check if valid certificates exist; if not, use dummy certificates
if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    echo "Valid certificates not found. Using dummy certificates."
    ln -sf /etc/ssl/certs/iscored.info.pem "$CERT_PATH"
    ln -sf /etc/ssl/certs/iscored.info.key "$KEY_PATH"
else
    echo "Valid certificates found."
fi

# Start Nginx
echo "Starting Nginx..."
service nginx start

# Activate the virtual environment
echo "Activating virtual environment..."
source /opt/arcadescore/venv/bin/activate

# Start Gunicorn with logging configuration
echo "Starting Gunicorn..."
exec gunicorn -c /opt/arcadescore/config/gunicorn.conf.py run:app
