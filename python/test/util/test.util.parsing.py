#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import time
import unittest
import cProfile,pstats,io
import json

import addtoplevelpath
from gpufort import util

LOG_FORMAT = "[%(levelname)s]\tgpufort:%(message)s"
util.logging.opts.verbose    = False
util.logging.init_logging("log.log",LOG_FORMAT,"warning")

PROFILING_ENABLE = False

testdata1 = \
"""
! comment
  ! comment
stmt_or_dir ! comment
!$acc stmt_or_dir
*$acc stmt_or_dir
c$acc stmt_or_dir
C$acc stmt_or_dir
!$ acc stmt_or_dir
! $acc comment
  !a$acc comment
"""

# whitespace at begin is important to
# as [cC] in first column indicates a comment
# line in Fortran 77.
testdata2 = """\
    call myroutine( & ! comment 1
        arg1,&
        ! comment 2


        arg2) ! comment 3
    !$acc directive & ! comment 4
    !$acc clause1(var) &
    !$acc& clause2(var)\
"""

testdata2_result = """\
    call myroutine( &
        arg1,&
        arg2)
    ! comment 1
        ! comment 2
        ! comment 3
    !$acc directive &
    !$acc clause1(var) &
    !$acc& clause2(var)
    ! comment 4\
"""

testdata3="k () + a ( b, c(d)+e(f)) + g(h(i,j+a(k(),2)))"""

testdata3_result= {
    "a" :  [('a ( b, c(d)+e(f))', [' b', ' c(d)+e(f)']), ('a(k(),2)', ['k()', '2'])],
    "b" :  [],
    "c" :  [('c(d)', ['d'])],
    "d" :  [],
    "f" :  [],
    "g" :  [('g(h(i,j+a(k(),2)))', ['h(i,j+a(k(),2))'])],
    "h" :  [('h(i,j+a(k(),2))', ['i', 'j+a(k(),2)'])],
    "i" :  [],
    "j" :  [],
    "k" :  [('k ()', []), ('k()', [])],
    }


class TestParsingUtils(unittest.TestCase):
    def prepare(self,text):
        return text.strip().splitlines()
    def clean(self,text):
        return text.replace(" ","").replace("\t","").replace("\n","").replace("\r","")
    def setUp(self):
        global PROFILING_ENABLE
        if PROFILING_ENABLE:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
        self.started_at = time.time()
    def tearDown(self):
        global PROFILING_ENABLE
        if PROFILING_ENABLE:
            self.profiler.disable() 
            s = io.StringIO()
            sortby = 'cumulative'
            stats = pstats.Stats(self.profiler, stream=s).sort_stats(sortby)
            stats.print_stats(10)
            print(s.getvalue())
        elapsed = time.time() - self.started_at
        print('{} ({}s)'.format(self.id(), round(elapsed, 6)))
    def test_01_tokenize(self):
        statements = [
          "a,b(i,j),c(i,j,k)",  # 17 tokens
          "call debug(1, \"my literal string with ; and \\\"; use something \")",
          "call debug(1, 'my literal string with ; and \\'; use something ')",
          "end do",
          "enddo",
          "end if",
          "endif",
          "else if",
          "elseif",
          "!$acc enter data copyin(a) copyout(b(-1:))",
        ]
        results = [
          ['a', ',', 'b', '(', 'i', ',', 'j', ')', ',', 'c', '(', 'i', ',', 'j', ',', 'k', ')'],
          ['call', 'debug', '(', '1', ',', '"my literal string with ; and \\"; use something "', ')'],
          ['call', 'debug', '(', '1', ',', "'my literal string with ; and \\'; use something '", ')'],
          ['end', 'do'],
          ['end', 'do'],
          ['end', 'if'],
          ['end', 'if'],
          ['else', 'if'],
          ['else', 'if'],
          ['!$', 'acc', 'enter', 'data', 'copyin', '(', 'a', ')', 'copyout', '(', 'b', '(', '-', '1', ':', ')', ')'],
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.tokenize(stmt))
            self.assertEqual(util.parsing.tokenize(stmt),results[i])
    def test_02_split_fortran_line(self):
        for line in self.prepare(testdata1):
            indent,stmt_or_dir,comment,trailing_ws =\
              util.parsing.split_fortran_line(line)
            if "stmt_or_dir" in line:
                self.assertTrue(len(stmt_or_dir))
            else:
                self.assertFalse(len(stmt_or_dir))
            if "comment" in line:
                self.assertTrue(len(comment))
            else:
                self.assertFalse(len(comment))
        # 
    def test_03_detect_line_starts(self):
        input_lines = testdata2.splitlines()
        linenos = util.parsing.detect_line_starts(\
                   input_lines)
        #print(linenos)
        #print([a for i,a in enumerate(input_lines) if i in linenos]) 
        self.assertEqual(linenos,[0,6,9])
    def test_04_relocate_inline_comments(self):
        result = util.parsing.relocate_inline_comments(\
                   testdata2.splitlines())
        self.assertEqual(self.clean("\n".join(result)),self.clean(testdata2_result))
    def test_05_get_top_level_operands(self):
        statements = [
          "a,b(i,j),c(i,j,k)",  # 17 tokens
          "a,b(i,j),c(i,j,k))",
          "a,b(i,j),c(i,j,k)))",
          "-1:2*(m+b)*c:k", # 14 tokens
          "a%b(i%a(5)%i3(mm%i4),j)%c(i%k%n,j,k%k%j)",
          "a%b(a,:) = myfunc(a,f=3)*b(:)",
          #"integer * 5 pure recursive function foo( arg1, arg2, arg3 ) result(i5) bind(c,name=\"cname\")",
        ]
        separators = [
          [","],
          [","],
          [","],
          [":"],
          ["%"],
          ["="],
        ]
        results = [
          (['a', 'b(i,j)', 'c(i,j,k)'],17),
          (['a', 'b(i,j)', 'c(i,j,k)'],17),
          (['a', 'b(i,j)', 'c(i,j,k)'],17),
          (['-1', '2*(m+b)*c', 'k'],14),
          (['a', 'b(i%a(5)%i3(mm%i4),j)', 'c(i%k%n,j,k%k%j)'], 37),
          (['a%b(a,:)', 'myfunc(a,f=3)*b(:)'], 22),
        ]
        for i,stmt in enumerate(statements):
           #print(util.parsing.get_top_level_operands(util.parsing.tokenize(stmt),
           #                                          separators=separators[i]))
           self.assertEqual(util.parsing.get_top_level_operands(util.parsing.tokenize(stmt),
                            separators=separators[i]),results[i])

    def test_06_extract_function_calls(self):
        for c in ["a","b","c","d","f","g","h","i","j","k"]:
        #for c in ["a"]:
            result = util.parsing.extract_function_calls(testdata3,c)
            #print(result)
            self.assertEqual(result,testdata3_result[c])
    def test_07_parse_use_statement(self):
        statements = [
          "use mymod",
          "use mymod, only: var1",
          "use mymod, only: var1, var2",
          "use mymod, only: var1, var2=>var3",
          "use mymod, var4 => var5",
          "USE module_domain, ONLY : domain, get_ijk_from_grid",
          "use, intrinsic :: iso_c_binding",
          "use, intrinsic :: iso_c_binding, only: myptr_t => c_ptr",
          "use, intrinsic :: iso_c_binding, myptr_t => c_ptr",
        ]
        results = [
          ('mymod', [], [], []),
          ('mymod', [], [], [('var1', 'var1')]),
          ('mymod', [], [], [('var1', 'var1'),('var2', 'var2')]),
          ('mymod', [], [], [('var1', 'var1'),('var2', 'var3')]),
          ('mymod', [], [('var4', 'var5')], []),
          ('module_domain', [], [], [('domain', 'domain'), ('get_ijk_from_grid', 'get_ijk_from_grid')]),
          ('iso_c_binding', ['intrinsic'], [], []),
          ('iso_c_binding', ['intrinsic'], [], [('myptr_t', 'c_ptr')]),
          ('iso_c_binding', ['intrinsic'], [('myptr_t', 'c_ptr')], []),
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.parse_use_statement(stmt))
            self.assertEqual(util.parsing.parse_use_statement(stmt),results[i])
    def test_08_parse_declaration(self):
        statements = [
          "integer,parameter :: a(1) = (/1/), b = 5*2**3",
          "integer(kind(hipSuccess)),parameter :: ierr = hipSuccess",
          "integer(kind=4),parameter :: mykind = 3",
          "integer*4,pointer :: a(:) => null(), b => null()",
          "integer*4,allocatable :: b(:,:,n,-1:5)",
          "integer,dimension(:,:) :: int_array2d",
          "character*(*) :: a",
          "character*(len=*) :: a",
          "integer a( m ), b( m, n )",
          "real*8 a( * ), b( * )",
          "character*(*), intent(in)    :: c",
        ]
        results = [
          # type, kind, qualifiers without dimensions, dimension bounds, variables: list of (name, bounds, rhs)
          ('integer', None, ['parameter'], [], [('a', ['1'], '(/1/)'), ('b', [], '5*2**3')], 'integer', ['parameter']),
          ('integer', 'kind(hipSuccess)', ['parameter'], [], [('ierr', [], 'hipSuccess')], 'integer(kind(hipSuccess))', ['parameter']),
          ('integer', '4', ['parameter'], [], [('mykind', [], '3')], 'integer(kind=4)', ['parameter']),
          ('integer', '4', ['pointer'], [], [('a', [':'], 'null()'), ('b', [], 'null()')], 'integer*4', ['pointer']),
          ('integer', '4', ['allocatable'], [], [('b', [':', ':', 'n', '-1:5'], None)], 'integer*4', ['allocatable']),
          ('integer', None, [], [':', ':'], [('int_array2d', [], None)], 'integer', ['dimension(:,:)']) ,
          ('character', '*', [], [], [('a', [], None)], 'character*(*)', []),
          ('character', 'len=*', [], [], [('a', [], None)], 'character*(len=*)', []),
          ('integer', None, [], [], [('a', ['m'], None), ('b', ['m', 'n'], None)], 'integer', []),
          ('real', '8', [], [], [('a', ['*'], None), ('b', ['*'], None)], 'real*8', []),
          ('character', '*', ['intent(in)'], [], [('c', [], None)], 'character*(*)', ['intent(in)']),
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.parse_declaration(stmt))
            self.assertEqual(util.parsing.parse_declaration(stmt),results[i])
    def test_09_parse_do_statement(self):
        statements = [
          "DO jj = MAX(jts,1) , MIN(jte,jde-1,spec_bdy_width)",
          "label: do j = min(x,y,z,k), max(M,n), min(a0,a1,2)",
          "DO 2000 IIM=1,NF"
        ]
        results = [
          (None, 'jj', 'MAX(jts,1)', 'MIN(jte,jde-1,spec_bdy_width)', None),
          ('label', 'j', 'min(x,y,z,k)', 'max(M,n)', 'min(a0,a1,2)'),
          ('2000', 'IIM', '1', 'NF', None),
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.parse_do_statement(stmt))
            self.assertEqual(util.parsing.parse_do_statement(stmt),results[i])
    def test_10_parse_type_statement(self):
        statements = [
          "type a",
          "type :: a",
          "type,bind(c) :: a",
          "type,bind(c) :: a(k,l)",
          "type,bind(c),private :: a(k,l)",
        ]
        results = [
          ('a', [], []),
          ('a', [], []),
          ('a', ['bind(c)'], []),
          ('a', ['bind(c)'], ['k', 'l']),
          ('a', ['bind(c)', 'private'], ['k', 'l']),
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.parse_type_statement(stmt))
            self.assertEqual(util.parsing.parse_type_statement(stmt),results[i])
    def test_11_parse_attributes_statement(self):
        statements = [
          "attributes(device,constant) :: a_d, b_d"
        ]
        results = [
          (['device','constant'], ['a_d','b_d'])
        ]
        for i,stmt in enumerate(statements):
            #print(util.parsing.parse_attributes_statement(stmt))
            self.assertEqual(util.parsing.parse_attributes_statement(stmt),results[i])
    def test_12_parse_function_statement(self):
        statements = [
          "function foo",
          "function foo()",
          "logical function foo ( arg1, arg2, arg3 )",
          "attributes(device) function foo()",
          "function foo( arg1, arg2, arg3 ) result(i5) bind(c,name=\"cname\")",
          "integer * 5 pure recursive function foo( arg1, arg2, arg3 ) result(i5) bind(c,name=\"cname\")",
          "integer(kind(hipSuccess)) attributes(host,device) pure recursive function foo( arg1, arg2, arg3 ) result(i5) bind(c,name=\"cname\")",
          "attributes(host,device) pure recursive subroutine foo( arg1, arg2, arg3 ) bind(c,name=\"cname\")",
        ]
        results = [
            ('function', 'foo', [], [], [], (None, None, 'foo'), (False, None)),
            ('function', 'foo', [], [], [], (None, None, 'foo'), (False, None)),
            ('function', 'foo', ['arg1', 'arg2', 'arg3'], [], [], ('logical', None, 'foo'), (False, None)),
            ('function', 'foo', [], [], ['device'], (None, None, 'foo'), (False, None)),
            ('function', 'foo', ['arg1', 'arg2', 'arg3'], [], [], (None, None, 'i5'), (True, 'cname')),
            ('function', 'foo', ['arg1', 'arg2', 'arg3'], ['pure', 'recursive'], [], ('integer', '5', 'i5'), (True, 'cname')),
            ('function', 'foo', ['arg1', 'arg2', 'arg3'], ['pure', 'recursive'], ['host', 'device'], ('integer', 'kind(hipSuccess)', 'i5'), (True, 'cname')),
            ('subroutine', 'foo', ['arg1', 'arg2', 'arg3'], ['pure', 'recursive'], ['host', 'device'], (None, None, None), (True, 'cname')),
        ]
        for i,stmt in enumerate(statements):
           #print(util.parsing.parse_function_statement(stmt))
           self.assertEqual(util.parsing.parse_function_statement(stmt),results[i])
    def test_13_strip_array_indexing(self):
        expressions = [
          "a",
          "a(1)",
          "a(:,5)",
          "a(:,5)%b",
          "A(:,5)%b(c(5,2))%c",
        ]
        results = [
          "a",
          "a",
          "a",
          "a%b",
          "A%b%c",
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.strip_array_indexing(expr))
            self.assertEqual(util.parsing.strip_array_indexing(expr),results[i])
    def test_14_derived_type_parents(self):
        expressions = [
          "a",
          "a(1)",
          "a(:,5)",
          "a(:,5)%b",
          "A(:,5)%b(c(5,2))%c",
        ]
        results = [
          [],
          [],
          [],
          ['a'],
          ['A', 'A%b'],
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.derived_type_parents(expr))
            self.assertEqual(util.parsing.derived_type_parents(expr),results[i])
    def test_15_parse_directive(self):
        expressions = [
          "!$acc enter data copyin(a,b,c(:)) copyout(b(-1:))",
        ]
        results = [
          ['!$', 'acc', 'enter', 'data', 'copyin(a,b,c(:))', 'copyout(b(-1:))'],
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_directive(expr))
            self.assertEqual(util.parsing.parse_directive(expr),results[i])
    
    def test_16_parse_acc_clauses(self):
        expressions = [
          ["copyin(a,b,c(:))","copyout(b(-1:))","async"],
          ["copyin(a,b,c(:))","copyout(b(-1:))","reduction(+:a)","async"],
          ["map(to:x,y(:),tofrom:a%z(1:n,2:m))"], # actually OMP clauses
        ]
        results = [
          [('copyin', ['a', 'b', 'c(:)']), ('copyout', ['b(-1:)']), ('async', [])],
          [('copyin', ['a', 'b', 'c(:)']), ('copyout', ['b(-1:)']), ('reduction', [('+', ['a'])]), ('async', [])],
          [('map', [('to', ['x', 'y(:)']), ('tofrom', ['a%z(1:n,2:m)'])])],
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_acc_clauses(expr))
            self.assertEqual(util.parsing.parse_acc_clauses(expr),results[i])
    
    def test_17_parse_acc_directive(self):
        expressions = [
          "!$acc enter data copyin(a,b,c(:)) copyout(b(-1:))",
          "!$acc wait(i,j) async(c)",
          "!$acc kernels loop reduction(+:x)",
          "!$acc parallel loop collapse(3) gang vector copyin(grid%al,grid%alb,grid%pb,grid%t_1) copyin(moist(:,:,:,p_qv))"
        ]
        results = [
          ('!$', ['acc', 'enter', 'data'], [], ['copyin(a,b,c(:))', 'copyout(b(-1:))']),
          ('!$', ['acc', 'wait'], ['i', 'j'], ['async(c)']),
          ('!$', ['acc', 'kernels', 'loop'], [], ['reduction(+:x)']),
          ('!$', ['acc', 'parallel', 'loop'], [], ['collapse(3)', 'gang', 'vector', 'copyin(grid%al,grid%alb,grid%pb,grid%t_1)', 'copyin(moist(:,:,:,p_qv))']),
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_acc_directive(expr))
            self.assertEqual(util.parsing.parse_acc_directive(expr),results[i])
    def test_18_parse_cuf_kernel_call(self):
        expressions = [
          "call mykernel<<<grid,block>>>(arg1,arg2,arg3(1:n))",
          "call mykernel<<<grid,block,0,stream>>>(arg1,arg2,arg3(1:n))",
        ]
        results = [
          ('mykernel',['grid','block'],['arg1','arg2','arg3(1:n)']),
          ('mykernel',['grid','block','0','stream'],['arg1','arg2','arg3(1:n)']),
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_cuf_kernel_call(expr))
            self.assertEqual(util.parsing.parse_cuf_kernel_call(expr),results[i])
    def test_19_mangle_fortran_var_expr(self):
        expressions = [
          "a(i,j)%b%arg3(1:n)",
        ]
        results = [
          "aLijR_b_arg3L1TnR",
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.mangle_fortran_var_expr(expr))
            self.assertEqual(util.parsing.mangle_fortran_var_expr(expr),results[i])
    def test_20_parse_derived_type_statement(self):
        expressions = [
          'type mytype',
          'type :: mytype',
          'type, bind(c) :: mytype',
          'type :: mytype(k,l)',
        ]
        results = [
          ('mytype', [], []),
          ('mytype', [], []),
          ('mytype', ['bind(c)'], []),
          ('mytype', [], ['k','l']),
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_derived_type_statement(expr))
            self.assertEqual(util.parsing.parse_derived_type_statement(expr),results[i])
    
    def test_21_parse_allocate_statement(self):
        expressions = [
          'allocate(a(1:N))',
          'allocate(a(1:N),b(-1:m:2,n))',
          'allocate(a(1:N),b(-1:m:2,n),stat=ierr)',
          'allocate(grid(domain%num,j)%a(1:N))',
        ]
        results = [
          ([('a', [('1', 'N', None)])], None),
          ([('a', [('1', 'N', None)]), ('b', [('-1', 'm', '2'), (None, 'n', None)])], None),
          ([('a', [('1', 'N', None)]), ('b', [('-1', 'm', '2'), (None, 'n', None)])], 'ierr'),
          ([('grid(domain%num,j)%a', [('1', 'N', None)])], None),
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_allocate_statement(expr))
            self.assertEqual(util.parsing.parse_allocate_statement(expr),results[i])
    def test_22_parse_deallocate_statement(self):
        expressions = [
          'deallocate(a)',
          'deallocate(a,b)',
          'deallocate(a,b,stat=ierr)',
          'deallocate(grid(domain%num,j)%a)',
        ]
        results = [
          (['a'], None),
          (['a', 'b'], None),
          (['a', 'b'], 'ierr'),
          (['grid(domain%num,j)%a'], None),
        ]
        for i,expr in enumerate(expressions):
            #print(util.parsing.parse_deallocate_statement(expr))
            self.assertEqual(util.parsing.parse_deallocate_statement(expr),results[i])

if __name__ == '__main__':
    unittest.main() 
