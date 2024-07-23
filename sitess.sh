#!/bin/bash

# List of websites to block
BLOCKED_SITES=(
    "www.example.com"
    "example.com"
)

# Get root privileges
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root."
    exit 1
fi

# Loop through blocked sites and add them to hosts file
for site in "${BLOCKED_SITES[@]}"; do
    if grep -q $site /etc/hosts; then
        echo "$site is already blocked."
    else
        echo "Blocking $site..."
        echo "127.0.0.1 $site" >> /etc/hosts
    fi
done

echo "All sites have been blocked."