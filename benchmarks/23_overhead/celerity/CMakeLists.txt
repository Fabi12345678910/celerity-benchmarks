cmake_minimum_required(VERSION 3.13)
project(overhead_celerity LANGUAGES CXX)

# configure with -DCMAKE_PREFIX_PATH=<celerity install> (copylib and no-copylib installs get separate build directories)
find_package(Celerity CONFIG REQUIRED)

set(BENCH_IMPL "celerity" CACHE STRING "label printed in the Config line")

add_executable(overhead_celerity overhead_celerity.cpp)
target_include_directories(overhead_celerity PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../common)
target_compile_definitions(overhead_celerity PRIVATE BENCH_IMPL="${BENCH_IMPL}")
target_compile_features(overhead_celerity PRIVATE cxx_std_20)
add_celerity_to_target(TARGET overhead_celerity SOURCES overhead_celerity.cpp)
