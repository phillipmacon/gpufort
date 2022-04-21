# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import textwrap

from gpufort import util
from gpufort import translator
from gpufort import indexer

from ... import opts

from .. import nodes
from .. import backends

from . import accbackends
from . import accnodes

# update
_ACC_UPDATE = "call gpufort_acc_update_{kind}({var}{options})\n"
# wait
_ACC_WAIT = "call gpufort_acc_wait({queue}{options})\n"
# init shutdown
_ACC_INIT = "call gpufort_acc_init()\n"
_ACC_SHUTDOWN = "call gpufort_acc_shutdown()\n"
# regions
_ACC_ENTER_REGION = "call gpufort_acc_enter_region({options})\n"
_ACC_EXIT_REGION = "call gpufort_acc_exit_region({options})\n"

# clauses
_ACC_CREATE = "call gpufort_acc_ignore(gpufort_acc_create({var}))\n"
_ACC_NO_CREATE = "call gpufort_acc_ignore(gpufort_acc_no_create({var}))\n"
_ACC_PRESENT = "call gpufort_acc_ignore(gpufort_acc_present({var}{options}))\n"
_ACC_DELETE = "call gpufort_acc_delete({var}{options})\n"
_ACC_COPY = "call gpufort_acc_ignore(gpufort_acc_copy({var}{options}))\n"
_ACC_COPYIN = "call gpufort_acc_ignore(gpufort_acc_copyin({var}{options}))\n"
_ACC_COPYOUT = "call gpufort_acc_ignore(gpufort_acc_copyout({var}{options}))\n"
_ACC_PRESENT_OR_CREATE = "call gpufort_acc_ignore(gpufort_acc_present_or_create({var}{options}))\n"
_ACC_PRESENT_OR_COPYIN = "call gpufort_acc_ignore(gpufort_acc_present_or_copyin({var}{options}))\n"
_ACC_PRESENT_OR_COPYOUT = "call gpufort_acc_ignore(gpufort_acc_present_or_copyout({var}{options}))\n"
_ACC_PRESENT_OR_COPY = "call gpufort_acc_ignore(gpufort_acc_present_or_copy({var}{options}))\n"
_ACC_USE_DEVICE = "gpufort_acc_use_device({var},lbound({var}){options})\n"

_DATA_CLAUSE_2_TEMPLATE_MAP = {
  "create": _ACC_CREATE,
  "no_create": _ACC_NO_CREATE,
  "delete": _ACC_DELETE,
  "copyin": _ACC_COPYIN,
  "copyout": _ACC_COPYOUT,
  "copy": _ACC_COPY,
  "present": _ACC_PRESENT,
  "present_or_create": _ACC_PRESENT_OR_CREATE,
  "present_or_copyin": _ACC_PRESENT_OR_COPYIN,
  "present_or_copyout": _ACC_PRESENT_OR_COPYOUT,
  "present_or_copy": _ACC_PRESENT_OR_COPY,
}
        
_DATA_CLAUSES_WITH_ASYNC = [
    "present",
    "copyin","copy","copyout",
    "present_or_copyin","present_or_copy","present_or_copyout",
  ]
_DATA_CLAUSES_WITH_FINALIZE = ["delete"] 

_CLAUSES_OMP2ACC = {
  "alloc": "create",
  "to": "copyin",
  "tofrom": "copy"
}

def _create_options_str(options,prefix=""):
    while(options.count("")):
      options.remove("")
    if len(options):
        return "".join([",",",".join(options)])
    else:
        return ""


class Acc2HipGpufortRT(accbackends.AccBackendBase):
    
    def _get_finalize_clause_expr(self):
        finalize_present = self.stnode.has_finalize_clause()
        finalize_expr = ""
        if finalize_present:
            finalize_expr = "finalize=True"
        return finalize_expr
    
    def _get_async_clause_expr(self):
        async_queue, async_present = self.stnode.get_async_clause_queue()
        async_expr = ""
        if async_present and async_queue!=None:
            async_expr = "async={}".format(async_queue)
        elif async_present and async_queue==None:
            async_expr = "async=0"
        return async_expr

    def _handle_wait_clause(self):
        result = []
        wait_queues, wait_present = self.stnode.get_wait_clause_queues()
        wait_expr = ""
        if wait_present and not len(wait_queues):
            result.append(_ACC_WAIT.format(queue="",options=""))
        elif wait_present and len(wait_queues):
            result.append(_ACC_WAIT.format(queue=",".join(wait_queues),options=""))
        return result
 
    def _handle_data_clauses(self,index,async_expr,finalize_expr):
        result = [] 
        #
        for kind, args in self.stnode.get_matching_clauses(_DATA_CLAUSE_2_TEMPLATE_MAP.keys()):
            options = []
            if kind in _DATA_CLAUSES_WITH_ASYNC:
                options.append(async_expr)
            if kind in _DATA_CLAUSES_WITH_FINALIZE:
                options.append(finalize_expr)
            for var_expr in args:
                template = _DATA_CLAUSE_2_TEMPLATE_MAP[kind.lower()]
                options_str =_create_options_str(options)
                result.append(template.format(var=var_expr,options=options_str))
                if not opts.acc_map_derived_types: 
                    ivar = indexer.scope.search_index_for_var(index,self.stnode.parent.tag(),var_expr)
                    if ivar["f_type"] == "type":
                        result.pop(-1)
        return result

    def _handle_if_clause(self,result):
        condition, found_if = self.stnode.get_if_clause_condition()
        if found_if:
            result = [textwrap.dedent(l," "*2) for l in result]
            result.insert(0,"if ( {} ) then\n".format(condition))
            result.append("endif\n".format(condition))
    
    def _update_directive(self,index,async_expr):
        """Emits a acc_clause_update command for every variable in the list
        """
        #if self.stnode.is_directive(["acc","update"]):
        result = []
        options = [ async_expr ]
        for kind, args in self.stnode.get_matching_clauses(["if","if_present"]):
            if kind == "if":
                options.append("=".join(["condition",args[0]]))
            elif kind == "if_present":
                options.append("if_present=.true.")
        for kind, args in self.stnode.get_matching_clauses(["self", "host", "device"]):
            for var_expr in args:
                result.append(_ACC_UPDATE.format(
                    var=var_expr,
                    options=_create_options_str(options),
                    kind=kind.lower()))
                if not opts.acc_map_derived_types: 
                    tag = indexer.scope.create_index_search_tag_for_var(var_expr)
                    ivar = indexer.scope.search_index_for_var(index,self.stnode.parent.tag(),tag)
                    if ("%" in tag and ivar["rank"] == 0
                       or ivar["f_type"] == "type"):
                            result.pop(-1)
        return result
    
    def _host_data_directive(self):
        """Emits an associate statement with a mapping
        of each host variable to the mapped device array.
        """
        mappings = []
        options = []
        for kind, args in self.stnode.get_matching_clauses(["if","if_present"]):
            if kind == "if":
                options.append("=".join(["condition",args[0]]))
            elif kind == "if_present":
                options.append("if_present=.true.")
        for kind, args in self.stnode.get_matching_clauses(["use_device"]):
            for var_expr in args:
                mappings.append(" => ".join([
                  var_expr,
                  _ACC_USE_DEVICE.format(var=var_expr,
                    options=_create_options_str(options)).rstrip(),
                  ]))
        result = []
        if len(mappings):
            result.append("associate (&\n")
            for mapping in mappings[:-1]:
                result.append("".join(["  ",mapping,",","&\n"]))
            result.append("".join(["  ",mappings[-1],"&\n"]))
            result.append(")\n")
        return result
    
    def _end_host_data_directive(self,async_expr):
        """Emits a acc_clause_update command for every variable in the list
        """
        #if self.stnode.is_directive(["acc","update"]):
        result = [""]
        return result

    def _wait_directive(self):
        """Emits an acc_wait  command for every variable in the list
        """
        result = []
        queues = self.stnode.directive_args
        asyncr_list = []
        for kind, args in self.stnode.get_matching_clauses(["async"]):
            for var_expr in args:
                asyncr_list.append(var_expr)
        queue = ""
        asyncr = ""
        if len(queues):
            queue = "[{}]".format(",".join(queues))
        if len(asyncr_list):
            asyncr = ",[{}]".format(",".join(asyncr_list))
        result.append(_ACC_WAIT.format(queue=queue,
                                       options=asyncr))
        return result

    def transform(self,
                  joined_lines,
                  joined_statements,
                  statements_fully_cover_lines,
                  index=[],
                  handle_if=True):
        """
        :param line: An excerpt from a Fortran file, possibly multiple lines
        :type line: str
        :return: If the text was changed at all
        :rtype: bool
        """
        result = []

        stnode = self.stnode
        if stnode.is_directive(["acc","init"]):
            result.append(_ACC_INIT)
        elif stnode.is_directive(["acc","shutdown"]):
            result.append(_ACC_SHUTDOWN)
        elif stnode.is_directive(["acc","update"]):
            result += self._handle_wait_clause()
            async_expr = self._get_async_clause_expr()
            result += self._update_directive(index,async_expr)
        elif stnode.is_directive(["acc","wait"]):
            result += self._wait_directive()
        elif stnode.is_directive(["acc","host_data"]):
            result += self._host_data_directive()
        elif stnode.is_directive(["acc","end","host_data"]):
            result.append("end associate")
        elif (stnode.is_directive(["acc","end","parallel"])
             or stnode.is_directive(["acc","end","parallel","loop"])
             or stnode.is_directive(["acc","end","kernels","loop"])):
            pass
        elif (stnode.is_directive(["acc","parallel"])
             or stnode.is_directive(["acc","parallel","loop"])
             or stnode.is_directive(["acc","kernels","loop"])):
            assert False, "should not be called for parallel (loop) and kernels loop directive"
        elif (stnode.is_directive(["acc","end","kernels"])
             or stnode.is_directive(["acc","end","data"])):
            result.append(_ACC_EXIT_REGION.format(
                options=""))
        # data regions
        elif stnode.is_directive(["acc","enter","data"]):
            result += self._handle_wait_clause()  
            result.append(_ACC_ENTER_REGION.format(
                options="unstructured=.true."))
        elif stnode.is_directive(["acc","data"]):
            result.append(_ACC_ENTER_REGION.format(
                options=""))
        elif stnode.is_directive(["acc","kernels"]):
            result += self._handle_wait_clause()  
            result.append(_ACC_ENTER_REGION.format(
                options=""))

        ## mapping clauses on data and kernels directives
        if (stnode.is_directive(["acc","enter","data"])
           or stnode.is_directive(["acc","exit","data"])
           or stnode.is_directive(["acc","data"])
           or stnode.is_directive(["acc","kernels"])):
            async_expr = self._get_async_clause_expr()
            finalize_expr = self._get_finalize_clause_expr();
            if len(finalize_expr) and not stnode.is_directive(["acc","exit","data"]):
                raise util.error.SyntaxError("finalize clause may only appear on 'exit data' directive.")
            result += self._handle_data_clauses(index,async_expr,finalize_expr)

        ## Exit region commands must come last
        if stnode.is_directive(["acc","exit","data"]):
            result.append(_ACC_EXIT_REGION.format(
                options="unstructured=.true."))
        # _handle if
        if handle_if:
            self._handle_if_clause(result)

        indent = stnode.first_line_indent()
        return textwrap.indent("".join(result),indent), len(result)

class AccComputeConstruct2HipGpufortRT(Acc2HipGpufortRT):

    def _map_array(clause_kind1,var_expr,tavar,**kwargs):
        asyncr,_   = util.kwargs.get_value("asyncr","",**kwargs)
        finalize,_ = util.kwargs.get_value("finalize","",**kwargs)
        prepend_present,_ = util.kwargs.get_value("prepend_present",False,**kwargs)       

        if prepend_present and clause_kind1.startswith("copy"):
            clause_kind = "".join(["present_or_",clause_kind1])
        else:
            clause_kind = clause_kind1
        if clause_kind in _DATA_CLAUSE_2_TEMPLATE_MAP:
            runtime_call_tokens = ["gpufort_acc_",clause_kind,"("]
            runtime_call_tokens.append(var_expr)
            if len(asyncr) and clause.kind in _DATA_CLAUSES_WITH_ASYNC:
                runtime_call_tokens += [",",asyncr]
            if len(finalize) and clause.kind in _DATA_CLAUSES_WITH_FINALIZE:
                runtime_call_tokens += [",",finalize]
            runtime_call_tokens.append(")") 
            tokens = [
              "gpufort_array",str(tavar["c_rank"]),"_wrap_device_cptr(&\n",
              " "*4,"".join(runtime_call_tokens),
              ",shape(",var_expr,",kind=c_int),lbound(",var_expr,",kind=c_int))",
            ]
            return "".join(tokens)
        else:
            raise util.parsing.SyntaxError("clause not supported") 
    
    def derive_kernel_call_arguments(self):
        """:return a list of arguments given the directives.
        """
        result = []
        acc_clauses = self.stnode.get_matching_clauses(_DATA_CLAUSE_2_TEMPLATE_MAP)
        
        kwargs = {
          "finalize":self._get_finalize_clause_expr(),
          "asyncr":self._get_async_clause_expr(),
        }
        if self.stnode.is_directive(["acc","kernels"]):
            kwargs["prepend_present"] = True
        mappings = translator.analysis.kernel_args_to_acc_mappings_no_types(
                       acc_clauses,
                       self.stnode.kernel_args_tavars,
                       self.stnode.get_vars_present_per_default(),
                       AccComputeConstruct2HipGpufortRT._map_array,
                       **kwargs)
        for var_expr, argument in mappings:
            result.append(argument)
        return result
        
    def transform(self,
                  joined_lines,
                  joined_statements,
                  statements_fully_cover_lines,
                  index=[]):
        result = []
        stloopnest = self.stnode
        ttloopnest = stloopnest.parse_result
        
        # if kernels loop / parallel / parallel loop -> enter_region
        # if kernels -> do not emit enter_region
        emit_enter_exit_region = \
           (stloopnest.is_directive(["acc","kernels","loop"])
           or stloopnest.is_directive(["acc","kernels","loop"])
           or stloopnest.is_directive(["acc","parallel","loop"]))
        
        if emit_enter_exit_region:
            result += self._handle_wait_clause()  
            result.append(_ACC_ENTER_REGION.format(
                options=""))
        
        queue, found_async = stloopnest.get_async_clause_queue()
        if not found_async:
            queue = "0"
        stloopnest.stream_f_str = "gpufort_acc_get_stream({})".format(queue)
        stloopnest.async_launch_f_str = ".{}.".format(str(found_async)).lower()
       
        stloopnest.kernel_args_names = self.derive_kernel_call_arguments()
        result_loopnest, _ = nodes.STComputeConstruct.transform(
                                 stloopnest, joined_lines, joined_statements,
                                 statements_fully_cover_lines, index)
        result.append(textwrap.dedent(result_loopnest))
        
        if emit_enter_exit_region:
            result.append(_ACC_EXIT_REGION.format(options=""))
        
        self._handle_if_clause(result)

        indent = stloopnest.first_line_indent()
        return textwrap.indent("".join(result),indent), len(result)

@util.logging.log_entry_and_exit(opts.log_prefix)
def _add_implicit_region(stcontainer):
    stcontainer.append_to_decl_list([_ACC_ENTER_REGION.format(\
        options="implicit_region=.true.")])
    stcontainer.prepend_to_return_or_end_statements([_ACC_EXIT_REGION.format(\
            options="implicit_region=.true.")])

def AllocateHipGpufortRT(stallocate, joined_statements, index):
    stcontainer = stallocate.parent
    parent_tag = stcontainer.tag()
    scope = indexer.scope.create_scope(index, parent_tag)
    scope_vars = scope["variables"]
    indent = stallocate.first_line_indent()
    local_var_names, dummy_arg_names = stcontainer.local_and_dummy_var_names(
        index)
    acc_present_calls = []
    implicit_region = False
    for var in [a[0] for a in stallocate.allocations]:
        ivar = indexer.scope.search_index_for_var(index, parent_tag, var)
        if opts.acc_map_derived_types or ivar["f_type"] != "type":
            var_expr = ivar["name"]
            is_local_var = var_expr in local_var_names
            is_arg = var_expr in dummy_arg_names
            is_used_module_var = not is_local_var and not is_arg
            is_allocatable_or_pointer = "allocatable" in ivar["qualifiers"] or\
                                 "pointer" in ivar["qualifiers"]
            assert is_allocatable_or_pointer # TODO emit error
            module_var = ",module_var=.true." if is_used_module_var else ""
            if not is_used_module_var:
                implicit_region = True
            declare = ivar["declare_on_target"]
            if declare in _CLAUSES_OMP2ACC.keys():
                map_kind = "".join(["present_or_",_CLAUSES_OMP2ACC[declare]])
                acc_present_template =  _DATA_CLAUSE_2_TEMPLATE_MAP[map_kind]
                acc_present_calls.append(acc_present_template.format(
                    var=var_expr,options=module_var))
    if len(acc_present_calls):
        if implicit_region:
            _add_implicit_region(stcontainer)
        for line in acc_present_calls:
            stallocate.add_to_epilog(textwrap.indent(line,indent))
    return joined_statements, False


def DeallocateHipGpufortRT(stdeallocate, joined_statements, index):
    stcontainer = stdeallocate.parent
    parent_tag = stcontainer.tag()
    scope = indexer.scope.create_scope(index, parent_tag)
    scope_vars = scope["variables"]
    indent = stdeallocate.first_line_indent()
    local_var_names, dummy_arg_names = stcontainer.local_and_dummy_var_names(
        index)
    acc_delete_calls = []
    for var in stdeallocate.variable_names:
        ivar = indexer.scope.search_index_for_var(index, parent_tag, var)
        if opts.acc_map_derived_types or ivar["f_type"] != "type":
            var_expr = ivar["name"]
            is_local_var = var_expr in local_var_names
            is_arg = var_expr in dummy_arg_names
            is_used_module_var = not is_local_var and not is_arg
            is_allocatable_or_pointer = "allocatable" in ivar["qualifiers"] or\
                                 "pointer" in ivar["qualifiers"]
            assert is_allocatable_or_pointer
            module_var = ",module_var=.true." if is_used_module_var else ""
            if ivar["declare_on_target"] in ["alloc", "to", "tofrom"]:
                acc_delete_calls.append(_ACC_DELETE.format(\
                  var=var_expr,options=module_var))
    for line in acc_delete_calls:
        stdeallocate.add_to_prolog(textwrap.indent(line,indent))
    return joined_statements, False


def Acc2HipGpufortRTPostprocess(stree, index):
    """:param stree: the full scanner tree
       :param staccdirectives: All acc directive tree accnodes."""
    accbackends.add_runtime_module_use_statements(stree,"gpufort_acc_runtime")

    # TODO check if there is any acc used in the
    # construct at all
    # TODO handle directly via directives; only variables occuring
    # in directives need to be available on device
    containers = stree.find_all(\
      lambda node: type(node) in [nodes.STProgram,nodes.STProcedure],
      recursively=True)
    for stcontainer in containers:
        last_decl_list_node = stcontainer.last_entry_in_decl_list()
        indent = last_decl_list_node.first_line_indent()
        scope = indexer.scope.create_scope(index, stcontainer.tag())
        scope_vars = scope["variables"]
        local_var_names, dummy_arg_names = stcontainer.local_and_dummy_var_names(
            index)
        # TODO also process type members
        acc_present_calls = []
        implicit_region = False
        for ivar in scope_vars:
            var_expr = ivar["name"]
            if opts.acc_map_derived_types or ivar["f_type"] != "type":
                is_local_var = var_expr in local_var_names
                is_arg = var_expr in dummy_arg_names
                is_used_module_var = not is_local_var and not is_arg
                is_allocatable = "allocatable" in ivar["qualifiers"]
                is_pointer = "pointer" in ivar["qualifiers"]
                if not is_allocatable:
                    if not is_used_module_var:
                        implicit_region = True
                    module_var = ",module_var=.true." if is_used_module_var else ""
                    # find return and end, emit 1 new implicit region for all
                    declare = ivar["declare_on_target"]
                    if declare in _CLAUSES_OMP2ACC.keys():
                        map_kind = "".join(["present_or_",_CLAUSES_OMP2ACC[declare]])
                        acc_present_template =  _DATA_CLAUSE_2_TEMPLATE_MAP[map_kind]
                        if is_pointer:
                            acc_present_template = "".join(["if (associated({var})) ",acc_present_template])
                        acc_present_calls.append(acc_present_template.format(
                            var=var_expr,options=module_var))
        if len(acc_present_calls):
            if implicit_region:
                _add_implicit_region(stcontainer)
            last_decl_list_node.add_to_epilog(textwrap.indent("".join(acc_present_calls),indent))

dest_dialects = ["hipgpufort"]
accnodes.STAccDirective.register_backend(dest_dialects,Acc2HipGpufortRT()) # instance
accnodes.STAccComputeConstruct.register_backend(dest_dialects,AccComputeConstruct2HipGpufortRT())

nodes.STAllocate.register_backend("acc", dest_dialects, AllocateHipGpufortRT) # function
nodes.STDeallocate.register_backend("acc", dest_dialects, DeallocateHipGpufortRT)

backends.supported_destination_dialects.add("hipgpufort")
backends.register_postprocess_backend("acc", dest_dialects, Acc2HipGpufortRTPostprocess)
