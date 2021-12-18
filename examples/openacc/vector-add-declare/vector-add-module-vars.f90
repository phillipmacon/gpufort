! SPDX-License-Identifier: MIT
! Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
module datatypes
  integer, parameter :: N = 1000
  integer,allocatable,dimension(:) :: x1
  integer,pointer,dimension(:)     :: x2
  integer                          :: y(N)
  !$acc declare create(x1,x2,y)
end module

program main
  ! begin of program

  use datatypes
  implicit none
  integer :: i
  integer(4) :: y_exact(N)

  allocate(x1(N),x2(N))

  y_exact = 4

  !$acc parallel loop
  do i = 1, N
    x1(i) = 1
    x2(i) = 1
    y(i) = 2
  end do

  !$acc parallel loop
  do i = 1, N
    y(i) = x1(i) + x2(i) + y(i)
  end do

  !$acc update host(y)

  do i = 1, N
    if ( y_exact(i) .ne.&
            y(i) ) ERROR STOP "GPU and CPU result do not match"
  end do

  print *, "PASSED"

  deallocate(x1,x2)

end program