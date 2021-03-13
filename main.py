#!/usr/bin/env python3

import subprocess
import os
import re
import threading
import time


from flask import Flask, request, render_template
from flask_socketio import SocketIO
from flask_mqtt import Mqtt

import schedule
import sqlite3
from icmplib import ping
import netifaces
import yaml


class ArpScan:
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
    def __init__(self, interface, finishedscan_callback=lambda n: None):
        self.finishedscan_callback = finishedscan_callback
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

    def startscan(self):
        print('startscan')
        arp_scan = ArpScan(self.interface)

        cur = self.db.cursor()
        hosts = {}
        newDevices = []
        changedtoOnline = []
        changedtoOffline = []
        for host in arp_scan.hosts:
            cur.execute(f"SELECT * FROM devices where mac='{host['mac']}';")
            row = cur.fetchone()
            if row is None:
                cur.execute(f"""INSERT INTO devices (mac, ip, vendor, hostname)
                 VALUES ('{host['mac']}', '{host['ip']}', '{host['vendor']}', '{host['hostname']}');""")
                self.db.commit()
                newDevices.append(host)
            else:
                dev_dict = dict(zip(row.keys(), list(row)))
                if not dev_dict['active']:
                    changedtoOnline.append(host['mac'])
                if dev_dict['ip'] != host['ip']:
                    cur.execute(
                        f"""UPDATE devices SET ip='{host['ip']}' WHERE mac='{host['mac']}';""")
                    self.db.commit()
                if dev_dict['hostname'] != host['hostname']:
                    cur.execute(
                        f"""UPDATE devices SET hostname='{host['hostname']}' WHERE mac='{host['mac']}';""")
                    self.db.commit()

            hosts[host['mac']] = {
                'ip': host['ip'],
                'vendor': host['vendor'],
                'hostname': host['hostname']
            }
        macs_query = ', '.join(f'"{w}"' for w in hosts.keys())
        cur.execute(
            f"SELECT mac, ip FROM devices where mac not in ({macs_query});")
        results = cur.fetchall()
        for result in results:
            host = ping(result[0], count=3, interval=0.2)
            if not host.is_alive:
                changedtoOffline.append(result[0])
        if len(changedtoOffline) > 0:
            update_macs_query = ', '.join(f'"{w}"' for w in changedtoOffline)
            cur.execute(
                f"UPDATE devices SET active=0 WHERE mac in ({update_macs_query});")
            self.db.commit()
        if len(changedtoOnline) > 0:
            update_macs_query = ', '.join(f'"{w}"' for w in changedtoOnline)
            cur.execute(
                f"UPDATE devices SET active=1 WHERE mac in ({update_macs_query});")
            self.db.commit()

        self.finishedscan_callback(hosts, changedtoOnline, changedtoOffline, newDevices)
        return hosts


def ReadConfig():
    with open('config.yaml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config


def endscan(hosts, changedtoOnline, changedtoOffline, newDevices):
    socketio.emit('endscan', hosts)
    print('newDevices:', newDevices)
    for newDevice in newDevices:
        message = f"""New device found {newDevice['ip']} ({newDevice['hostname']}). Device specific: {newDevice['mac']} ({newDevice['vendor']})"""
        mqtt.publish(config['mqtt']['topic'], message)


def run_scan_forever():
    netscan.startscan()
    schedule.every(config['scaninterval']).seconds.do(netscan.startscan)
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_trheading():
    thread = threading.Thread(target=run_scan_forever)
    thread.daemon = True
    thread.start()


config = ReadConfig()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(42)
app.config['MQTT_BROKER_URL'] = config['mqtt']['host']
app.config['MQTT_BROKER_PORT'] = config['mqtt']['port']
app.config['MQTT_USERNAME'] = config['mqtt']['user']
app.config['MQTT_PASSWORD'] = config['mqtt']['pass']
app.config['MQTT_REFRESH_TIME'] = 1.0  # refresh time in seconds
mqtt = Mqtt(app)

socketio = SocketIO(app)
netscan = NetworkScan(config['network'], endscan)


@app.route('/update_device', methods=['POST', 'GET'])
def update_device():
    update_query = f"""UPDATE devices SET
            icon='{ request.form['icon'] }',
            brand='{ request.form['brand'] }',
            devicetype='{ request.form['devicetype'] }',
            model='{ request.form['model'] }',
            name='{ request.form['name'] }',
            is_recognized={ request.form['is_recognized'] },
            notify_away={ request.form['notify_away'] }
        WHERE
            mac='{ request.form['mac'] }'
    """
    netscan.updatequery(update_query)
    return "done"

@app.route('/delete_device', methods=['POST', 'GET'])
def delete_device():
    delete_query = f"""DELETE FROM devices
        WHERE mac='{ request.form['mac'] }'
    """
    netscan.updatequery(delete_query)
    return "done"


@app.route('/scan')
def scan_network():
    hosts = netscan.startscan()
    return hosts


@app.route('/')
def index():
    devices = []
    rows = netscan.getquery("SELECT * FROM devices")
    for row in rows:
        dev_dict = dict(zip(row.keys(), list(row)))
        ip = dev_dict['ip']
        dev_dict['sortip'] = ''.join(i.zfill(3) for i in ip.split('.'))
        dev_dict['statecolor'] = 'green' if dev_dict['active'] else 'red'
        dev_dict['recognizedcolor'] = 'white' if dev_dict['is_recognized'] else 'cyan'
        dev_dict['details'] = dev_dict['vendor']
        if dev_dict['name'] != "":
            dev_dict['details'] = dev_dict['name']
        elif dev_dict['brand'] != "":
            dev_dict['details'] = dev_dict['brand']
            if dev_dict['model'] != "":
                dev_dict['details'] += " " + dev_dict['model']
        dev_dict['device'] = dev_dict['hostname']
        if dev_dict['devicetype'] != "":
            dev_dict['device'] = dev_dict['devicetype']
        devices.append(dev_dict)
    return render_template('index.html', devices=devices)


if __name__ == '__main__':
    if config['scaninterval'] > 0:
        start_trheading()
    socketio.run(app, host='0.0.0.0', port=config['appport'], debug=config['debug'])
