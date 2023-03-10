#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
import addtoplevelpath
import os,sys
import time
import unittest
import cProfile,pstats,io
import re

import utils.logging
import translator.translator as translator
import indexer.indexerutils as indexerutils

log_format = "[%(levelname)s]\tgpufort:%(message)s"
log_level                   = "warning"
utils.logging.VERBOSE       = False
utils.logging.TRACEBACK = False
utils.logging.init_logging("log.log",log_format,log_level)

class TestParseLoopAnnotation(unittest.TestCase):
    def setUp(self):
        self.testdata = [
          "!$acc loop",
          "!$acc kernels loop create(b) copy(a(:)) reduction(+:c) async(1)",
          "!$acc parallel loop",
          "!$acc loop gang worker",
          "!$acc loop gang"
        ]
        self.started_at = time.time()
    def tearDown(self):
        elapsed = time.time() - self.started_at
        print('{} ({}s, {} directives)'.format(self.id(), round(elapsed, 6),len(self.testdata)))
    def test_0_parse_loop_annotation(self):
        for snippet in self.testdata:
            try:
                result = translator.loop_annotation.parseString(snippet,parseAll=True)
            except Exception as e:
                print("failed to parse '{}'".format(snippet),file=sys.stderr)
                raise e

if __name__ == '__main__':
    unittest.main() 