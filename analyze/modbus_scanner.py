#!/usr/bin/env python3
"""Pymodbus Synchronous Client Example.

An example of a single threaded synchronous client.

usage::

    client_sync.py [-h] [-c {tcp,udp,serial,tls}]
                    [-f {ascii,rtu,socket,tls}]
                    [-l {critical,error,warning,info,debug}] [-p PORT]
                    [--baudrate BAUDRATE] [--host HOST]

    -h, --help
        show this help message and exit
    -c, --comm {tcp,udp,serial,tls}
        set communication, default is tcp
    -f, --framer {ascii,rtu,socket,tls}
        set framer, default depends on --comm
    -l, --log {critical,error,warning,info,debug}
        set log level, default is info
    -p, --port PORT
        set port
    --baudrate BAUDRATE
        set serial device baud rate
    --host HOST
        set host, default is 127.0.0.1

The corresponding server must be started before e.g. as:

    python3 server_sync.py

"""
from __future__ import annotations

import logging
import sys


import pymodbus.client as modbusClient
from pymodbus import ModbusException


_logger = logging.getLogger(__file__)
_logger.setLevel("DEBUG")


def setup_sync_client(description=None, cmdline='serial'):
    _logger.info("### Create client object")
    client = modbusClient.ModbusSerialClient(
            port='/dev/ttyUSB1',  # serial port
            # Common optional parameters:
            framer='rtu',
            timeout=1,
            #    retries=3,
            # Serial setup parameters
            baudrate=9600,
            bytesize=8,
            parity="N",
            stopbits=1
            #    handle_local_echo=False,
        )
    return client


def run_sync_client(client, modbus_calls=None):
    """Run sync client."""
    _logger.info("### Client starting")
    client.connect()
    if modbus_calls:  # pragma: no cover
        modbus_calls(client)
    client.close()
    _logger.info("### End of Program")


def run_a_few_calls(client):
    """Test connection works."""
    try:
        rr = client.read_coils(32, count=1, device_id=1)
        assert len(rr.bits) == 8
        rr = client.read_holding_registers(4, count=2, device_id=1)
        assert rr.registers[0] == 17
        assert rr.registers[1] == 17
    except ModbusException as exc:
        raise exc

def main(cmdline=None):
    """Combine setup and run."""
    testclient = setup_sync_client(
        description="Run synchronous client.", cmdline=cmdline
    )
    run_sync_client(testclient, modbus_calls=run_a_few_calls)


if __name__ == "__main__":
    main()