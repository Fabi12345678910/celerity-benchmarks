cmake_minimum_required(VERSION 3.13)
project(transfer CXX)

find_package(Celerity CONFIG REQUIRED)

foreach(name strided_transfer block_transfer)
  add_executable(${name} ${name}.cpp)
  add_celerity_to_target(TARGET ${name} SOURCES ${name}.cpp)
endforeach()
