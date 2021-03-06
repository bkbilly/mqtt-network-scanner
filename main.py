import subprocess
import os
import re
import threading

import schedule
import time

from flask import Flask, request, render_template, g
from flask_socketio import SocketIO
import sqlite3

from icmplib import ping
import netifaces


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
    def __init__(self):
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
        arp_scan = ArpScan("enp3s0")

        cur = self.db.cursor()
        hosts = {}
        newMacs = []
        changedtoOnline = []
        changedtoOffline = []
        for host in arp_scan.hosts:
            cur.execute(f"SELECT * FROM devices where mac='{host['mac']}';")
            row = cur.fetchone()
            if row is None:
                cur.execute(f"""INSERT INTO devices (mac, ip, vendor, hostname)
                 VALUES ('{host['mac']}', '{host['ip']}', '{host['vendor']}', '{host['hostname']}');""")
                self.db.commit()
                newMacs.append(host['mac'])
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

        print('endscan')
        return hosts


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(42)
socketio = SocketIO(app)


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
        dev_dict['device'] = dev_dict['vendor']
        if dev_dict['name'] != "":
            dev_dict['device'] = dev_dict['name']
        elif dev_dict['brand'] != "":
            dev_dict['device'] = dev_dict['brand']
            if dev_dict['model'] != "":
                dev_dict['device'] += " " + dev_dict['model']
        devices.append(dev_dict)
    return render_template('index.html', devices=devices)


def run_scan_forever():
    netscan.startscan()
    schedule.every(120).seconds.do(netscan.startscan)
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_trheading():
    thread = threading.Thread(target=run_scan_forever)
    thread.daemon = True
    thread.start()


if __name__ == '__main__':
    netscan = NetworkScan()
    start_trheading()
    socketio.run(app, host='0.0.0.0', debug=True)
