module cudafor
  type,bind(c) :: dim3
     integer(c_int) :: x,y,z
     integer :: d
  end type dim3
end module cudafor
