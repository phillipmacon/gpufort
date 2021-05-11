program testSaxpy
  use cudafor
  implicit none
  integer, parameter :: N = 40000
  real :: x(N), y(N), a
  real, device, allocatable :: x_d(:)
  real, allocatable :: y_d(:)
  !real, device :: x_d(N), y_d(N) ! fixed-size arrays are not fully 
                       ! supported yet as alloc/dealloc are not generated yet
  type(dim3) :: grid, tBlock
  integer :: i

  attributes(device) :: y_d

  tBlock = dim3(256,1,1)
  grid = dim3(ceiling(real(N)/tBlock%x),1,1)

  allocate(x_d(N),y_d(N))

  x = 1.0; y = 2.0; a = 2.0
  x_d = x
  y_d = y
  
  call gpuKernel<<<grid, tBlock>>>(a,x_d,y_d,N)

  y = y_d

  deallocate(x_d,y_d)

  write(*,*) 'Max error: ', maxval(abs(y-4.0))

contains 
   
   attributes(device) subroutine deviceFun(a,x,y,N)
    real :: x(N), y(N), a
    integer :: N
    integer :: i
    i = threadidx%x
    if (i < N) then
      y(i) = y(i) + a*x(i)
    endif
   end subroutine

   attributes(global) subroutine gpuKernel(a,x,y,N)
    real :: x(N), y(N), a
    integer :: N
    integer :: i
    i = threadidx%x
    if (i < N) then
      y(i) = y(i) + a*x(i)
    endif
   end subroutine
end program testSaxpy
