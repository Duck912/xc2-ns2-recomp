#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
r"""Name the entry points inside a Vulkan ICD DLL (Windows).

    python tools\analysis\vk_entry_map.py <icd.dll> [--rva 0x1ac180 ...] [--out map.txt]

The loader normally hides this: a crash log says "amdvlk64.dll+0x4acf06" and the module exports only
vk_icdGetInstanceProcAddr, so there is no name to look up. This script plays the loader's part instead -- it loads the
ICD, creates a VkInstance through the ICD's own vkCreateInstance (no loader involved) and then asks
vk_icdGetInstanceProcAddr for every prototype in vulkan_core.h. Each answer is an address inside the DLL, so the result
is an RVA -> name table for every instance and device entry point (492 of them on amdvlk 9.2.10.353).

That is how HANDOVER 95 identified the amdvlk crash site: 0x1ac180 -> vkCmdPipelineBarrier.
Vulkan header: $VULKAN_SDK\Include\vulkan\vulkan_core.h, or --header.
"""

import argparse
import ctypes
import os
import re
import sys


class VkApplicationInfo(ctypes.Structure):
    _fields_ = [('sType', ctypes.c_int32), ('pNext', ctypes.c_void_p), ('pApplicationName', ctypes.c_char_p),
                ('applicationVersion', ctypes.c_uint32), ('pEngineName', ctypes.c_char_p),
                ('engineVersion', ctypes.c_uint32), ('apiVersion', ctypes.c_uint32)]


class VkInstanceCreateInfo(ctypes.Structure):
    _fields_ = [('sType', ctypes.c_int32), ('pNext', ctypes.c_void_p), ('flags', ctypes.c_uint32),
                ('pApplicationInfo', ctypes.POINTER(VkApplicationInfo)),
                ('enabledLayerCount', ctypes.c_uint32), ('ppEnabledLayerNames', ctypes.c_void_p),
                ('enabledExtensionCount', ctypes.c_uint32), ('ppEnabledExtensionNames', ctypes.c_void_p)]


def prototypes(header):
    src = open(header, 'r', encoding='utf-8', errors='replace').read()
    return sorted(set(re.findall(r'VKAPI_ATTR\s+[A-Za-z0-9_\*\s]+VKAPI_CALL\s+(vk[A-Za-z0-9_]+)\s*\(', src)))


def main(argv=None):
    ap = argparse.ArgumentParser(description='map Vulkan entry points of an ICD DLL to RVAs')
    ap.add_argument('icd')
    ap.add_argument('--rva', action='append', default=[], help='also resolve this RVA (repeatable)')
    ap.add_argument('--header', default='', help='vulkan_core.h (default: $VULKAN_SDK)')
    ap.add_argument('--out', default='', help='write the whole RVA -> name table here')
    a = ap.parse_args(argv)
    header = a.header or os.path.join(os.environ.get('VULKAN_SDK', r'C:\VulkanSDK\1.4.363.0'),
                                      'Include', 'vulkan', 'vulkan_core.h')
    names = prototypes(header)
    print('%d prototypes from %s' % (len(names), header))

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.LoadLibraryW.restype = ctypes.c_void_p
    k32.LoadLibraryW.argtypes = [ctypes.c_wchar_p]
    k32.GetProcAddress.restype = ctypes.c_void_p
    k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    base = k32.LoadLibraryW(a.icd)
    if not base:
        print('LoadLibrary failed (%d)' % ctypes.get_last_error())
        return 2
    icd_gipa = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(
        k32.GetProcAddress(base, b'vk_icdGetInstanceProcAddr'))
    if not icd_gipa:
        print('no vk_icdGetInstanceProcAddr: not a Vulkan ICD')
        return 2
    buf = ctypes.create_string_buffer(256)

    def gipa(inst, name):
        buf.value = name.encode()
        return icd_gipa(inst, ctypes.cast(buf, ctypes.c_char_p))

    create = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.POINTER(VkInstanceCreateInfo), ctypes.c_void_p,
                              ctypes.POINTER(ctypes.c_void_p))(gipa(None, 'vkCreateInstance'))
    app = VkApplicationInfo(0, None, b'vk_entry_map', 1, b'vk_entry_map', 1, (1 << 22) | (4 << 12))
    ci = VkInstanceCreateInfo(1, None, 0, ctypes.pointer(app), 0, None, 0, None)
    inst = ctypes.c_void_p()
    if create(ctypes.byref(ci), None, ctypes.byref(inst)) != 0 or not inst.value:
        print('vkCreateInstance failed; the ICD needs a real device? falling back to instance-less queries')
    table = {}
    for n in names:
        p = gipa(inst.value, n)
        if p:
            table[n] = p - base
    print('%d entry points resolved inside %s' % (len(table), os.path.basename(a.icd)))
    inv = {}
    for n, r in table.items():
        inv.setdefault(r, []).append(n)
    for r in a.rva:
        rva = int(r, 0)
        hit = ','.join(sorted(inv.get(rva, [])))
        print('  0x%08x -> %s' % (rva, hit or '(internal function: not an entry point)'))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            for n, r in sorted(table.items(), key=lambda kv: kv[1]):
                f.write('%08x %s\n' % (r, n))
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
