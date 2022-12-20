#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import os,sys
import time
import unittest
import addtoplevelpath
from gpufort import grammar

print("Running test '{}'".format(os.path.basename(__file__)),end="",file=sys.stderr)

class TestGramarNummber(unittest.TestCase):
    def setUp(self):
        global index
        self.started_at = time.time()
    def tearDown(self):
        elapsed = time.time() - self.started_at
        print('{} ({}s)'.format(self.id(), round(elapsed, 9)))
    def test_0_type_start_pass(self):
        testdata = """-1
         +1
         -12
         +12
         .1
         +1
         -1.
         +1.
         -12.3
         +12.3
         -12.3e0
         -12.3d0
         -12.3d1.
         -12.3d1.5
         -12.3d-1.5
         -12.3d-1.5_dp
         -12.3d-1.5_4
         .5e-4_w
         .5_w4""".splitlines()
        for snippet in testdata:
            try:
                grammar.number.parseString(snippet)
            except Exception as e:
                self.assertTrue(False, "failed to parse '{}'".format(snippet)) 

if __name__ == '__main__':
    unittest.main() 