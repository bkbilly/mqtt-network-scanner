#!/usr/bin/env python3

import subprocess
import re
import time

from multiprocessing import Pool
import sqlite3
from icmplib import multiping
import netifaces


class ArpScan:
    """ Scans for devices in the network using system command arp-scan """

    def __init__(self, interface):
        self.hosts = []
        if interface not in netifaces.interfaces():
            print("Can't find network interface")
            return

        output = subprocess.check_output(
            f"arp-scan -I {interface} -l -gx",
            shell=True)

        for host_str in output.decode().splitlines():
            host_list = host_str.split('\t')
            if host_list[2] == '(Unknown)':
                host_list[2] = None
            host_list[1] = host_list[1].upper()
            host_dict = dict(zip(['ip', 'mac', 'vendor'], host_list))
            host_dict['hostname'] = self.get_hostname(host_dict['ip'])
            self.hosts.append(host_dict)

    def get_hostname(self, ip):
        output = subprocess.check_output(
            f"arp -a {ip}",
            shell=True)
        arp_out = str(output.decode('ascii'))

        hostname = None
        p = re.compile(r'^[\w-]+')
        find_hostname = re.findall(p, arp_out)
        if len(find_hostname) > 0:
            hostname = find_hostname[0]
        return hostname


class NetworkScan():
    def __init__(self, interface, endscan_callback=lambda n: None):
        self.endscan_callback = endscan_callback
        self.interface = interface
        DATABASE = 'database.db'
        self.db = sqlite3.connect(DATABASE, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with open('schema.sql', mode='r') as f:
            self.db.cursor().executescript(f.read())
        self.db.commit()

    def getquery(self, query):
        cur = self.db.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        return rows

    def updatequery(self, update_query):
        cur = self.db.cursor()
        cur.execute(update_query)
        self.db.commit()

    def changedstate(self, host, state):
        cur = self.db.cursor()
        if state == 'new':
            cur.execute(f"""INSERT INTO devices (mac, ip, vendor, hostname)
             VALUES ('{host['mac']}', '{host['ip']}', '{host['vendor']}', '{host['hostname']}');""")
        elif state == 'online':
            cur.execute(f"""UPDATE devices SET 
                active=1, last_changed=CURRENT_TIMESTAMP
                WHERE mac='{host['mac']}';""")
        elif state == 'offline':
            cur.execute(f"""UPDATE devices SET
                active=0, last_changed=CURRENT_TIMESTAMP
                WHERE mac='{host['mac']}';""")
        elif state == 'ip':
            cur.execute(f"""UPDATE devices SET ip='{host['ip']}' WHERE mac='{host['mac']}';""")
        elif state == 'hostname':
            cur.execute(f"""UPDATE devices SET hostname='{host['hostname']}' WHERE mac='{host['mac']}';""")
        self.db.commit()

    def startscan(self):
        print('startscan')
        time_arp_start = time.time()

        # Check devices with arp scan
        arp_scan = ArpScan(self.interface)
        time_arp = time_arp_start - time.time()

        time_sql_start = time.time()
        cur = self.db.cursor()
        hosts = {}
        newDevices = []
        changedtoOnline = []
        changedtoOffline = []

        # Check for newly changed devices
        for host in arp_scan.hosts:
            print(host)
            cur.execute(f"SELECT * FROM devices where mac='{host['mac']}';")
            row = cur.fetchone()
            if row is None:
                newDevices.append(host)
                self.changedstate(host, 'new')
            else:
                dev_dict = dict(zip(row.keys(), list(row)))
                if not dev_dict['active']:
                    self.changedstate(host, 'online')
                    changedtoOnline.append(host)
                if dev_dict['ip'] != host['ip']:
                    self.changedstate(host, 'ip')
                if dev_dict['hostname'] != host['hostname']:
                    self.changedstate(host, 'hostname')

            hosts[host['mac']] = {
                'ip': host['ip'],
                'vendor': host['vendor'],
                'hostname': host['hostname']
            }

        # Check offline devices with ping scan
        macs_query = ', '.join(f'"{w}"' for w in hosts.keys())
        cur.execute(f"SELECT * FROM devices where mac not in ({macs_query});")
        results = cur.fetchall()
        pings_check = []
        devices = []
        for row in results:
            dev_dict = dict(zip(row.keys(), list(row)))
            pings_check.append(dev_dict['ip'])
            devices.append(dev_dict)
        time_sql = time_sql_start - time.time()

        print('start ping process')
        time_ping_start = time.time()
        ping_result = multiping(pings_check, count=2, interval=0.5, timeout=2)

        for num, host in enumerate(ping_result):
            # print(host, dev_dict)
            if not host.is_alive and devices[num]['active'] == 1:
                self.changedstate(devices[num], 'offline')
                changedtoOffline.append(devices[num])
        time_ping = time_ping_start - time.time()

        print(f"Timings: arp = {time_arp}, sql = {time_sql}, ping = {time_ping}")

        self.endscan_callback(hosts, changedtoOnline, changedtoOffline, newDevices)
        return hosts
