# Custom Inverter Templates

This folder is for user-defined custom inverter templates. Use this when your inverter is not supported by the built-in templates or when you need to customize register mappings.

## Structure

```
custom/
├── common/
│   ├── battery.yaml       # Custom battery sensors
│   ├── pv.yaml            # Custom PV sensors
│   ├── grid_1p.yaml       # Custom single-phase grid sensors
│   ├── grid_3p.yaml       # Custom three-phase grid sensors
│   ├── load_1p.yaml       # Custom single-phase load sensors
│   ├── load_3p.yaml       # Custom three-phase load sensors
│   └── inverter.yaml      # Custom inverter sensors
├── EXAMPLE.yaml           # Example custom template
└── README.md
```

## Creating a Custom Template

### Step 1: Identify Your Inverter Model

Determine:
- Manufacturer name
- Model code (e.g., SG0XLP1, or create your own)
- Number of phases (1 or 3)
- Voltage type (LV or HV)

### Step 2: Find Register Addresses

You need to know the Modbus register addresses for your inverter. Sources:
- Manufacturer's Modbus register documentation
- Community forums (e.g., Home Assistant, GitHub)
- Modbus scanner tools
- Similar inverter models

### Step 3: Create Common Sensor Packages

Create sensor definition files in `custom/common/`:

**Example: custom/common/battery.yaml**
```yaml
# Custom battery sensors
sensors:
  battery_voltage:
    address: 183        # Your inverter's register address
    name: "Battery Voltage"
    unit: "V"
    factor: 0.01        # Scaling factor (raw value * factor = actual value)
    icon: "mdi:battery"
    device_class: "voltage"
    state_class: "measurement"
  
  battery_soc:
    address: 184
    name: "Battery SOC"
    unit: "%"
    factor: 1
    icon: "mdi:battery"
    device_class: "battery"
    state_class: "measurement"
```

### Step 4: Create Model Template

Create a template file in `custom/` folder:

**Example: custom/MY_INVERTER.yaml**
```yaml
metadata:
  manufacturer: "CustomBrand"
  model: "MY_INVERTER"
  description: "My custom inverter model"
  phases: 1
  mode: "single"
  voltage: "LV"
  supported_models:
    - "CustomBrand Model X"

communication:
  default_port: 8899
  default_modbus_id: 1
  default_timeout: 10
  default_batch_size: 60
  driver: "pymodbus"

registers:
  start_address: 0
  count: 250

# Include your custom common packages
includes:
  - custom/common/battery.yaml
  - custom/common/pv.yaml
  - custom/common/grid_1p.yaml
  - custom/common/load_1p.yaml
  - custom/common/inverter.yaml

# Or define sensors directly here
sensors: {}

```

### Step 5: Use Your Custom Template

In your add-on configuration:

```yaml
inverters:
  - name: "My Custom Inverter"
    host: "192.168.1.100"
    manufacturer: "custom"
    model: "MY_INVERTER"
    sensor_group: "essential"
```

## Tips

### Scaling Factors

- **Positive factor**: Unsigned value
  - `factor: 0.1` → Register 235 becomes 23.5
  - `factor: 0.01` → Register 5000 becomes 50.00
  
- **Negative factor**: Signed 16-bit value
  - `factor: -1` → Register 65535 becomes -1
  - `factor: -0.1` → Treats as signed, then multiplies by 0.1

### 32-bit Values

For values spanning two registers:

```yaml
total_energy:
  address: [96, 97]      # Two consecutive registers
  name: "Total Energy"
  unit: "kWh"
  factor: 0.1
  icon: "mdi:counter"
  device_class: "energy"
  state_class: "total_increasing"
  is_32bit: true
```

### Testing

1. Start with a minimal sensor set (e.g., just battery_soc)
2. Enable debug logging: `debug: 2`
3. Check logs for register values
4. Verify scaling factors produce correct values
5. Add more sensors incrementally

### Copying from Existing Templates

You can copy and modify existing templates:

```bash
# Copy Deye common packages as starting point
cp templates/deye/common/*.yaml templates/custom/common/

# Copy a model template
cp templates/deye/SG0XLP1.yaml templates/custom/MY_INVERTER.yaml
```

Then modify register addresses and scaling factors for your inverter.

## Sharing Your Template

If you create a working template for a new inverter model, consider:
1. Testing thoroughly with your inverter
2. Documenting supported models
3. Contributing back to the project via GitHub pull request

This helps other users with the same inverter!

## Troubleshooting

**Template not found:**
- Check file name matches model code (case-sensitive)
- Verify file is in `templates/custom/` folder

**Wrong sensor values:**
- Check register addresses in manufacturer documentation
- Verify scaling factor (factor field)
- Enable debug logging to see raw register values

**Register read errors:**
- Verify start_address and count cover all sensor addresses
- Try reducing read_sensors_batch_size
- Check Modbus ID matches inverter settings
