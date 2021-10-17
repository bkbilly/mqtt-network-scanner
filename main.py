#!/usr/bin/env python3

import os
import threading
import time


from flask import Flask, request, render_template
from flask_socketio import SocketIO
from flask_mqtt import Mqtt

import schedule
import yaml
import timeago
from datetime import datetime

from scanner import ArpScan, NetworkScan


def ReadConfig():
    with open('config.yaml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config


def endscan(hosts, changedtoOnline, changedtoOffline, newDevices):
    socketio.emit('endscan', hosts)
    print('newDevices:', newDevices)
    print('changedtoOnline:', changedtoOnline)
    print('changedtoOffline:', changedtoOffline)
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
            notify_away=False
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
        now = datetime.utcnow()
        date = datetime.strptime(dev_dict['last_changed'], '%Y-%m-%d %H:%M:%S')
        dev_dict['last_changed_hm'] = timeago.format(date, now)
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
