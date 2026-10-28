# 鸿蒙 Node-API 库 libentry.so：把核心（core + perception + agent）编进来。
cmake_minimum_required(VERSION 3.16)
project(lingtouch_harmony LANGUAGES C CXX)

# 仓库根 = 本目录往上 6 层（apps/harmony/entry/src/main/cpp），随仓库一起移动
get_filename_component(LINGTOUCH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../../.." ABSOLUTE)

# 备选取流路径：usbManager.getFileDescriptor + libusb_wrap_sys_device（没人测过）。
# libusb 的 Linux 后端在鸿蒙 NDK 下若编不过，把这里改成 OFF，主路径（usbSubmitTransfer）不受影响。
option(LINGTOUCH_HARMONY_LIBUSB "Build the getFileDescriptor + libusb alternative" ON)

set(LINGTOUCH_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LINGTOUCH_WITH_LIBUSB ${LINGTOUCH_HARMONY_LIBUSB} CACHE BOOL "" FORCE)
add_subdirectory("${LINGTOUCH_ROOT}/core" "${CMAKE_CURRENT_BINARY_DIR}/lingtouch_core")

add_library(entry SHARED napi_init.cpp)
target_link_libraries(entry PUBLIC libace_napi.z.so lingtouch_engine)
if(LINGTOUCH_HARMONY_LIBUSB)
  target_compile_definitions(entry PRIVATE LINGTOUCH_HARMONY_LIBUSB=1)
  target_link_libraries(entry PUBLIC lingtouch_cs30_libusb)
endif()
lingtouch_target_defaults(entry)
