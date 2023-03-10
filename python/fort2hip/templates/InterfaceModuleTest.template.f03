{# SPDX-License-Identifier: MIT                                                 #}
{# Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved. #}
! This file was generated by gpufort
{# Jinja2 template for generating tests for interface modules #}
program test_{{name}}
  implicit none
  integer :: global_error_code = 0, error_code, fails = 0, tests = 0
  ! declare test functions and return type
{% for interface in interfaces %}{% if interface.do_test %}  integer :: test_{{interface.f_name}}
{% endif %}{# if interface.do_test #}
{% endfor %}
  write(*,*) "SUITE test_{{name}} run ..."
{% for interface in interfaces %}{% if interface.do_test %}  error_code = test_{{interface.f_name}}()
  IF (error_code > 0) THEN
    fails = fails + 1
    write(*,*) "TEST test_{{interface.f_name}} ... FAILURE"
  ELSE 
    write(*,*) "TEST test_{{interface.f_name}} ... SUCCESS"
  END IF
  tests = tests + 1
  global_error_code = global_error_code + error_code
{% endif %}{# if interface.do_test #}
{% endfor %}
  IF (global_error_code > 0) THEN
    write(*,*) "SUITE test_{{name}} ... FAILURE passed:",(tests-fails)," failed:",fails," total:",tests
  ELSE 
    write(*,*) "SUITE test_{{name}} ... SUCCESS passed:",(tests-fails)," failed:",fails," total:",tests
  END IF
  contains
{% for interface in interfaces %}{% if interface.do_test %} 
{% for line in interface.test_comment %}! {{line}}
{% endfor %}
    function test_{{interface.f_name}}()
      ! error_code > 0 implies that the test has failed
      use iso_c_binding
      use hipfort
      use hipfort_check
      use {{name}}
      implicit none
      integer :: error_code = 1
      ! TODO fix parameters
      ! - Add missing arguments
      ! - Determine size of arrays (typically indicated by 'type(c_ptr)' type)
      ! - Add target where we need a pointer
    {% for arg in interface.args %}
      {{arg.type}}{%- if arg.qualifiers|length > 0 -%}, {%- endif -%}{{arg.qualifiers | join(",") | replace(", value","") }} :: {{arg.name}}
    {% endfor %}
      ! TODO Create initial data on host
      ! TODO Copy data to device ! (dest,src,size,direction)
      CALL hipCheck(hipMemcpy(???,c_loc(???),C_SIZEOF(???),hipMemcpyHostToDevice)) ! 
      CALL hipCheck(hipMemcpy(???,c_loc(???),C_SIZEOF(???),hipMemcpyHostToDevice)) ! 
      ! ... might be more (or less) than two memcopies 
      ! TODO run the test
      CALL {{interface.f_name}}(0,c_null_ptr,{{interface.argnames | join(",") }}) ! Modify sharedmem if other than default 0
      CALL hipCheck(hipDeviceSynchronize())
      CALL {{interface.f_name | replace("_auto","") }}_cpu(0,c_null_ptr,{{interface.argnames | join(",") }})
    
      ! TODO Copy results back to host
      CALL hipCheck(hipMemcpy(c_loc(???),???,C_SIZEOF(???),hipMemcpyDeviceToHost)
      CALL hipCheck(hipMemcpy(c_loc(???),???,C_SIZEOF(???),hipMemcpyDeviceToHost)
      ! ... might be more (or less) than two memcopies 
      ! TODO Compare results
      ! TODO Update error code if the results do not match
      return error_code
    end function
{% endif %}{# if interface.do_test #}
{% endfor %}
end program test_{{name}}