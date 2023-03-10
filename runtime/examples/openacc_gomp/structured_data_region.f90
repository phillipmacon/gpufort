! SPDX-License-Identifier: MIT                                                
! Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
program test_acc
  use openacc_gomp
  implicit none
  !
  real(4),target :: a(10),b(10,10),c(10,10)
  type(c_ptr) :: tmp_d = c_null_ptr
  call acc_init(acc_device_nvidia)

  write(*, fmt="(a)", advance="no") "hostaddr of 'a': "
  call print_cptr(c_loc(a))
  print *, ""
  write(*, fmt="(a)", advance="no") "hostaddr of 'b': "
  call print_cptr(c_loc(b))
  print *, ""
  write(*, fmt="(a)", advance="no") "hostaddr of 'c' (will not be mapped): "
  call print_cptr(c_loc(c))
  print *, ""

  call GOACC_data_start(acc_device_default,&
          mappings=[map_create(a),map_create(b)]&
  )

!  !$acc enter data create(a(:),b(:,:))
  !call GOACC_enter_exit_data(acc_get_device_num(acc_device_nvidia),&
  !        mappings=[map_create(a),map_create(b)]&
  !)

  write(*, fmt="(a)", advance="no") "acc_deviceptr(a)="
  call print_cptr(acc_deviceptr(a))
  print *, ""
  write(*, fmt="(a)", advance="no") "acc_deviceptr(b)="
  call print_cptr(acc_deviceptr(b))
  print *, ""
  write(*, fmt="(a)", advance="no") "acc_deviceptr(c)="
  call print_cptr(acc_deviceptr(c))
  print *, ""
  
  print *, "acc_is_present(a) = ", acc_is_present(a)
  print *, "acc_is_present(b) = ", acc_is_present(b)
  print *, "acc_is_present(c) = ", acc_is_present(c)

  call GOACC_data_end()
  
  print *, "acc_is_present(a) = ", acc_is_present(a)
  print *, "acc_is_present(b) = ", acc_is_present(b)
  print *, "acc_is_present(c) = ", acc_is_present(c)
  
!  !$acc exit data delete(a(:),b(:,:))
  !call GOACC_enter_exit_data(acc_get_device_num(acc_device_nvidia),&
  !        mappings=[map_delete(a),map_delete(b)]&
  !)

  call acc_shutdown(acc_device_nvidia)

end program test_acc