cmake_minimum_required(VERSION 3.13)
project(both_strided CXX)

find_package(Celerity CONFIG REQUIRED)

add_executable(strided_both_transfer strided_both_transfer.cpp)
add_celerity_to_target(TARGET strided_both_transfer SOURCES strided_both_transfer.cpp)
