"""
Overkube — Cloud Pricing Calculator
===================================
Converts CPU (millicores) and Memory (MiB) waste or usage values into estimated
monthly cost ($USD) based on cloud provider rates.

Default rates are blended AWS EC2 rates:
  - CPU   : $0.0400 per vCPU-hour
  - Memory: $0.0050 per GB-hour

Rates can be overridden using app settings (which read from environment variables or a .env file).
Support for loading custom rates from a JSON config file is also included.
"""

from __future__ import annotations

import os
import json
import logging
from typing import TypedDict
from app.config import settings

logger = logging.getLogger(__name__)

# Blended default rates
DEFAULT_CPU_RATE = 0.0400  # $/vCPU-hour
DEFAULT_MEM_RATE = 0.0050  # $/GB-hour (1 GB = 1024 MiB)

# Standard hours in a month (30 days * 24 hours = 730 hours average)
HOURS_PER_MONTH = 730.0


class PricingRates(TypedDict):
    cpu_rate_per_vcpu_hour: float
    mem_rate_per_gb_hour: float


def load_pricing_rates() -> PricingRates:
    """
    Loads pricing rates, prioritizing overrides from a pricing_config.json file
    if it exists in the app root, then checking application settings,
    and falling back to the hardcoded defaults.
    """
    config_path = os.path.join(os.getcwd(), "pricing_config.json")
    
    # Try reading from file first
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                cpu_rate = data.get("cpu_rate_per_vcpu_hour", settings.price_cpu_per_vcpu_hour)
                mem_rate = data.get("mem_rate_per_gb_hour", settings.price_mem_per_gb_hour)
                logger.info(f"Loaded custom pricing from pricing_config.json: CPU=${cpu_rate}/vCPU-hr, Mem=${mem_rate}/GB-hr")
                return {
                    "cpu_rate_per_vcpu_hour": float(cpu_rate),
                    "mem_rate_per_gb_hour": float(mem_rate)
                }
        except Exception as e:
            logger.warning(f"Failed to read pricing_config.json, using defaults: {e}")

    # Fall back to settings (env variables or default settings values)
    return {
        "cpu_rate_per_vcpu_hour": settings.price_cpu_per_vcpu_hour,
        "mem_rate_per_gb_hour": settings.price_mem_per_gb_hour
    }


def calculate_monthly_cost(cpu_millicores: float, mem_mib: float) -> float:
    """
    Calculate the monthly cost in USD for a given CPU (millicores) and Memory (MiB) allocation.
    """
    rates = load_pricing_rates()
    
    # CPU calculation:
    # (cpu_millicores / 1000) = vCPUs
    # cost = vCPUs * rate * hours_per_month
    vcpus = cpu_millicores / 1000.0
    cpu_cost = vcpus * rates["cpu_rate_per_vcpu_hour"] * HOURS_PER_MONTH
    
    # Memory calculation:
    # (mem_mib / 1024) = GBs
    # cost = GBs * rate * hours_per_month
    gb = mem_mib / 1024.0
    mem_cost = gb * rates["mem_rate_per_gb_hour"] * HOURS_PER_MONTH
    
    return round(cpu_cost + mem_cost, 2)


def calculate_waste_cost(
    current_cpu: float,
    recommended_cpu: float,
    current_mem: float,
    recommended_mem: float
) -> float:
    """
    Computes the waste cost ($/month) when current allocation is higher than recommended.
    If the service is under-provisioned (recommended > current), returns 0.0.
    """
    cpu_diff = max(0.0, current_cpu - recommended_cpu)
    mem_diff = max(0.0, current_mem - recommended_mem)
    return calculate_monthly_cost(cpu_diff, mem_diff)
