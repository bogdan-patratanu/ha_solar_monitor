#!/usr/bin/env python3
"""
Test JK BMS driver with direct serial connection
"""
import sys
import json
import os

# Add parent directory to path to import drivers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from drivers.jk_bms_driver import JKBMSDriver

# Configuration
serial_port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
device_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

print(f"Testing JK BMS on {serial_port}, device_id={device_id}\n")

# Create driver with direct serial connection
driver = JKBMSDriver(
    serial_port=serial_port,
    baudrate=9600,
    device_id=device_id,
    timeout=3.0
)

# Connect
if not driver.connect():
    print("❌ Failed to connect to BMS")
    sys.exit(1)

print(f"✓ Connected via {driver.mode}\n")

try:
    # Test 1: Read live data
    print("="*80)
    print("TEST 1: Reading live data...")
    print("="*80)
    
    live_data = driver.read_live_data()
    
    if live_data:
        print("✓ Live data received!\n")
        
        # Display key values
        print("Key Values:")
        print("-" * 80)
        
        if 'total_voltage' in live_data:
            print(f"Total Voltage:        {live_data['total_voltage']:.2f} V")
        if 'total_current' in live_data:
            print(f"Total Current:        {live_data['total_current']:.2f} A")
        if 'total_power' in live_data:
            print(f"Total Power:          {live_data['total_power']:.2f} W")
        if 'soc' in live_data:
            print(f"State of Charge:      {live_data['soc']} %")
        if 'soh' in live_data:
            print(f"State of Health:      {live_data['soh']} %")
        if 'remaining_capacity' in live_data:
            print(f"Remaining Capacity:   {live_data['remaining_capacity']:.2f} Ah")
        if 'battery_capacity' in live_data:
            print(f"Battery Capacity:     {live_data['battery_capacity']:.2f} Ah")
        if 'cycle_count' in live_data:
            print(f"Cycle Count:          {live_data['cycle_count']}")
        
        print()
        
        # Cell voltages
        cell_voltages = {k: v for k, v in live_data.items() if k.startswith('cell_') and k.endswith('_voltage')}
        if cell_voltages:
            print("Cell Voltages:")
            print("-" * 80)
            for i in range(1, 17):
                key = f'cell_{i}_voltage'
                if key in cell_voltages:
                    print(f"  Cell {i:2d}: {cell_voltages[key]:.3f} V")
            print()
            
            if 'cell_voltage_max' in live_data:
                print(f"  Max:   {live_data['cell_voltage_max']:.3f} V")
            if 'cell_voltage_min' in live_data:
                print(f"  Min:   {live_data['cell_voltage_min']:.3f} V")
            if 'cell_voltage_delta' in live_data:
                print(f"  Delta: {live_data['cell_voltage_delta']:.3f} V")
            print()
        
        # Temperatures
        temps = {k: v for k, v in live_data.items() if 'temp' in k}
        if temps:
            print("Temperatures:")
            print("-" * 80)
            for key, value in temps.items():
                print(f"  {key}: {value:.1f} °C")
            print()
        
        # Full data dump
        print("\n" + "="*80)
        print("FULL DATA (JSON):")
        print("="*80)
        print(json.dumps(live_data, indent=2))
        
    else:
        print("❌ No live data received")
    
    print("\n" + "="*80)
    print("TEST 2: Reading setup data...")
    print("="*80)
    
    setup_data = driver.read_setup_data()
    
    if setup_data:
        print("✓ Setup data received!\n")
        print(json.dumps(setup_data, indent=2))
    else:
        print("❌ No setup data received")
    
    print("\n" + "="*80)
    print("TEST 3: Reading alarms...")
    print("="*80)
    
    alarms = driver.read_alarms()
    
    if alarms is not None:
        print(f"✓ Alarm register: 0x{alarms:08X} ({alarms})")
        if alarms == 0:
            print("  No alarms active")
        else:
            print("  ⚠ Alarms detected!")
    else:
        print("❌ No alarm data received")
    
finally:
    driver.disconnect()
    print("\n✓ Disconnected")
