#!/bin/bash
echo "Establishing Deterministic AMD Environment for Master's Thesis..."

# Stop Update Timers & Background Maintenance
# Prevents CPU spikes from apt or file indexing
sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer 2>/dev/null
sudo systemctl stop mintupdate-automation-upgrade.timer 2>/dev/null
sudo systemctl stop plocate-updatedb.timer cron.service 2>/dev/null
sudo systemctl stop irqbalance.service 2>/dev/null # Prevent moving IRQs between cores during test

# Network & Kernel Configuration
sudo modprobe br_netfilter
sudo sysctl -w kernel.nmi_watchdog=0        # Disable watchdog interrupts
sudo sysctl -w vm.stat_interval=60          # Reduce VM statistics collection frequency
sudo sysctl -w kernel.randomize_va_space=0  # Disable ASLR for deterministic memory access

# AMD CPU Optimization
# Disable Core Performance Boost
# prevents frequency fluctuations due to heat during DoS attacks
if [ -f /sys/devices/system/cpu/cpufreq/boost ]; then
    echo "Disabling AMD Core Performance Boost..."
    echo 0 | sudo tee /sys/devices/system/cpu/cpufreq/boost
fi

# Set Governor to Performance
if command -v cpupower &> /dev/null; then
    sudo cpupower frequency-set -g performance
else
    echo "Warning: cpupower not found. Attempting manual governor set..."
    echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
fi

# Memory Preparation
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches