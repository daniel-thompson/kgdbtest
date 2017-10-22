KERNEL_DIR = $(PWD)
KCONTEST_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
export KERNEL_DIR KCONTEST_DIR


test :
	pytest-3
