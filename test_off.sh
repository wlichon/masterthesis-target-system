#!/bin/bash
echo "Restoring Linux Mint to default settings..."

# Restart Update Timers
sudo systemctl start apt-daily.timer apt-daily-upgrade.timer 2>/dev/null
sudo systemctl start mintupdate-automation-upgrade.timer 2>/dev/null

# Restart Housekeeping
sudo systemctl start plocate-updatedb.timer cron 2>/dev/null

# Reset CPU to balanced/powersave mode
if command -v cpupower &> /dev/null; then
    sudo cpupower frequency-set -g powersave
    echo "CPU set back to Powersave/Balanced mode."
else
    echo "Warning: cpupower not found. Could not reset CPU governor."
fi

echo "System restored to default environment."