# 上游 libusb 1.0.29（LGPL-2.1，见 COPYING），只取 Linux/Android 后端。
# 编成独立的共享库 libusb-1.0.so，不静态链进核心：LGPL 要求使用者能替换这个库。
add_library(usb-1.0 SHARED
  libusb/core.c
  libusb/descriptor.c
  libusb/hotplug.c
  libusb/io.c
  libusb/strerror.c
  libusb/sync.c
  libusb/os/linux_usbfs.c
  libusb/os/linux_netlink.c
  libusb/os/events_posix.c
  libusb/os/threads_posix.c)
target_include_directories(usb-1.0
  PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/libusb"
  PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/config" "${CMAKE_CURRENT_SOURCE_DIR}/libusb/os")
set_target_properties(usb-1.0 PROPERTIES C_STANDARD 11 C_EXTENSIONS ON)
target_compile_options(usb-1.0 PRIVATE -fvisibility=hidden)
find_package(Threads REQUIRED)
target_link_libraries(usb-1.0 PRIVATE Threads::Threads)
if(ANDROID)
  target_link_libraries(usb-1.0 PRIVATE log)
endif()
