# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
"""Parent package for GPUFORT's C/C++ code generators.

This package mainly provides generic classes
and base classes to its subpackages.
"""
from .filegen import *
from .derivedtypegen import *
from .kernelgen import *
from .templategen import *

from . import hip
from . import gpufort_sources
from . import render

#from . import opts # might not work; might create new opts module that differs from the package-local opts module
from .render import opts # imports package-local opts module

print("init gpufort.fort2x")
