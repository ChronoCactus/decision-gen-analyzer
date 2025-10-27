#!/bin/bash

# Script to discover the host IP address for LAN discovery
# This helps users configure the HOST_IP environment variable

echo "🔍 Discovering host IP addresses..."
echo ""

# Try different methods based on OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "📱 macOS detected"
    echo ""
    echo "Available network interfaces:"
    ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "  - " $2}'
    echo ""
    echo "💡 Recommended: Use your WiFi or Ethernet IP (usually starts with 192.168 or 10.0)"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Linux detected"
    echo ""
    echo "Available network interfaces:"
    hostname -I | tr ' ' '\n' | grep -v '^$' | awk '{print "  - " $1}'
    echo ""
    echo "💡 Recommended: Use your primary network IP (usually starts with 192.168 or 10.0)"
    
else
    # Windows or other
    echo "🖥️  Please manually check your IP address:"
    echo "  - Windows: Run 'ipconfig' in Command Prompt"
    echo "  - Other: Check your network settings"
fi

echo ""
echo "📋 To enable LAN discovery, add these to your .env file:"
echo "   ENABLE_LAN_DISCOVERY=true"
echo "   HOST_IP=<your-ip-address>"
echo ""
echo "Example:"
echo "   ENABLE_LAN_DISCOVERY=true"
echo "   HOST_IP=192.168.0.53"
