cmake_minimum_required(VERSION 3.13)
project(rows CXX)

find_package(Celerity CONFIG REQUIRED)

add_executable(strided_rows_transfer strided_rows_transfer.cpp)
add_celerity_to_target(TARGET strided_rows_transfer SOURCES strided_rows_transfer.cpp)
