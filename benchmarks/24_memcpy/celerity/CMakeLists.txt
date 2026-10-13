cmake_minimum_required(VERSION 3.13)
project(memcpy_celerity LANGUAGES CXX)

# configure with -DCMAKE_PREFIX_PATH=<celerity install>
find_package(Celerity CONFIG REQUIRED)

set(BENCH_IMPL "celerity" CACHE STRING "label printed in the Config line")

add_executable(memcpy_celerity memcpy_celerity.cpp)
target_include_directories(memcpy_celerity PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../common)
target_compile_definitions(memcpy_celerity PRIVATE BENCH_IMPL="${BENCH_IMPL}")
target_compile_features(memcpy_celerity PRIVATE cxx_std_20)
add_celerity_to_target(TARGET memcpy_celerity SOURCES memcpy_celerity.cpp)
