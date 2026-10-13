cmake_minimum_required(VERSION 3.13)
project(device_strided CXX)

find_package(Celerity CONFIG REQUIRED)

add_executable(device_strided_transfer device_strided_transfer.cpp)
add_celerity_to_target(TARGET device_strided_transfer SOURCES device_strided_transfer.cpp)
