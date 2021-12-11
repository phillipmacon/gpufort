{#- SPDX-License-Identifier: MIT                                                -#}
{#- Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.-#}
{#- Jinja2 template for generating interface modules                            -#}
{#- This template works with data structures of the form :                      -#}
{########################################################################################}
{%- macro render_param_decl(ivar,interop_suffix) -%}
{%- if ivar.f_type in ["integer","real","logical","type"] -%}
{%-   if ivar.rank > 0 -%}
type(gpufort_array{{ivar.rank}}) :: {{ivar.name}}
{%-   else -%}
{%-     if ivar.f_type == "type" -%}
{{ivar.f_type}}({{ivar.kind}}{{interop_suffix}}) :: {{ivar.name}}
{%-     elif ivar.kind is not none and ivar.kind|length > 0 -%}
{{ivar.f_type}}({{ivar.kind}}) :: {{ivar.name}}
{%-     else -%}
{{ivar.f_type}} :: {{ivar.name}}
{%-     endif -%}
{%-   endif -%}
{%- endif -%}
{%- endmacro -%}
{########################################################################################}
{%- macro render_param_decls(ivars,interop_suffix,sep) -%}
{%- for ivar in ivars -%}{{render_param_decl(ivar,interop_suffix)}}{{sep if not loop.last}}{% endfor -%}
{%- endmacro -%}
{########################################################################################}
{%- macro render_params(ivars) -%}
{%- for ivar in ivars -%}{{ivar.name}}{{"," if not loop.last}}{% endfor -%}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_types(derived_types,interop_suffix) -%}
{% for derived_type in derived_types %}
type, bind(c) :: {{derived_type.name}}{{interop_suffix}}
{{ (render_param_decls(derived_type.variables,interop_suffix,"\n")) | indent(2,True) }}
end type {{derived_type.name}}{{interop_suffix}}
{% endfor %}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_type_copy_scalars( derived_type, derived_types,
          inline=False, interop_suffix="_interop", 
          orig_var="orig_type", interop_var="interop_type" ) -%}
{% for ivar in derived_type.variables %}
{%   if ivar.rank == 0 %}
{%     if ivar.f_type in ["integer","real","logical"] %}
{{interop_var}}%{{ivar.name}} = {{orig_var}}%{{ivar.name }}
{%     elif ivar.f_type == "type" %}
{%       if inline %}
{%         for derived_type2 in derived_types %}
{%           if derived_type2.name == ivar.kind %}
{{ render_derived_type_copy_scalars( derived_type2, derived_types,
     True, interop_suffix, orig_var+"%"+ivar.name, interop_var+"%"+ivar.name ) }}
{%           endif %}
{%         endfor %}
{%       else %}
call {{ivar.kind}}{{interop_suffix}}_copy_scalars({{interop_var}}%{{ivar.name}},{{orig_var}}%{{ivar.name}})  
{%       endif %}
{%     endif %}
{%   endif %}
{% endfor %}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_type_copy_scalars_routines(derived_types,interop_suffix="_interop",
                                                    used_modules=[]) -%}
{% for derived_type in derived_types %}
subroutine {{derived_type.name}}{{interop_suffix}}_copy_scalars(interop_type,orig_type)
{% if used_modules|length > 0 %}
{% for mod in used_modules %}
  use {{mod}}
{% endfor %}
{% endif %}
  type({{derived_type.name}}{{interop_suffix}}),intent(inout) :: interop_type
  type({{derived_type.name}}),intent(in) :: orig_type
  !
  {{ render_derived_type_copy_scalars(derived_type,derived_types,False,interop_suffix) }}
end subroutine{{"\n" if not loop.last}}
{% endfor %}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_type_size_bytes_routines(derived_types,interop_suffix="_interop",
                                                  used_modules=[]) -%}
{% for derived_type in derived_types %} 
function {{derived_type.name}}{{interop_suffix}}_size_bytes() result(size_bytes)
  use iso_c_binding
{%   if used_modules|length > 0 %}
{%     for mod in used_modules %}
  use {{mod}}
{%     endfor %}
{%   endif %}
  type({{derived_type.name}}{{interop_suffix}}) :: dummy
  integer(c_int) :: size_bytes
  !
  size_bytes = int(c_sizeof(dummy),c_int)
end function
{% endfor %}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_type_copy_array_member(derived_type, member,
          derived_types, sync_mode="gpufort_array_sync_copy",
          interop_suffix="_interop", 
          orig_var="orig_type", interop_var="interop_type") -%}
{% for ivar in derived_type.variables %}
{%   if ivar.name == member %}
{%     if ivar.f_type in ["integer","real","logical"] %}
call hipCheck(gpufort_array_init({{interop_var}}%{{member}},{{orig_var}}%{{member}},&
  alloc_mode=gpufort_array_wrap_host_alloc_device,&
  sync_mode={{sync_mode}}))
{%     elif ivar.f_type == "type" %}
call hipCheck(gpufort_array_init({{interop_var}}%{{member}},&
  {{ivar.kind}}{{interop_suffix}}_size_bytes(),&
  shape({{orig_var}}%{{member}}),&
  lbounds=lbound({{orig_var}}%{{member}}),&
  alloc_mode=gpufort_array_alloc_pinned_host_alloc_device)) 
  ! 
call c_f_pointer({{interop_var}}%{{member}}%data%data_host,&
  {{interop_var}}_{{member}},shape=shape({{orig_var}}%{{member}}))
!call hipCheck(gpufort_array_copy_to_device(mesh_interop%x))
{%     endif %}
{%   endif %}
{% endfor %}
{%- endmacro -%}
{########################################################################################}
{%- macro render_derived_type_copy_array_member_routines(derived_types,
          interop_suffix="_interop", 
          orig_var="orig_type",interop_var="interop_type",
          used_modules=[]) -%}
{% for derived_type in derived_types %}
{%   for ivar in derived_type.variables %}
{%     if ivar.rank > 0 %} 
subroutine {{derived_type.name}}{{interop_suffix}}_copy_{{ivar.name}}({{interop_var}},{{orig_var}},sync_mode)
  use gpufort_array
{%       if used_modules|length > 0 %}
{%         for mod in used_modules %}
  use {{mod}}
{%         endfor %}
{%       endif %}
  type({{derived_type.name}}{{interop_suffix}}),intent(inout) :: {{interop_var}}
  type({{derived_type.name}}),intent(in)                      :: {{orig_var}}
  integer(kind(gpufort_array_sync_none)),intent(in)           :: sync_mode
  !
{{ render_derived_type_copy_array_member(derived_type, ivar.name,
                                           derived_types, "sync_mode") | indent(2,True) }}
end subroutine{{"\n" if not loop.last}}
{%     endif %}
{%   endfor %}
{% endfor %}
{%- endmacro -%}