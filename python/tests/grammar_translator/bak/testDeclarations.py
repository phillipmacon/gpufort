#!/usr/bin/env python3
import sys
sys.path.append("../..")
from kernelconverter.grammar import * 

print (declaration.parseString("COMPLEX(DP), ALLOCATABLE :: wfcatom_d(:,:,:) ! atomic wfcs for initialization (device)"))
print (attributes.parseString("attributes(DEVICE) :: etatom_d, wfcatom_d, randy_d"))
#print (structElem.parseString("threadidx%x3")[0].cStr())
#print (datatype.parseString("double precision")[0].cStr())
#print (declaration.parseString("real(kind=8) :: rhx, rhy")[0].cStr())
#print (declaration.parseString("real(kind=8), device :: rhx, rhy")[0].cStr())
#print (declaration.parseString("real, device, parameter :: rhx, rhy")[0].cStr())
#print (datatype.parseString("integer(kind=2)")[0].cStr())
#print (declaration.parseString("real, device, parameter :: rhx(:,:), rhy(:,:)")[0].cStr())
#print (declaration.parseString("real, device, parameter :: rhx(:,:) = 3, rhy(:,:) = 2")[0].cStr())