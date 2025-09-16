# NVIDIA GPU Throttle Monitor

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/voipmonitor/nvmonitor)
[![Python](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A real-time monitoring tool for NVIDIA GPU throttling and performance issues. This tool provides instant visibility into power limits, thermal throttling, and other performance bottlenecks affecting your GPUs.

## Features

- **Real-time Monitoring** - Live updates of GPU status with configurable sampling interval
- **Multiple GPU Support** - Monitor all GPUs or select specific ones
- **Throttle Detection** - Identifies and explains all types of throttling:
  - Power brake (hardware power limits)
  - Thermal throttling (overheating protection)
  - Software power caps
  - Driver thermal limits
- **Visual History Graph** - 40-sample rolling graph showing throttle events
- **Problem Descriptions** - Clear, actionable explanations of detected issues
- **CSV Logging** - Optional data export for analysis
- **Compact Mode** - Automatic adjustment for small terminals
- **Two Backends** - Uses PyNVML if available, falls back to nvidia-smi

## Requirements

- Linux system with NVIDIA driver installed
- Python 3.6 or later
- NVIDIA GPU with nvidia-smi support
- Optional: `pynvml` package for better performance

## Installation

### Method 1: Install from GitHub using pip (Recommended)

```bash
# Install directly from GitHub
pip install git+https://github.com/voipmonitor/nvmonitor.git

# Or install with NVML support for better performance
pip install git+https://github.com/voipmonitor/nvmonitor.git#egg=nvmonitor[nvml]
```

### Method 2: Clone and Install Locally

```bash
# Clone the repository
git clone https://github.com/voipmonitor/nvmonitor.git
cd nvmonitor

# Install the package
pip install .

# Or install with NVML support
pip install .[nvml]
```

### Method 3: Run Without Installation

```bash
# Clone the repository
git clone https://github.com/voipmonitor/nvmonitor.git
cd nvmonitor

# Make the script executable
chmod +x nvmonitor.py

# Run directly
./nvmonitor.py
```

## Usage

### Basic Monitoring

After installation, you can run the tool from anywhere:

```bash
# Monitor all GPUs with default settings (1 second interval)
nvmonitor

# Monitor specific GPUs
nvmonitor --gpus 0,1

# Custom sampling interval (0.5 seconds)
nvmonitor --interval 0.5

# Run for specific duration (60 seconds)
nvmonitor --duration 60

# Save data to CSV file
nvmonitor --csv gpu_log.csv
```

### Understanding the Display

The monitor shows for each GPU:

1. **Power Draw** - Current power consumption in Watts
2. **SM Clock** - Streaming Multiprocessor clock speed in MHz
3. **Utilization** - GPU compute utilization percentage
4. **Temperature** - Current GPU temperature in Celsius
5. **History Graph** - Visual timeline of throttle events:
   - `·` = Normal operation
   - `█` (red) = Throttling detected
6. **Status Line** - Detailed problem description when issues occur

### Problem Types and Solutions

| Problem | Description | Solution |
|---------|-------------|----------|
| **POWER LIMIT** | GPU wants more power but is limited | Check PSU capacity, PCIe cables, increase power limit |
| **OVERHEATING** | Hardware thermal protection active | Improve cooling, check thermal paste |
| **HOT** | Driver thermal throttling | Improve airflow, reduce ambient temperature |
| **CAPPED** | Software power limit reached | Use `nvidia-smi -pl <watts>` to increase |
| **THROTTLED** | General hardware slowdown | Check for multiple concurrent issues |

## Command Line Options

```
--interval FLOAT    Sampling interval in seconds (default: 1.0)
--duration FLOAT    Run duration in seconds, 0 = infinite (default: 0)
--gpus STRING      Comma-separated GPU indices or "all" (default: all)
--csv PATH         Save monitoring data to CSV file
```

## CSV Output Format

When using `--csv`, the tool saves:
- Timestamp (ISO format with milliseconds)
- GPU index
- Power draw (W)
- SM clock (MHz)
- GPU utilization (%)
- Temperature (°C)
- Throttle mask (hexadecimal)
- Human-readable problem description

## Example Output

```
GPU Throttle Monitor │ Uptime: 45.2s │ NVML
────────────────────────────────────────────
GPU0: 250.3W │ 1890MHz │  98% │  75°C [HOT]
  History: ····················██████··········
  Status: POWER LIMIT: GPU wants more power but is limited by power delivery

GPU1: 180.5W │ 2100MHz │  87% │  62°C
  History: ········································
  Status: OK: No throttling
```

## Troubleshooting

### "Unable to query GPUs"
- Ensure NVIDIA driver is installed: `nvidia-smi`
- Check driver is loaded: `lsmod | grep nvidia`

### Missing temperature or power readings
- Some older GPUs don't support all metrics
- Virtual GPUs (vGPU) may have limited telemetry

### Inaccurate readings with nvidia-smi backend
- Install `pynvml` for more accurate data: `pip install pynvml`

## Technical Details

The tool monitors NVIDIA's clock event reason masks:
- `0x0080` - HW Power Brake Slowdown
- `0x0040` - HW Thermal Slowdown
- `0x0020` - SW Thermal Slowdown
- `0x0008` - HW Slowdown
- `0x0004` - SW Power Cap

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Author

Created for monitoring GPU performance in high-load environments where throttling can impact workload performance.