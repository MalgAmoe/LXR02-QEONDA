# Copyright (C) 2026 Erica Synths
# SPDX-License-Identifier: GPL-3.0-only

# Host unit tests: firmware sources compiled with the computer's own C compiler
# and run on the computer. See README.md in this folder.
#
#   cmake --preset host-tests
#   cmake --build --preset host-tests
#   ctest --preset host-tests

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)

set(LXR_SOURCE_DIR "${PROJECT_SOURCE_DIR}")

# AddressSanitizer and UndefinedBehaviorSanitizer turn out-of-bounds accesses
# and undefined behaviour in the code under test into test failures.
option(LXR_TEST_SANITIZERS "Build the host tests with ASan and UBSan" ON)

add_library(lxr_test_common INTERFACE)
target_include_directories(lxr_test_common INTERFACE
    # Must come before Core/Inc: replaces the ST HAL and CMSIS headers.
    ${CMAKE_CURRENT_SOURCE_DIR}/shim
    ${CMAKE_CURRENT_SOURCE_DIR}/framework
    ${LXR_SOURCE_DIR}/Core/Inc
    ${LXR_SOURCE_DIR}/FATFS/App
    ${LXR_SOURCE_DIR}/FATFS/Target
    ${LXR_SOURCE_DIR}/Middlewares/Third_Party/FatFs/src
)
target_compile_definitions(lxr_test_common INTERFACE LXR_HOST_TEST)
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(lxr_test_common INTERFACE -g -O1 -Wall)
    # The firmware uses GCC's "#pragma GCC optimize", which Clang doesn't know.
    if(CMAKE_C_COMPILER_ID MATCHES "Clang")
        target_compile_options(lxr_test_common INTERFACE -Wno-unknown-pragmas)
    endif()
    if(LXR_TEST_SANITIZERS)
        set(sanitize -fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer)
        target_compile_options(lxr_test_common INTERFACE ${sanitize})
        target_link_options(lxr_test_common INTERFACE ${sanitize})
    endif()
endif()

# lxr_add_host_test(<name> SOURCES <test and firmware sources...>)
#
# Builds one test program from its test file, the firmware files it tests
# (paths relative to the repository root) and any stubs, and registers it with
# CTest.
function(lxr_add_host_test name)
    cmake_parse_arguments(arg "" "" "SOURCES;FIRMWARE_SOURCES" ${ARGN})
    list(TRANSFORM arg_FIRMWARE_SOURCES PREPEND "${LXR_SOURCE_DIR}/")
    add_executable(${name} ${arg_SOURCES} ${arg_FIRMWARE_SOURCES})
    target_link_libraries(${name} PRIVATE lxr_test_common)
    add_test(NAME ${name} COMMAND ${name})
endfunction()

lxr_add_host_test(test_fifo
    SOURCES test_fifo.c
    FIRMWARE_SOURCES Core/Src/Soundengine/FIFO.c
)

lxr_add_host_test(test_euklid
    SOURCES test_euklid.c
    FIRMWARE_SOURCES Core/Src/Soundengine/Sequencer/EuklidGenerator.c
)

lxr_add_host_test(test_frontpanel_cc
    SOURCES test_frontpanel_cc.c
    FIRMWARE_SOURCES Core/Src/frontPanelParser.c
)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME test_audio_scheduling
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_audio_scheduling.py)

lxr_add_host_test(test_play_debounce
    SOURCES test_play_debounce.c
    FIRMWARE_SOURCES Core/Src/IO/DIO.c
)

add_test(NAME test_performance_break
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_performance_break.py)

lxr_add_host_test(test_safe_storage
    SOURCES test_safe_storage.c
    FIRMWARE_SOURCES Core/Src/Preset/SafeStorage.c
)

add_test(NAME test_save_io
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_save_io.py)

lxr_add_host_test(test_delay_bounds
    SOURCES test_delay_bounds.c
    FIRMWARE_SOURCES Core/Src/Soundengine/DSPAudio/FX/Delay.c
                     Core/Src/Soundengine/DSPAudio/1PoleLp.c
)

add_test(NAME test_control_fixes
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_control_fixes.py)
lxr_add_host_test(test_slot_files
    SOURCES test_slot_files.c
    FIRMWARE_SOURCES Core/Src/Preset/SlotFiles.c
)

add_test(NAME test_cleanup_fatfs
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_cleanup_fatfs.py)

add_test(NAME test_index_bounds
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_index_bounds.py)

add_test(NAME test_tempo
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_tempo.py)

add_test(NAME test_decay_endpoints
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_decay_endpoints.py)

add_test(NAME test_wavetable_wrap
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_wavetable_wrap.py)

add_test(NAME test_external_clock
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_external_clock.py)

lxr_add_host_test(test_midi_stream
    SOURCES test_midi_stream.c
    FIRMWARE_SOURCES Core/Src/Soundengine/MIDI/MidiStream.c
)
add_test(NAME test_midi_uart
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_midi_uart.py)

add_test(NAME test_midi_usb_rx
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_midi_usb_rx.py)

add_test(NAME test_midi_usb_tx_adapter
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_midi_usb_tx_adapter.py)

lxr_add_host_test(test_midi_usb_tx
    SOURCES test_midi_usb_tx.c
    FIRMWARE_SOURCES Core/Src/Soundengine/MIDI/MidiUsbTx.c
                     Core/Src/Soundengine/MIDI/MidiStream.c
)

add_test(NAME test_midi_routing
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_midi_routing.py)

add_test(NAME test_compressor
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_compressor.py)

add_test(NAME test_snare_hardclip
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_snare_hardclip.py)

add_test(NAME test_fx_drywet
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_fx_drywet.py)

# SD-only platform shims; compile the real BSP, disk adapter and FatFs dispatch.
lxr_add_host_test(test_sd_driver
    SOURCES test_sd_driver.c
    FIRMWARE_SOURCES FATFS/Target/sd_diskio.c
                     FATFS/Target/bsp_driver_sd.c
                     Middlewares/Third_Party/FatFs/src/diskio.c
                     Middlewares/Third_Party/FatFs/src/ff_gen_drv.c
)
target_include_directories(test_sd_driver BEFORE PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/shim/sd)
add_test(NAME test_sd_hal_status
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_sd_hal_status.py)
set_tests_properties(test_sd_driver test_sd_hal_status PROPERTIES TIMEOUT 30)

add_test(NAME test_sd_remount
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_sd_remount.py)

add_test(NAME test_perf_reload
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_perf_reload.py)

add_test(NAME test_output_order
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_output_order.py)

# DSP owner: actual float32 implementation, no replacement filter model.
lxr_add_host_test(test_main_dj_filter SOURCES test_main_dj_filter.c)
target_link_libraries(test_main_dj_filter PRIVATE m)
add_test(NAME test_main_dj_mixer
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_main_dj_mixer.py)

add_test(NAME test_main_dj_filter_ui
    COMMAND ${CMAKE_COMMAND} -E env "CC=${CMAKE_C_COMPILER}"
            ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_main_dj_filter_ui.py)
