# MQTT Network Scanner
Presence detection for your whole Network.
Helps to keep an eye for new devices through an interactive web interface.


# Features
  * Scans at a configurable interval or manually.
  * Highlights the new unrecognized devices.
  * Custom fields for personalise each device.
  * Custom icons through [Google Fonts](https://fonts.google.com/icons).
  * [TBD] Will send notifications on MQTT and Mail.


# Tech details
Sends ARP requests to get the IP and MAC of each device through the `arp-scan` command and for each offline device, it checks if it is actually offline with ICMP (ping). There were more pythonic ways to run the arp scan like the `scapy`, but the results on Linux were not so accurate.

Every ARP scan needs root permitions because it is using a promiscuous mode to monitor the network and create custom packages, so you need sudo to run this app.

# Installation
The installation process is still on development, but the basic installation is as follows:
```bash
git clone git@github.com:bkbilly/mqtt-network-scanner.git /opt/mqtt-network-scanner
cd /opt/mqtt-network-scanner
vi config.yaml

sudo pip install -r requirements.txt
sudo cp networkscanner.service /etc/systemd/system/networkscanner.service
sudo systemctl enable networkscanner.service
sudo systemctl start networkscanner.service
```

# Inspiration
I wanted a tool like `fing` which could scan my network, but it doesn't support linux systems and I couldn't find any other easy to use alternatives.
