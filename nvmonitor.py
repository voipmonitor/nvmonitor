#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPU Throttle Monitor - Real-time monitor for NVIDIA GPU throttle reasons
Shows all GPUs always, with clear problem descriptions
"""

import argparse
import collections
import datetime as dt
import os
import shutil
import signal
import subprocess
import sys
import time
from typing import Deque, Dict, List, Tuple

# ---------- Config & CLI ----------

def parse_args():
    p = argparse.ArgumentParser(
        description="Real-time monitor for NVIDIA GPU throttle/event reasons"
    )
    p.add_argument("--interval", type=float, default=1.0,
                   help="Sampling interval in seconds (default: 1.0)")
    p.add_argument("--duration", type=float, default=0.0,
                   help="Run for N seconds then exit (default: 0 = until Ctrl-C)")
    p.add_argument("--gpus", type=str, default="all",
                   help="Comma-separated GPU indices to watch (default: all)")
    p.add_argument("--csv", type=str, default="",
                   help="Optional path to save CSV log")
    return p.parse_args()

# ---------- ANSI Terminal Control ----------

class Terminal:
    """ANSI escape sequence handler for terminal control"""

    def __init__(self):
        self.color = sys.stdout.isatty() and os.environ.get("TERM", "") not in ("dumb", "")

        # Colors
        self.RESET = "\033[0m" if self.color else ""
        self.BOLD = "\033[1m" if self.color else ""
        self.DIM = "\033[2m" if self.color else ""
        self.RED = "\033[31m" if self.color else ""
        self.GREEN = "\033[32m" if self.color else ""
        self.YELLOW = "\033[33m" if self.color else ""
        self.CYAN = "\033[36m" if self.color else ""

        # Get terminal size
        self.update_size()

    def update_size(self):
        """Update terminal dimensions"""
        size = shutil.get_terminal_size((80, 24))
        self.width = size.columns
        self.height = size.lines

    def clear_screen(self):
        """Clear entire screen and move cursor to home"""
        sys.stdout.write("\033[2J\033[H")

    def hide_cursor(self):
        """Hide cursor"""
        sys.stdout.write("\033[?25l")

    def show_cursor(self):
        """Show cursor"""
        sys.stdout.write("\033[?25h")

# ---------- NVML Backend ----------

class Backend:
    """Abstracts data collection via NVML or nvidia-smi"""

    def __init__(self):
        self.use_nvml = False
        self.nvml = None
        self._init_backend()

    def _init_backend(self):
        try:
            import pynvml as nvml
            nvml.nvmlInit()
            self.nvml = nvml
            self.use_nvml = True
        except Exception:
            self.use_nvml = False
            self.nvml = None

    def device_count(self) -> int:
        if self.use_nvml:
            return self.nvml.nvmlDeviceGetCount()
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"], text=True
        ).strip().splitlines()
        return len(out)

    def name(self, idx: int) -> str:
        if self.use_nvml:
            h = self.nvml.nvmlDeviceGetHandleByIndex(idx)
            name = self.nvml.nvmlDeviceGetName(h)
            if isinstance(name, bytes):
                return name.decode("utf-8", "ignore")
            return name
        out = subprocess.check_output(
            ["nvidia-smi", f"--id={idx}", "--query-gpu=name", "--format=csv,noheader"], text=True
        )
        return out.strip()

    def sample(self, idx: int) -> Tuple[float, int, int, int, float]:
        """
        Returns: (power_watts, sm_clock_mhz, util_gpu_percent, reasons_mask, temp_c)
        """
        if self.use_nvml:
            nv = self.nvml
            h = nv.nvmlDeviceGetHandleByIndex(idx)

            # Power
            try:
                p_mw = nv.nvmlDeviceGetPowerUsage(h)
            except:
                p_mw = 0
            power_w = p_mw / 1000.0

            # Clocks and utilization
            sm = nv.nvmlDeviceGetClockInfo(h, nv.NVML_CLOCK_SM)
            util = nv.nvmlDeviceGetUtilizationRates(h).gpu

            # Temperature
            try:
                temp = nv.nvmlDeviceGetTemperature(h, nv.NVML_TEMPERATURE_GPU)
            except:
                temp = 0

            # Throttle reasons
            mask = 0
            try:
                mask = nv.nvmlDeviceGetCurrentClocksEventReasons(h)
            except:
                try:
                    mask = nv.nvmlDeviceGetCurrentClocksThrottleReasons(h)
                except:
                    mask = 0

            return (power_w, sm, util, int(mask), float(temp))

        # Fallback via nvidia-smi
        cmd = [
            "nvidia-smi", f"--id={idx}",
            "--query-gpu=power.draw,clocks.current.sm,utilization.gpu,clocks_throttle_reasons.active,temperature.gpu",
            "--format=csv,noheader,nounits"
        ]
        line = subprocess.check_output(cmd, text=True).strip()
        parts = [x.strip() for x in line.split(",")]
        power_w = float(parts[0]) if parts[0] else 0.0
        sm = int(parts[1]) if parts[1] else 0
        util = int(parts[2]) if parts[2] else 0
        mask = int(parts[3], 16) if parts[3] else 0
        temp = float(parts[4]) if len(parts) > 4 and parts[4] else 0.0
        return (power_w, sm, util, mask, temp)

    def close(self):
        if self.use_nvml and self.nvml:
            try:
                self.nvml.nvmlShutdown()
            except:
                pass

# ---------- Main Monitor ----------

class GPUMonitor:
    def __init__(self, args):
        self.args = args
        self.term = Terminal()
        self.backend = Backend()

        # Get GPU info
        try:
            self.gpu_count = self.backend.device_count()
        except Exception as e:
            print(f"Error: Unable to query GPUs. Is NVIDIA driver loaded?")
            print(f"Details: {e}")
            sys.exit(1)

        if args.gpus.lower() == "all":
            self.gpu_indices = list(range(self.gpu_count))
        else:
            self.gpu_indices = [int(x) for x in args.gpus.split(",") if x.strip()]

        self.gpu_names = {i: self.backend.name(i) for i in self.gpu_indices}

        # Initialize histories for graphs (last 40 samples)
        self.histories = {i: collections.deque(maxlen=40) for i in self.gpu_indices}

        # CSV logging
        self.csvf = None
        if args.csv:
            self.csvf = open(args.csv, "w", buffering=1)
            header = ["timestamp", "gpu", "power_w", "sm_mhz", "util_pct", "temp_c", "mask_hex", "problems"]
            self.csvf.write(",".join(header) + "\n")

        self.start_time = time.time()
        self.stop_flag = False

        # Set up signal handler
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        self.stop_flag = True

    def get_problem_description(self, mask: int) -> str:
        """Get human-readable problem description"""
        problems = []

        if mask & 0x0080:  # HW Power Brake
            problems.append("POWER LIMIT: GPU wants more power but is limited by power delivery")
        if mask & 0x0040:  # HW Thermal
            problems.append("OVERHEATING: Hardware thermal protection activated")
        if mask & 0x0020:  # SW Thermal
            problems.append("HOT: Driver thermal throttling")
        if mask & 0x0004:  # SW Power Cap
            problems.append("CAPPED: Software power limit reached")
        if mask & 0x0008:  # HW Slowdown
            problems.append("THROTTLED: General hardware slowdown")

        if not problems:
            return "OK: No throttling"

        return " | ".join(problems)

    def update_display(self):
        """Update the terminal display"""
        now = time.time()
        self.term.update_size()

        # Collect samples
        per_gpu = {}
        for i in self.gpu_indices:
            data = self.backend.sample(i)
            per_gpu[i] = data

            # Update history for graphs
            power_w, sm, util, mask, temp = data
            # Store if throttled (1) or not (0)
            is_throttled = 1 if (mask & 0x00E8) else 0  # Check all throttle bits
            self.histories[i].append(is_throttled)

            # CSV logging
            if self.csvf:
                power_w, sm, util, mask, temp = data
                problems = self.get_problem_description(mask)
                fields = [
                    dt.datetime.fromtimestamp(now).isoformat(timespec="milliseconds"),
                    str(i), f"{power_w:.2f}", str(sm), str(util),
                    f"{temp:.1f}", f"0x{mask:016x}", problems
                ]
                self.csvf.write(",".join(fields) + "\n")

        # Clear screen
        self.term.clear_screen()

        # Check if we have enough space - compact mode if too small
        needed_lines = len(self.gpu_indices) * 4 + 3  # 4 lines per GPU + header
        compact_mode = self.term.height < needed_lines

        # Header
        uptime = now - self.start_time

        if compact_mode:
            # Ultra compact for small terminals
            print(f"{self.term.BOLD}GPU Monitor{self.term.RESET} [{uptime:.0f}s] {self.term.RED}[COMPACT MODE - Terminal too small]{self.term.RESET}")

            for i in self.gpu_indices:
                power_w, sm, util, mask, temp = per_gpu[i]

                # Build mini graph (last 20 samples)
                mini_graph = ""
                history_slice = list(self.histories[i])[-20:]
                for val in history_slice:
                    if val:
                        mini_graph += f"{self.term.RED}█{self.term.RESET}"
                    else:
                        mini_graph += "·"
                # Pad if needed
                pad = 20 - len(history_slice)
                mini_graph = "·" * pad + mini_graph

                # Single line per GPU
                line = f"{self.term.CYAN}GPU{i}{self.term.RESET}: {power_w:3.0f}W {sm:4d}MHz {temp:2.0f}°C {mini_graph}"

                # Add problem codes
                if mask & 0x0080:
                    line += f" {self.term.RED}PWR{self.term.RESET}"
                elif mask & 0x0040:
                    line += f" {self.term.RED}THM{self.term.RESET}"
                elif mask & 0x0020:
                    line += f" {self.term.YELLOW}HOT{self.term.RESET}"
                elif mask & 0x0004:
                    line += f" {self.term.YELLOW}CAP{self.term.RESET}"

                print(line)
        else:
            # Normal display
            print(f"{self.term.BOLD}GPU Throttle Monitor{self.term.RESET} │ "
                  f"Uptime: {uptime:.1f}s │ "
                  f"{'NVML' if self.backend.use_nvml else 'nvidia-smi'}")
            print("─" * min(self.term.width, 120))

            # Display each GPU
            for i in self.gpu_indices:
                power_w, sm, util, mask, temp = per_gpu[i]

                # GPU status line
                status = f"{self.term.CYAN}GPU{i}{self.term.RESET}: "
                status += f"{power_w:5.1f}W │ {sm:4d}MHz │ {util:3d}% │ {temp:3.0f}°C"

                # Temperature warning
                if temp > 80:
                    status += f" {self.term.RED}[OVERHEATING]{self.term.RESET}"
                elif temp > 70:
                    status += f" {self.term.YELLOW}[HOT]{self.term.RESET}"

                print(status)

                # Throttle graph - show history
                graph = ""
                for val in self.histories[i]:
                    if val:
                        graph += f"{self.term.RED}█{self.term.RESET}"  # Red block for throttled
                    else:
                        graph += "·"  # Dot for OK

                # Pad graph if not full
                pad = 40 - len(self.histories[i])
                graph = "·" * pad + graph

                print(f"  History: {graph}")

                # Problem description - ALWAYS shown
                problem = self.get_problem_description(mask)
                if "OK:" in problem:
                    print(f"  Status: {self.term.GREEN}{problem}{self.term.RESET}")
                elif "POWER LIMIT" in problem or "OVERHEATING" in problem:
                    print(f"  Status: {self.term.RED}{problem}{self.term.RESET}")
                elif "HOT" in problem or "CAPPED" in problem:
                    print(f"  Status: {self.term.YELLOW}{problem}{self.term.RESET}")
                else:
                    print(f"  Status: {problem}")

                print()  # Blank line between GPUs

        # Footer
        print("─" * min(self.term.width, 120))
        print(f"{self.term.DIM}Press Ctrl+C to exit{self.term.RESET}")

        sys.stdout.flush()

    def show_summary(self):
        """Show run summary with problem analysis"""
        runtime = time.time() - self.start_time
        print(f"\n{self.term.BOLD}=== SUMMARY ==={self.term.RESET}")
        print(f"Runtime: {runtime:.1f} seconds\n")

        print(f"{self.term.BOLD}PROBLEM ANALYSIS:{self.term.RESET}")
        print()

        # Analyze each GPU's last state
        for i in self.gpu_indices:
            try:
                data = self.backend.sample(i)
            except:
                # NVML may be closed, skip
                continue
            power_w, sm, util, mask, temp = data

            print(f"{self.term.CYAN}GPU{i} [{self.gpu_names[i]}]{self.term.RESET}")

            problems_found = False

            # Critical problems
            if mask & 0x0080:
                problems_found = True
                print(f"  {self.term.RED}✗ POWER BRAKE ACTIVE{self.term.RESET}")
                print(f"    Problem: GPU needs more power than available")
                print(f"    Solution: Check PSU capacity, PCIe power cables, or increase power limit")
                print()

            if mask & 0x0040:
                problems_found = True
                print(f"  {self.term.RED}✗ THERMAL THROTTLING{self.term.RESET}")
                print(f"    Problem: GPU is overheating (currently {temp:.0f}°C)")
                print(f"    Solution: Improve cooling, check thermal paste, increase fan speed")
                print()

            # Warnings
            if mask & 0x0020:
                problems_found = True
                print(f"  {self.term.YELLOW}⚠ SOFTWARE THERMAL LIMIT{self.term.RESET}")
                print(f"    Problem: Driver is limiting performance due to temperature")
                print(f"    Solution: Improve airflow, reduce ambient temperature")
                print()

            if mask & 0x0004:
                problems_found = True
                print(f"  {self.term.YELLOW}⚠ POWER CAP{self.term.RESET}")
                print(f"    Problem: Software power limit is restricting performance")
                print(f"    Solution: Use 'sudo nvidia-smi -pl <watts>' to increase limit")
                print()

            if not problems_found:
                print(f"  {self.term.GREEN}✓ No problems detected{self.term.RESET}")
                print()

        if self.csvf:
            print(f"\n{self.term.GREEN}CSV log saved to: {self.args.csv}{self.term.RESET}")

    def run(self):
        """Main monitoring loop"""
        self.term.hide_cursor()

        try:
            deadline = self.start_time + self.args.duration if self.args.duration > 0 else None

            while not self.stop_flag:
                if deadline and time.time() >= deadline:
                    break

                self.update_display()
                time.sleep(self.args.interval)

        finally:
            # Cleanup
            self.term.show_cursor()
            self.term.clear_screen()

            if self.csvf:
                self.csvf.close()

            self.backend.close()

            # Show summary
            self.show_summary()

# ---------- Main Entry Point ----------

def main():
    args = parse_args()

    try:
        monitor = GPUMonitor(args)
        monitor.run()
    except KeyboardInterrupt:
        print("\n\nMonitoring interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()