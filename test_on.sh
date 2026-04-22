#!/bin/bash
echo "Optimizing Linux Mint for Master Thesis testing..."

# Stop Update Timers
sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null
sudo systemctl stop mintupdate-automation-upgrade.timer 2>/dev/null

# Stop Housekeeping
sudo systemctl stop plocate-updatedb.timer cron 2>/dev/null

# Set Performance mode (Ensure you ran the apt install linux-tools command first!)
if command -v cpupower &> /dev/null; then
    sudo cpupower frequency-set -g performance
else
    echo "Warning: cpupower not found. CPU scaling may still occur."
fi

echo "Baseline environment ready."