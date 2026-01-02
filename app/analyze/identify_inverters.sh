#!/bin/bash
# Script to identify which USB port corresponds to which inverter

echo "=========================================="
echo "INVERTER PORT IDENTIFICATION"
echo "=========================================="
echo ""

echo "Scanning /dev/ttyUSB0..."
echo "----------------------------------------"
python3 scan_rtu.py /dev/ttyUSB0 --baudrate 9600 --unit 1 --timeout 2.0
echo ""
echo ""

echo "Scanning /dev/ttyUSB1..."
echo "----------------------------------------"
python3 scan_rtu.py /dev/ttyUSB1 --baudrate 9600 --unit 1 --timeout 2.0
echo ""
echo ""

echo "=========================================="
echo "SCAN COMPLETE"
echo "=========================================="
echo ""
echo "Compare the register values above to identify each inverter."
echo "Look for differences in:"
echo "  - Serial numbers (often in registers 0-10)"
echo "  - Model information"
echo "  - Current power output"
echo "  - Any other identifying values"
