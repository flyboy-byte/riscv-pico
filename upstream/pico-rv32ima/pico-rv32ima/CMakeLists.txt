add_executable(pico-rv32ima
    main.c
	usb/get_serial.c
	usb/usb_descriptors.c
	console/console.c
	console/terminal/terminal.c
	console/terminal/vt.c
	console/vga/vga.c
	console/ps2/ps2.c
	console/oled/ssd1306.c
	console/oled/status_panel.c
	../tiny-rv32ima/psram/psram.c
	../tiny-rv32ima/emulator/emulator.c
	../tiny-rv32ima/cache/cache.c
	../tiny-rv32ima/pff/pff.c
	../tiny-rv32ima/pff/mmcbbp.c
)

# Add the standard library and FatFS/SPI to the build
target_link_libraries(pico-rv32ima
	pico_stdlib 
	pico_time
	pico_multicore
	pico_unique_id
	hardware_vreg
	hardware_spi
	hardware_i2c
	hardware_clocks
	hardware_pio
	hardware_dma
	tinyusb_device 
	tinyusb_board
)

target_include_directories(pico-rv32ima PUBLIC 
	.
	hal
	usb
	console
	console/oled
	../tiny-rv32ima
)

pico_define_boot_stage2(slower_boot2 ${PICO_DEFAULT_BOOT_STAGE2_FILE})
target_compile_definitions(slower_boot2 PRIVATE PICO_FLASH_SPI_CLKDIV=4)
pico_set_boot_stage2(pico-rv32ima slower_boot2)

# The whole binary runs from RAM and RAM is nearly full, so the terminal emulator is built for size.
# It only runs on core 0 between console tasks, so it doesn't need the speed.
set_source_files_properties(console/terminal/vt.c PROPERTIES COMPILE_OPTIONS -Os)

pico_set_binary_type(pico-rv32ima copy_to_ram)
pico_add_extra_outputs(pico-rv32ima)

