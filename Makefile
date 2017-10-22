KERNEL_DIR = $(PWD)
KCONTEST_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
export KERNEL_DIR KCONTEST_DIR

test :
	pytest-3 $(PYTEST_VERBOSE)

ifeq ("$(origin V)", "command line")
  PYTEST_VERBOSE = $(V)
else
  PYTEST_VERBOSE = 0
endif

ifeq ($(PYTEST_VERBOSE),1)
  PYTEST_VERBOSE = -v
else
  PYTEST_VERBOSE =
endif
