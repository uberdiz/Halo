"""
Calamares job, in place of the partition module when installing to free space. The work is in SAINT's
core/install_target.py (standard library only, tested there); this fills the same globals the partition module
would, which mount, fstab, initcpiocfg, grubcfg and bootloader read.
"""

import importlib.util

import libcalamares

MODULE = "/opt/saint/app/core/install_target.py"


def pretty_name():
    return "Making room for HalOS in the free space"


def run():
    spec = importlib.util.spec_from_file_location("halos_install_target", MODULE)
    target = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = target              # dataclasses look their module up here
    spec.loader.exec_module(target)
    try:
        plan = target.load_plan()
        values = target.apply(plan)
    except target.TargetError as e:
        return "HalOS couldn't use that free space", str(e)
    for key, value in values.items():
        libcalamares.globalstorage.insert(key, value)
    return None
