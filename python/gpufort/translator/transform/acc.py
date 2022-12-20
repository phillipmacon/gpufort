# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
from .. import tree

from . import loops

label_generator = loops.unique_label

def _label_array_buffer(name):
    return "_"+name+"_buffer"

def _label_firstprivate_argument(name):
    return "_"+name+"_at_init"

def _derive_private_decl_nodes(var_name,symbol_info):
    if symbol_info.rank > 0:
        buffer_name = _label_array_buffer(var_name)
        return [
          tree.TTCVarDeclFromFortranSymbol(buffer_name,symbol_info),
          TTCGpufortArrayPtrDecl(var_name,symbol_info),
          TTCGpufortArrayPtrWrap(var_name,buffer_name,symbol_info),
        ]
    else:
        return [
          tree.TTCVarDeclFromFortranSymbol(var_name,symbol_info),
        ]

def _inject_private_var_decls(ttcontainer,var_list):
    """:note: Assumes semantics check has been performed on all variables.
    """
    new_nodes = []
    for ttvalue in var_list:
        new_nodes += _derive_private_decl_nodes(
          ttvalue.name,ttvalue.symbol_info
        )
    for node in reversed(new_nodes):
        ttcontainer.body.insert(0,node)

def _inject_firstprivate_var_decls(ttcontainer,var_list):
    """:note: Assumes semantics check has been performed on all variables.
    """
    new_nodes = []
    for ttvalue in ttvalue_list:
        new_nodes += _derive_private_decl_nodes(
          ttvalue.name,ttvalue.symbol_info
        )
        src_name = _label_firstprivate_argument(ttvalue.name),
        if ttvalue.rank > 0:
            new_nodes.append(
              tree.TTCCopyForLoop(# dest,src,idx,n
                ttvalue.name,
                src_name,
                label_generator("idx"),
                ttvalue.symbol_info.size_expr.cstr()
              )
            )
        else:
            new_nodes.append(
              tree.TTCCopyStatement(ttvalue.name,src_name)
            ) 
    for node in reversed(new_nodes):
        ttcontainer.body.insert(0,node)

def _inject_reduction_var_decls(ttcontainer,op,var_list):
    """:note: Assumes semantics check has been performed on all variables.
    """
    new_nodes += _derive_private_decl_nodes(
      ttvalue.name,ttvalue.symbol_info
    )

def _traverse_acc_compute_construct(self,ttaccdir,device_type):
    """:note: Syntax checks prevent that num_gangs, num_workers, and
              vector_length can be specified for TTAccSerial.
    """
    private_vars = [] 
    first_private_vars = []
    if isinstance(ttaccdir,tree.TTAccSerial):
        max_num_gangs = "1"    
        max_num_workers = "1"    
        max_vector_length = "1"    
    else:
        max_num_gangs = None    
        max_num_workers = None    
        max_vector_length = None    
    for clause in ttaccdir.walk_clauses_device_type(device_type):
        if isinstance(clause,tree.TTAccClauseNumGangs):
            if clause.arg_specified:
                max_num_gangs = clause.arg
        elif isinstance(clause,tree.TTAccClauseNumWorkers):
            if clause.arg_specified:
                max_num_workers = clause.arg
        elif isinstance(clause,tree.TTAccClauseVectorLength):
            if clause.arg_specified:
                max_vector_length = clause.arg
        elif isinstance(clause,tree.TTAccClausePrivate):
            private_vars = clause.var_list 
            generated_code += render.render_private_vars_decl_list(
              ttvalues,scope
            )
        elif isinstance(clause,tree.TTAccClauseFirstprivate):
            firstprivate_vars = clause.var_list
    #self._result.generated_code += loops.render_hip_kernel_prolog_acc()
    #self._compute_construct = ttaccdir 
    return ... # TODO return subst
        

def unroll_all_acc_directives(ttcontainer,device_type):
    """Recursively unrolls all OpenACC constructs,
    found in the container, descends into every
    container statement in the body.
    :param str device_type: The device type identifier for
    which to perform the transformation.
    :note: Assumes that semantics checks have been performed.
    :note: Propagates (assignment, function call) statement filter down from the top
           of the tree to the leaves
    """
    newbody = [] # shallow copy
    statement_filter = "<filter>" # todo
    statement_filter_node = None
    # todo reduce resources here too
    last = -1
    for i,ttstmt in enumerate(ttcontainer.body):
         # pre-process
         if isinstance(ttstmt,(tree.TTAccParallelLoop,tree.TTAccKernelsLoop)):
            if isinstance(ttstmt,tree.TTAccKernelsLoop):
                new_acc_construct = ttstmt.acc_kernels()
            else:
                new_acc_construct = ttstmt.acc_parallel()
            new_acc_loop = ttstmt.acc_loop()
            new_acc_construct.append(new_acc_loop)
            new_acc_loop.body = list(ttstmt.body)
            ttstmt = TTSubstContainer(stmt)
            ttstmt.append(new_acc_construct)
        elif isinstance(ttsmt,tree.TTAccLoop):
            # update statement activation mask
            pass
        # statement filtering
        if isinstance(ttstmt,(
            tree.TTAssignment,
            tree.TTUnrolledArrayAssignment,
            tree.TTSubroutineCall, # subroutine call must be masked in OpenACC context, is always masked in CUF context, 
                                   # see rule on acc routine clauses,
                                   # * acc routine worker may not be called from worker and vector but only from gang-part./red. region
                                   # * acc routine vector may not be called from vector but only from gang-part./red. and worker-part. region
                                   # * acc routine seq may only be called from gang-part/-red. and worker-/vector-part. regions 
          )):
            if statement_filter_node == None:
                statement_filter_node = TTCElseIf(statement_filter)
            statement_filter_node.body.append(ttstmt)
        else:
            if statement_filter_node == None:
                newbody.append(statement_filter_node)
            newbody.append(ttstmt)
        # descend
        if isinstance(ttstmt,tree.TTContainer):
            unroll_all_acc_directives(ttstmt,device_type)
        # ascend, post process
        if isinstance(ttstmt,tree.TTAccSerial):
           # resource limitations
           # no reduction
           newbody[i] = subst
        if isinstance(ttstmt,tree.TTAccParallel):
           # resource limitations
           # no reduction
           newbody[i] = subst
        elif isinstance(ttstmt,tree.TTAccKernels):
           # resource limitations
           # no reduction
           newbody[i] = subst
        elif isinstance(ttstmt,tree.TTAccLoop):
           # resource limitations
           # update filter
           subst = tree.TTSubstLoopDirective(ttstmt)
           subst.body = list(orig.body) # shallow copy
           newbody[i] = subst
    #
    ttcontainer.body = newbody
