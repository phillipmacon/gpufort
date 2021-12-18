#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
# SPDX-License-Identifier: MIT
# Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
import addtoplevelpath
import sys
import test

import grammar.grammar as grammar

testdata = []
testdata.append("size(x,1)")
testdata.append("size(y,dim=1)")
testdata.append("size(z,dim=1,kind=4)")
testdata.append("lbound(x,2)")
testdata.append("lbound(y,dim=2)")
testdata.append("lbound(z,dim=2,kind=4)")
testdata.append("ubound(x,1)")
testdata.append("ubound(y,dim=1)")
testdata.append("ubound(z,dim=1,kind=4)")
testdata.append("size(a%x,1)")
testdata.append("size(a%y,dim=1)")
testdata.append("size(a(i,j)%z,dim=1,kind=4)")

test.run(
   expression     = grammar.inquiry_function,
   testdata       = testdata,
   tag            = "inquiry_function",
   raiseException = True
)