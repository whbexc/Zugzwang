#!/bin/bash
# ZUGZWANG - Lightpanda Setup Script for WSL2

echo "--- Installing Lightpanda (Nightly Build) ---"

# 1. Download the binary
curl -L -o lightpanda https://github.com/lightpanda-io/browser/releases/download/nightly/lightpanda-x86_64-linux

# 2. Make it executable
chmod a+x ./lightpanda

# 3. Move to local bin
sudo mv lightpanda /usr/local/bin/

echo "--- Installation Complete ---"
echo "To start the server, run:"
echo "lightpanda serve --host 0.0.0.0 --port 9222"
