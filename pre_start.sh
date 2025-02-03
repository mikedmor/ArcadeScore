#!/bin/sh
# Pre-start script for ArcadeScore

# Define directories
VPS_DATA_DIR="/opt/arcadescore/app/vps-data"
IMAGES_DIR="/opt/arcadescore/app/static/images"

# Create directories if they don't exist
mkdir -p $VPS_DATA_DIR
mkdir -p $IMAGES_DIR

# Initialize VPS data if not present
if [ ! -f "$VPS_DATA_DIR/vpsdb.json" ]; then
    echo "{}" > "$VPS_DATA_DIR/vpsdb.json"
fi

if [ ! -f "$VPS_DATA_DIR/lastUpdated.json" ]; then
    echo '0' > "$VPS_DATA_DIR/lastUpdated.json"
fi