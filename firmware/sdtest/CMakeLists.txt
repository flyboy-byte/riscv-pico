cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico CACHE STRING "Board type")

include(pico_sdk_import.cmake)

project(sdtest C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(sdtest main.c)
target_link_libraries(sdtest pico_stdlib hardware_spi)

pico_enable_stdio_usb(sdtest 1)
pico_enable_stdio_uart(sdtest 0)

pico_add_extra_outputs(sdtest)
