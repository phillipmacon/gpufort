# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import os
import copy
import logging

from gpufort import translator
from gpufort import indexer
from gpufort import scanner
from gpufort import util

from .. import codegen
from . import hipderivedtypegen
from . import hipkernelgen
from . import opts

class HipCodeGenerator(codegen.CodeGenerator):
    """Code generator for generating HIP C++ kernels and kernel launchers
       that can be called from Fortran code."""

    def __init__(self, stree, index, **kwargs):
        r"""Constructor.
        :param stree: Scanner tree created by GPUFORT's scanner component.
        :param index: Index data structure created by GPUFORT's indexer component.
        :param \*\*kwargs: See below.
        
        :Keyword Arguments:

        * *kernels_to_convert* (`list`):
            Filter the kernels to convert to C++ by their name or their id. Pass ['*'] 
            to extract all kernels [default: ['*']]
        * *cpp_file_preamble* (`str`):
            A preamble to write at the top of the files produced by the C++ generators
            that can be created by this class [default: fort2x.opts.cpp_file_preamble].
        * *cpp_file_ext* (`str`):
            File extension for the generated C++ files [default: fort2x.opts.cpp_file_ext].
        * *emit_launcher_interfaces* (``bool``):
            Render **explicit** Fortran interfaces to the generated launchers.
        * *emit_grid_launcher* (``bool``):
            Render a launcher that takes the grid as first argument, defaults to opts value.
        * *emit_problem_size_launcher* (``bool``):
            Render a launcher that takes the problem size as first argument, defaults to opts value.
        * *emit_cpu_launcher* (``bool``):
            Only for loop nests: Render a launcher that runs the original loop nest on the CPU, defaults to opts value
        * *emit_gpu_kernel* (``bool``):
            Emit GPU kernels, defaults to opts value.
        * *emit_debug_code* (``bool``):
            Write debug code such as printing of kernel arguments or device array norms and elements
            into the generated kernel launchers. Defaults to opts value.
        * *emit_interop_types* (``bool``):
            Emit interoperable derived types. Defaults to opts value.
"""
        codegen.CodeGenerator.__init__(self, stree, index, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_debug_code",
                                    opts.emit_debug_code, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_gpu_kernel",
                                    opts.emit_gpu_kernel, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_grid_launcher",
                                    opts.emit_grid_launcher, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_problem_size_launcher",
                                    opts.emit_problem_size_launcher, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_cpu_launcher",
                                    opts.emit_cpu_launcher, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_launcher_interfaces",
                                    opts.emit_launcher_interfaces, **kwargs)
        util.kwargs.set_from_kwargs(self, "emit_interop_types",
                                    opts.emit_interop_types, **kwargs)

    @util.logging.log_entry_and_exit(opts.log_prefix+".HipCodeGenerator")
    def __render_kernel(self,
                        mykernelgen,
                        cpp_filegen,
                        fortran_filegen,
                        is_loopnest=False,
                        is_kernel_subroutine=False):
        if self.emit_gpu_kernel:
            cpp_filegen.rendered_kernels += (
                mykernelgen.render_begin_kernel_comment_cpp()
                + mykernelgen.render_gpu_kernel_cpp()
                + mykernelgen.render_end_kernel_comment_cpp())
        rendered_launchers_cpp = []
        rendered_interfaces_f03 = []
 
        if is_loopnest or is_kernel_subroutine: 
            if self.emit_grid_launcher:
                grid_launcher = mykernelgen.create_launcher_context(
                    "hip", self.emit_debug_code, fortran_filegen.used_modules)
                rendered_launchers_cpp  += mykernelgen.render_gpu_launcher_cpp(grid_launcher)
                rendered_interfaces_f03 += mykernelgen.render_launcher_interface_f03(grid_launcher)
            
            if self.emit_problem_size_launcher:
                problem_size_launcher = mykernelgen.create_launcher_context(
                    "hip_ps", self.emit_debug_code, fortran_filegen.used_modules)
                rendered_launchers_cpp += mykernelgen.render_gpu_launcher_cpp(
                    problem_size_launcher)
                rendered_interfaces_f03 += mykernelgen.render_launcher_interface_f03(
                    problem_size_launcher)

        if is_loopnest and self.emit_cpu_launcher:
            cpu_launcher = mykernelgen.create_launcher_context(
                "cpu", self.emit_debug_code, fortran_filegen.used_modules)
            rendered_launchers_cpp += mykernelgen.render_cpu_launcher_cpp(
                cpu_launcher)
            rendered_interfaces_f03 += mykernelgen.render_launcher_interface_f03(
                cpu_launcher)
            fortran_filegen.rendered_routines += (
                mykernelgen.render_begin_kernel_comment_f03()
                + mykernelgen.render_cpu_routine_f03(cpu_launcher)
                + mykernelgen.render_end_kernel_comment_f03())
       
        if len(rendered_launchers_cpp):
            cpp_filegen.rendered_launchers += (
                mykernelgen.render_begin_kernel_comment_cpp()
                + rendered_launchers_cpp
                + mykernelgen.render_end_kernel_comment_cpp())
       
        if self.emit_launcher_interfaces and len(rendered_interfaces_f03):
            fortran_filegen.rendered_interfaces += (
                mykernelgen.render_begin_kernel_comment_f03()
                + rendered_interfaces_f03
                + mykernelgen.render_end_kernel_comment_f03())

    @util.logging.log_entry_and_exit(opts.log_prefix+".HipCodeGenerator")
    def _render_loop_nest(self, stloopnest, cpp_filegen, fortran_filegen):
        """:note: Writes back to stloopnest argument.
        """
        scope = indexer.scope.create_scope(self.index, stloopnest.parent.tag())

        # TODO 
        # clause analysis needed to derive kernel arguments
        # if derived type access in kernel
        # Further tree modification required if no parent type is passed down
        # but an error expression instead

        try:
            mykernelgen = hipkernelgen.HipKernelGenerator4LoopNest(
                stloopnest.parse_result, scope,
                kernel_name = stloopnest.kernel_name(),
                kernel_hash = stloopnest.kernel_hash(),
                fortran_snippet = "".join(stloopnest.lines()))
        
            self.__render_kernel(mykernelgen,
                                 self.cpp_filegen,
                                 fortran_filegen,
                                 is_loopnest=True)
            # feed back arguments; TODO see above
            stloopnest.kernel_args_tavars = mykernelgen.get_kernel_args()

            stloopnest.problem_size = mykernelgen.problem_size
            stloopnest.block_size = mykernelgen.block_size
        except (util.error.SyntaxError, util.error.LimitationError, util.error.LookupError) as e:
            msg = "{}:[{}-{}]:{}".format(
                    stloopnest._linemaps[0]["file"],stloopnest.min_lineno(),stloopnest.max_lineno(),e.args[0])
            e.args = (msg,)
            raise

    @util.logging.log_entry_and_exit(opts.log_prefix+".HipCodeGenerator")
    def _render_device_procedure(self, stprocedure, cpp_filegen, fortran_filegen):
        iprocedure = stprocedure.index_record
        kernel_name = iprocedure["name"]
        scope = indexer.scope.create_scope(self.index, stprocedure.tag())
        try:
            if stprocedure.is_kernel_subroutine():
                mykernelgen = hipkernelgen.HipKernelGenerator4CufKernel(
                    stprocedure.parse_result, iprocedure, scope,
                    kernel_name = iprocedure["name"],
                    kernel_hash = "", 
                    fortran_snippet = "".join(stprocedure.lines()))

                self.__render_kernel(mykernelgen,
                                     self.cpp_filegen,
                                     fortran_filegen,
                                     is_kernel_subroutine=True)
            else:
                mykernelgen = hipkernelgen.HipKernelGenerator4AcceleratorRoutine(
                    stprocedure.parse_result, iprocedure, scope,
                    kernel_name = iprocedure["name"],
                    kernel_hash = "", 
                    return_type = stprocedure.c_result_type,
                    fortran_snippet = "".join(stprocedure.lines()))

                # might be used and inlined (assumption) in other modules!
                self.__render_kernel(mykernelgen,
                                     cpp_filegen,
                                     fortran_filegen)
            
            stprocedure.kernel_args_tavars = mykernelgen.get_kernel_args()
        except (util.error.SyntaxError, util.error.LimitationError, util.error.LookupError) as e:
            msg = "{}:[{}-{}]:{}".format(
                    stloopnest._linemaps[0]["file"],stloopnest.min_lineno(),stloopnest.max_lineno(),e.args[0])
            e.args = (msg,)
            raise

    @util.logging.log_entry_and_exit(opts.log_prefix+".HipCodeGenerator")
    def _render_derived_types(self, itypes, cpp_filegen, fortran_modulegen):
        if self.emit_interop_types:
            derivedtypegen = hipderivedtypegen.HipDerivedTypeGenerator(itypes, [])
            cpp_filegen.rendered_types += derivedtypegen.render_derived_type_definitions_cpp(
            )
            fortran_modulegen.rendered_types += derivedtypegen.render_derived_type_definitions_f03(
            )
            fortran_modulegen.rendered_routines += derivedtypegen.render_derived_type_routines_f03(
            )
