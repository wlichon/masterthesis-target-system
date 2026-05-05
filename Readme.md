# Description

This GitHub repository serves as a comprehensive archive of the artifacts used in my master's thesis, providing the necessary transparency for others to verify my results. By documenting the inner workings and technical details of my methodology, it functions as a resource for anyone seeking to validate my findings or understand the underlying processes of my research.

# Configuration and Setup

1. Start "configure_test_environment.sh"
2. sudo /bin/bash ./start.sh --mode lite --no-wifi
3. Launch Attacker System Webserver on a connected machine (https://github.com/wlichon/masterthesis-attacker-system)

# Testing Pipeline Execution

Either launch it directly with following command:

sudo python automation/test_pipeline.py --attack ATTACK_CATEGORY --attack-time X --idle Y

- ATTACK_CATEGORY can be either: empty_payload_flood, random_payload_flood, stx_header_flood, stress_test_random_payload_flood or stress_test_empty_payload_flood
- X and Y define the attack time and normal flight time in seconds respectively
- additional --no-reset flag can be provided to prevent the flight controller from resetting (saves time during DoS attack prototyping/testing)

OR

Launch multiple iterations of a selection of attack categories with the benchmarking script:

sudo python automation/run_benchmarks.py

the script's configuration can be adapted in the source code to accomodate specific testing parameters

# Logs

All the data generated from a pipeline iteration can be found in the logs folder, which has the pipeline's starting timestamp as its name

# eBPF Filter

Filters are provided in the ebpf folder and can be launched on any driver (thanks to generic XDP)

# Statistics

Any scripts which generate charts, plots and calculate statistics are also found in the automation folder. 

# Damn Vulnerable Drone

The Damn Vulnerable Drone is an intentionally vulnerable drone hacking simulator based on the popular ArduPilot/MAVLink architecture, providing a realistic environment for hands-on drone hacking. It served as the foundation for my master's thesis, thanks to its pre-configured realistic drone-environment simulation.

# Disclaimer

The Damn Vulnerable Drone (DVD) platform is provided solely for educational and research purposes. Users are expected to adhere to ethical hacking principles, respecting privacy and laws, and must not use skills or knowledge acquired from Damn Vulnerable Drone for malicious activities. The creators and maintainers of Damn Vulnerable Drone are not liable for any misuse of the platform. By using Damn Vulnerable Drone, you agree to use it responsibly and within legal boundaries. Damn Vulnerable Drone is highly insecure, and as such, should not be deployed on drone hardware or internet facing servers. It is intentionally flawed and vulnerable, as such, it comes with no warranties.

# License

It is distributed under the MIT License. See LICENSE for more information.

