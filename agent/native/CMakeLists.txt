# 对话 agent 同学的 C++ 部分。本次只有接口头文件，没有实现。
add_library(lingtouch_agent INTERFACE)
target_include_directories(lingtouch_agent INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(lingtouch_agent INTERFACE lingtouch_base)
