# Solar Monitor - Home Assistant Add-on

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fbogdan-patratanu%2Fha_solar_monitor)

Monitor solar inverters and JK BMS batteries and publish their data as sensors in Home Assistant via MQTT discovery.

---

## Supported Hardware

### Inverters

| Profile | Models |
|---|---|
| `Deye_SG03LP1` | SUN-3K/5K/6K/8K-SG03LP1-EU (single phase, LV) |
| `Deye_SG04LP3` | SUN-8K/10K/12K-SG04LP3-EU (three phase, LV) |

### Batteries

| Profile | Description |
|---|---|
| `JK_BMS_BROADCAST` | JK BMS in RS485 broadcast mode via USB serial adapter (JK-B2A24S, JK-B1A24S, JK-B2A20S) |

### Drivers

| Driver | Use case |
|---|---|
| `modbusTCP` | Inverter connected via LAN/Wi-Fi (most common) |
| `modbusRTU` | Inverter connected via RS485-to-USB adapter |
| `rawTCPRTU` | Modbus RTU framing tunnelled over a TCP socket |
| `jkBMS` | JK BMS in broadcast mode over USB serial |

---

## Installation

1. Click the badge above to add the repository to your Home Assistant, or go to **Settings → Add-ons → Add-on Store → ⋮ → Repositories** and add:
   ```
   https://github.com/bogdan-patratanu/ha_solar_monitor
   ```
2. Find **Solar Monitor** in the store and click **Install**.
3. Configure the add-on (see below).
4. Start the add-on.

---

## Configuration

All configuration is done through the add-on's **Configuration** tab in Home Assistant.

### Full configuration reference

```yaml
# One or more inverters (optional if you only have batteries)
inverters:
  - name: string           # Friendly name (used in logs)
    profile: string        # Hardware profile (see Supported Hardware)
    driver: string         # Connection driver
    ha_prefix: string      # Prefix for all HA entity IDs, e.g. "deye_"
    path: string           # IP:port for TCP drivers, device path for RTU
    modbus_id: int         # Modbus slave ID (1-16)

# One or more BMS batteries (optional)
batteries:
  - name: string           # Friendly name (used in logs)
    profile: string        # Hardware profile
    driver: string         # Connection driver
    ha_prefix: string      # Prefix for all HA entity IDs, e.g. "jk_master_"
    path: string           # Serial device path, e.g. /dev/ttyUSB0
    modbus_id: int         # BMS ID on the RS485 bus (1-16)

# MQTT broker settings
mqtt:
  host: string             # Broker hostname or IP (use "core-mosquitto" for the HA Mosquitto add-on)
  port: int                # Broker port (default: 1883)
  username: string         # MQTT username
  password: string         # MQTT password
  discovery_prefix: string # HA discovery prefix (default: "homeassistant")

# Optional
debug: bool                # Extra debug output (default: false)
log_level: string          # CRITICAL | ERROR | WARNING | INFO | DEBUG (default: INFO)
```

---

## Examples

### Inverter only — TCP (most common)

```yaml
inverters:
  - name: Deye
    profile: Deye_SG04LP3
    driver: modbusTCP
    ha_prefix: deye_
    path: 192.168.1.10:502
    modbus_id: 1
mqtt:
  host: core-mosquitto
  port: 1883
  username: mqtt_user
  password: mqtt_password
  discovery_prefix: homeassistant
```

`path` is the inverter's IP address and Modbus port. Most Deye inverters use port `502`.

---

### Inverter + single JK BMS

```yaml
inverters:
  - name: Deye
    profile: Deye_SG04LP3
    driver: modbusTCP
    ha_prefix: deye_
    path: 192.168.1.10:502
    modbus_id: 1
batteries:
  - name: bmsMaster
    profile: JK_BMS_BROADCAST
    driver: jkBMS
    ha_prefix: jk_
    path: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_XXXXXXXX-if00-port0
    modbus_id: 1
mqtt:
  host: core-mosquitto
  port: 1883
  username: mqtt_user
  password: mqtt_password
  discovery_prefix: homeassistant
```

---

### Inverter + two JK BMS units on the same RS485 bus

When multiple BMS units share one USB adapter (RS485 bus), use the **same `path`** for both and assign a different `modbus_id` to each:

```yaml
inverters:
  - name: Deye
    profile: Deye_SG04LP3
    driver: modbusTCP
    ha_prefix: deye_
    path: 192.168.1.10:502
    modbus_id: 1
batteries:
  - name: bmsMaster
    profile: JK_BMS_BROADCAST
    driver: jkBMS
    ha_prefix: jk_master_
    path: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_XXXXXXXX-if00-port0
    modbus_id: 1
  - name: bmsSlave
    profile: JK_BMS_BROADCAST
    driver: jkBMS
    ha_prefix: jk_slave_
    path: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_XXXXXXXX-if00-port0
    modbus_id: 2
mqtt:
  host: core-mosquitto
  port: 1883
  username: mqtt_user
  password: mqtt_password
  discovery_prefix: homeassistant
```

---

## Finding the Serial Device Path

When using a USB-to-RS485/serial adapter, use a **persistent path** (`/dev/serial/by-id/...`) instead of `/dev/ttyUSB0`, which can change after a reboot.

To find the persistent path, go to **Settings → System → Hardware** in Home Assistant, or run in the HA terminal:

```bash
ls /dev/serial/by-id/
```

Use the full path shown, for example:
```
/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A5069RR4-if00-port0
```

---

## MQTT Discovery

Entities are registered automatically via MQTT discovery. After the add-on starts, sensors will appear in Home Assistant under **Settings → Devices & Services → MQTT**.

The entity ID format is: `sensor.<ha_prefix><sensor_name>`

Example with `ha_prefix: deye_`:
- `sensor.deye_battery_soc`
- `sensor.deye_pv1_power`
- `sensor.deye_grid_frequency`

---

## Troubleshooting

### Permission denied on serial device

If you see `Permission denied for /dev/serial/...` in the logs, the add-on does not have access to the serial port. This can happen after a Home Assistant update.

**Fix:** Reinstall the add-on. The manifest declares `uart: true` which grants serial device access — a reinstall ensures HA applies the latest permissions.

### No data received

- Verify the `path` (IP:port or device path) is correct.
- Check that `modbus_id` matches the setting on the inverter/BMS.
- For TCP: confirm the inverter is reachable from HA (`ping <inverter IP>`).
- For serial: confirm the device path exists and the adapter is plugged in.
- Set `log_level: DEBUG` for more detail.

### Entities not appearing in Home Assistant

- Confirm the Mosquitto (or other) MQTT broker is running.
- Check that `mqtt.host`, `mqtt.username`, and `mqtt.password` are correct.
- Verify `discovery_prefix` matches your HA MQTT integration setting (default: `homeassistant`).

### Wrong sensor values

- Double-check `modbus_id` — a mismatch causes data from the wrong device to be read.
- Check that the correct `profile` is selected for your hardware model.
