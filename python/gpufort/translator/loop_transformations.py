import copy
import textwrap
   
single_level_indent = " "*2

def reset():
  _counters.clear()

hip_kernel_prolog =\
""""\
gpufort::acc_grid _res(gridDim.x,div_round_up(blockDim.x/warpSize),{max_vector_length});
gpufort::acc_coords _coords(gang_id,worker_id,vector_lane_id);
"""

_counters = {}
 
def _unique_label(label: str):
    """Returns a unique label for a loop variable that describes
    a loop entity. The result is prefixed with "_" to
    prevent collisions with Fortran variables.
    """
    if label not in _counters:
        _counters[label] = 0
    counter = _counters[label]
    _counters[label] += 1
    return "_"+label+str(counter)

def _render_const_int_decl(lhs,rhs):
    return "const int {} = {};\n".format(lhs,rhs)

def _render_tile_size_var_decl(tile_size_var,loop_len,num_tiles):
    """:return: C++ expression (str) that introduces a tile size var based
    on a loop length and a number of tiles.
    """
    rhs = "{fun}({loop_len},{num_tiles})".format(
              fun="gpufort::div_round_up",
              loop_len=loop_len,
              num_tiles=num_tiles)
    return _render_const_int_decl(tile_size_var,rhs)

def _render_for_loop_open(index,incl_lbound,excl_ubound,step=None):
  if step == None:
      template = """\
for ({0} = {1}; 
     {0} < {2}; {0}++) {{
"""
  else:
      template = """\
for ({0} = {1};
     {0} < {2}; {0} += {3}) {{
"""
  return template.format(index,incl_lbound,excl_ubound,step)

class Loop:
    
    def __init__(self,
          index,
          first,
          last = None,
          length = None,
          excl_ubound = None,
          step = None,
          gang_partitioned = False,
          worker_partitioned = False,
          vector_partitioned = False,
          num_gangs = None,
          num_workers = None,
          vector_length = None,
          prolog = None,
          body_prolog = None):
        self.index = index.strip()
        self.first = first.strip()
        self._last = last
        self._length = length
        self._excl_ubound = excl_ubound
        self.step = step
        self.gang_partitioned = gang_partitioned
        self.worker_partitioned = worker_partitioned
        self.vector_partitioned = vector_partitioned
        self.num_workers = num_workers
        self.num_gangs = num_gangs
        self.vector_length = vector_length
        self.prolog = prolog
        self.body_prolog = body_prolog
        self.body_indent_levels = 1

    def last(self):
        assert (self._length != None 
               or self._last != None
               or self._excl_ubound != None), "one of self._length, self._last, self._excl_ubound must not be None"
        if self._last != None:
            return self._last
        elif self._excl_ubound != None:
            return "({} - 1)".format(self._excl_ubound)
        else:
            return "({} + {} - 1)".format(self.first,self._length)
        
    def excl_ubound(self):
        assert (self._length != None 
               or self._last != None
               or self._excl_ubound != None), "one of self._length, self._last, self._excl_ubound must not be None"
        if self._excl_ubound != None:
            return self._excl_ubound
        elif self._last != None:
            return "({} + 1)".format(self._last)
        else:
            if self.step != None and self.step.strip() != "1":
                step_str = "("+self.step+")*"
            else:
                step_str = ""
            if self.first == "0":
                return step_str + self._length
            else:
                return "({} + {}{})".format(self.first,step_str,self._length)

    def length(self):
        assert (self._length != None 
               or self._last != None
               or self._excl_ubound != None), "one of self._length, self._last, self._excl_ubound must not be None"
        if self._length != None:
            return self._length
        else:
            gpufort_fun = "gpufort::loop_len"
            if self.step == None:
                return "{}({},{})".format(
                  gpufort_fun,
                  self.first,self.last())
            else:
                return "{}({},{},{})".format(
                  gpufort_fun,
                  self.first,self.last(),self.step)


    def _is_normalized_loop(self):
        return (
                 self.first == "0" 
                 and (
                       self.step == None
                       or self.step.strip() == "1"
                     )
                )

    def _render_index_recovery(self,first,step,normalized_index):
        """:return: Expression that computes an original loop index
        from the normalized index, which runs from 0 to the length
        of the original loop, and the `first` index and `step` size
        of the original loop. 
        """
        if first != "0":
            result = first+" + "
        else:
            result = ""
        if step != None:
            result += "({})*{}".format(
              step,
              normalized_index
            )
        else: 
            result += normalized_index
        return result
    
    def tile(self,tile_size,tile_loop_index=None):
        """
        :param tile_loop_index: Index to use for the loop over the tiles,
                                chosen automatically if None is passed.
        """
        # tile loop
        orig_len_var = _unique_label("len")
        tile_loop_prolog = _render_const_int_decl( 
            orig_len_var,
            self.length()
        )
        num_tiles = "gpufort::div_round_up({loop_len},{tile_size})".format(
          loop_len=orig_len_var,
          tile_size=tile_size
        )
        num_tiles_var = _unique_label("num_tiles")
        tile_loop_prolog += _render_const_int_decl( 
            num_tiles_var,
            num_tiles
        )
        if tile_loop_index == None:
            tile_loop_index = _unique_label("tile")
        tile_loop = Loop(
            index = tile_loop_index,
            first = "0",
            length = num_tiles_var,
            excl_ubound = num_tiles_var,
            step = None,
            gang_partitioned = self.gang_partitioned,
            worker_partitioned = not self.vector_partitioned and self.worker_partitioned,
            vector_partitioned = self.vector_partitioned,
            num_gangs = self.num_gangs,
            num_workers = self.num_workers if self.vector_partitioned else None,
            vector_length = self.vector_length,
            prolog=tile_loop_prolog)
        # element_loop
        element_loop_index = _unique_label("elem")
        normalized_index_var = _unique_label("idx")
        element_loop_body_prolog = _render_const_int_decl( 
          normalized_index_var,
          "{} + ({})*{}".format(
            element_loop_index,
            tile_size,
            tile_loop_index
          )
        )
        element_loop_body_prolog += "if ( {normalized_index} < {orig_len} ) {{\n".format(
          normalized_index=normalized_index_var,
          orig_len=orig_len_var
        )
        element_loop_body_prolog += single_level_indent
        # recover original index
        element_loop_body_prolog +=_render_const_int_decl( 
          self.index,
          self._render_index_recovery(
            self.first,self.step,normalized_index_var
          )
        )
        element_loop = Loop(
            index = element_loop_index,
            first = "0",
            length = tile_size,
            excl_ubound = tile_size,
            step = self.step,
            gang_partitioned = False,
            worker_partitioned = not self.vector_partitioned and self.worker_partitioned,
            vector_partitioned = self.vector_partitioned,
            num_gangs = self.num_gangs,
            num_workers = self.num_workers if not self.vector_partitioned else None,
            vector_length = self.vector_length,
            body_prolog = element_loop_body_prolog)
        element_loop.body_indent_levels = 2
        return (tile_loop,element_loop)


    def _render_hip_prolog_and_epilog(self,local_res_var):
        hip_loop_prolog =\
"""
gpufort::acc_grid {local_res}({num_gangs},{num_workers},{vector_length});
if ( {permissive_condition} ) {{
"""

        hip_loop_epilog = """\
}} // {comment}
"""
        conditions = []
        num_gangs = "_res.gangs"  
        if self.gang_partitioned:
            if self.num_gangs != None:
                num_gangs = self.num_gangs
            conditions.append("_coords.gang < {num_gangs}".format(
                num_gangs=local_res_var+".gangs"))
        else:
            conditions.append("true")
        if self.worker_partitioned:
            if self.num_workers == None:
                num_workers = "_res.workers"  
            else:
                num_workers = self.num_workers
            conditions.append("_coords.worker < {num_workers}".format(
                num_workers=local_res_var+".workers"))
        else:
            num_workers = "1"
        if self.vector_partitioned:
            if self.vector_length == None:
                vector_length = "_res.vector_lanes"  
            else:
                vector_length = self.vector_length
            conditions.append("_coords.vector_lane < {vector_length}".format(
                vector_length=local_res_var+".vector_lanes"))
        else:
            vector_length = "1"
        permissive_condition = " && ".join(conditions)
        loop_open = hip_loop_prolog.format(
          local_res=local_res_var,
          num_gangs=num_gangs,
          num_workers=num_workers,
          vector_length=vector_length,
          permissive_condition=permissive_condition
        )
        loop_close = hip_loop_epilog.format(
          comment=local_res_var
        )
        return (loop_open,loop_close)

    def map_to_hip_cpp(self):
        """
        :return: HIP C++ device code.
        """
        indent = ""
        loop_open = ""
        loop_close = ""
        statement_activation_condition = None
        if self.prolog != None:
            loop_open += self.prolog
        partitioned = (
          self.gang_partitioned
          or self.worker_partitioned
          or self.vector_partitioned
        )
        if partitioned: 
            local_res_var = _unique_label("local_res")
            hip_prolog, hip_epilog = self._render_hip_prolog_and_epilog(
              local_res_var) 
            loop_open += hip_prolog
            #
            orig_len_var = _unique_label("len")
            worker_tile_size_var = _unique_label("worker_tile_size")
            num_worker_tiles = "{}.total_num_workers()".format(local_res_var)
            worker_id_var = _unique_label("worker_id")
            #
            indent += single_level_indent
            loop_open += textwrap.indent(
              _render_const_int_decl(
                orig_len_var,
                self.length()
              ) 
              +
              _render_tile_size_var_decl(
                worker_tile_size_var,
                orig_len_var,
                num_worker_tiles)
              +
              _render_const_int_decl(
                worker_id_var,
                "_coords.worker_id({})".format(local_res_var)
              ),
              indent
            )
            if self.prolog != None:
                loop_open += textwrap.indent(self.prolog,indent)
            if self.vector_partitioned: # vector, worker-vector, gang-worker-vector
                # loop over vector lanes
                if self._is_normalized_loop():
                    index_var = self.index
                else:
                    index_var = _unique_label("idx")
                first = "{}*{}".format(worker_id_var,worker_tile_size_var)
                excl_ubound_var = _unique_label("excl_ubound")
                loop_open += textwrap.indent(
                   _render_const_int_decl( 
                    excl_ubound_var,
                    "min({},({}+1)*{})".format(
                      orig_len_var,
                      worker_id_var,
                      worker_tile_size_var
                    )
                  )
                  +
                  _render_for_loop_open(
                    index_var,
                    first,
                    excl_ubound_var,
                    local_res_var+".vector_lanes"
                  ),
                  indent
                )
                loop_close = indent+"}} // {}\n".format(index_var) + loop_close
                indent += single_level_indent
                # recover the original index
                if not self._is_normalized_loop():
                    loop_open += "{}{} = {};\n".format(
                      indent,
                      self.index,
                      self._render_index_recovery(
                        self.first,self.step,index_var
                      )
                    )
            else:
                # keep the element loop, map tile loop to resources
                _, element_loop = self.tile(
                    worker_tile_size_var,
                    tile_loop_index=worker_id_var
                )
                loop_open += textwrap.indent(
                  _render_for_loop_open(
                    element_loop.index,
                    element_loop.first,
                    element_loop.excl_ubound(),
                    element_loop.step
                  ),
                  indent
                )
                loop_close = indent+"}} // {}\n".format(element_loop.index) + loop_close
                #
                indent += single_level_indent
                loop_open += textwrap.indent(
                  element_loop.body_prolog.replace("$idx$",worker_id_var),
                  indent
                )
                loop_close = indent+"}\n" + loop_close
                indent += single_level_indent
            loop_close += hip_epilog
            statement_activation_condition = "{} < _res".format(local_res_var)
        else:
            loop_open += _render_for_loop_open(
              self.index,
              self.first,
              self.excl_ubound(),
              self.step
            )
            loop_close = "}\n"
            indent += single_level_indent
        # add the body prolog, outcome of previous loop transformations
        if self.body_prolog != None:
            loop_open += textwrap.indent(
              self.body_prolog.replace("$idx$",self.index),
              indent
            )
        return (loop_open,loop_close,statement_activation_condition,indent)

class Loopnest:
    """ Transforms tightly-nested loopnests where only the first loop
    stores information about loop transformations and mapping the loop to a HIP
    device. Possible transformations are collapsing and tiling of the loopnest.
    In the latter case, the loopnest must contain as many loops as tiles.
    Mapping to a HIP device is performed based on the
    offload information stored in the first loop of the loopnest.
    """
    def __init__(self):
        self._loops = []
        self._original_loops = []
        self._is_tiled = False
    def append_loop(self,loop):
        self._loops.append(loop) 
        self._original_loops.append(loop)
    def collapse(self):
        assert not self._is_tiled, "won't collapse tiled loopnest"
        assert len(self._loops)
        loop_lengths_vars = []
        first_loop = self._loops[0]
        # Preamble before loop
        prolog = ""
        for i,loop in enumerate(self._loops):
            loop_lengths_vars.append(_unique_label("len"))
            prolog += "const int {} = {};\n".format(
              loop_lengths_vars[-1],loop.length())
        total_len_var = _unique_label("total_len")
        prolog += "const int {} = {};\n".format(
              total_len_var, "*".join(loop_lengths_vars)
            )
        # Preamble within loop body
        body_prolog = ""
        remainder_var = _unique_label("rem");
        denominator_var= _unique_label("denom")
        # template, idx remains as placeholder
        # we use $idx$ and simple str.replace as the
        # { and } of C/C++ scopes could cause issues
        # with str.format
        body_prolog += "int {rem} = $idx$;\n".format(rem=remainder_var)
        body_prolog += "int {denom} = {total_len};\n".format(
          denom=denominator_var,total_len=total_len_var
        )
        # index recovery
        for i,loop in enumerate(self._original_loops):
            gpufort_fun = "gpufort::outermost_index_w_len"
            if loop.step != None:
                body_prolog += ("const int {} = "
                  + gpufort_fun
                  + "({}/*inout*/,{}/*inout*/,{},{},{});\n").format(
                    remainder_var,denominator_var,
                    loop.first,loop_lengths_vars[i],loop.step
                  )
            else:
                body_prolog += ("const int {} = "
                  + gpufort_fun
                  + "({}/*inout*/,{}/*inout*/,{},{});\n").format(
                    remainder_var,denominator_var,
                    loop.first,loop_lengths_vars[i]
                  )
        collapsed_index_var = _unique_label("idx")
        collapsed_loop = Loop(
          index = collapsed_index_var,
          first = "0",
          length = total_len_var,
          excl_ubound = total_len_var,
          step = None,
          gang_partitioned = first_loop.gang_partitioned,
          worker_partitioned = first_loop.worker_partitioned,
          vector_partitioned = first_loop.vector_partitioned,
          num_gangs = first_loop.num_gangs,
          num_workers = first_loop.num_workers,
          vector_length = first_loop.vector_length,
          prolog = prolog, 
          body_prolog = body_prolog)
        self._loops.clear()
        self._loops.append(collapsed_loop)

    def tile(self,tile_sizes):
        if isinstance(tile_sizes,str):
            tile_sizes = [tile_sizes]
        assert len(tile_sizes) == len(self._loops)
        tile_loops = []
        element_loops = []
        for i,loop in enumerate(self._loops()):
            tile_loop, element_loop = loop.tile(tile_sizes[i])
            tile_loops.append(tile_loop)
            element_loops.append(element_loop)
        self._loops.clear()
        self._loops += tile_loops
        self._loops += element_loops
        self._is_tiled = True

    def map_to_hip_cpp(self):
        # TODO analyze and return required resources (gangs,workers,vector_lanes)
        # but perform it outside as we deal with C++ expressions here.
        # * Alternatively, move the derivation of launch parameters into C++ code?
        #   * Problem size depends on other parameters that need to be passed
        #     to the C++ layer anyway ...
        # Think outside of the box:
        # * Gang synchronization might require us to launch multiple kernels
        #   and put wait events inbetween
        # * What about reductions?
        pass
         

# TODO implement
# TODO workaround, for now expand all simple workshares
# Workshares are interesting because the loop
# bounds might actually coincide with the array
# dimensions of a variable
#class Workshare:
#    pass
## Workshare that reduces some array to a scalar, e.g. MIN/MAX/...
#class ReducingWorkshare:
#    pass 