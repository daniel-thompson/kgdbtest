ifeq ("$(ARCH)", "")
UARCH=$(shell uname -m)
ifeq ("$(UARCH)", "aarch64")
  export ARCH=arm64
else
  export ARCH=x86
endif
endif
ifeq ("$(notdir $(PWD))", "build-$(ARCH)")
  export KERNEL_DIR = $(dir $(PWD))
else
  export KERNEL_DIR = $(PWD)
endif
export KGDBTEST_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

# Include kdmx in the path
export PATH := $(PATH):$(shell pwd)/agent-proxy/kdmx

test :
	pytest-3 $(PYTEST_VERBOSE) $(PYTEST_RESTRICT) $(PYTEST_EXTRAFLAGS)

interact :
ifeq ("$(origin K)", "command line")
	tests/interact.py $(K)
else
	tests/interact.py
endif

ifeq ("$(origin K)", "command line")
  PYTEST_RESTRICT = -k '$(K)'
else
  PYTEST_RESTRICT =
endif

ifeq ("$(origin V)", "command line")
  PYTEST_VERBOSE = $(V)
else
  PYTEST_VERBOSE = 0
endif

ifeq ($(PYTEST_VERBOSE),2)
  PYTEST_VERBOSE = -v -s
else ifeq ($(PYTEST_VERBOSE),1)
  PYTEST_VERBOSE = -v
else
  PYTEST_VERBOSE =
endif

submodule-update :
	git submodule update --init

BUILDROOT ?= $(KGDBTEST_DIR)/buildroot/tree
BUILDROOT_INTERMEDIATES = \
		$(KGDBTEST_DIR)/buildroot/$(ARCH)/build \
		$(KGDBTEST_DIR)/buildroot/$(ARCH)/staging \
		$(KGDBTEST_DIR)/buildroot/$(ARCH)/target

buildroot : kdmx buildroot-update buildroot-build buildroot-tidy

buildroot-update : submodule-update buildroot-config

buildroot-config :
	(cd $(KGDBTEST_DIR)/buildroot/$(ARCH); $(MAKE) -C $(BUILDROOT) O=$$PWD olddefconfig)

# Remove intermediates, rather than doing a full clean, so we can (mostly)
# keep running tests whilst the rebuild happens
buildroot-build :
	$(RM) -r $(BUILDROOT_INTERMEDIATES)
	make -C $(KGDBTEST_DIR)/buildroot/$(ARCH)

# This is enough to save disk space (and force a rebuild) but leaves
# the cross-compilers and root images alone.
buildroot-tidy :
	$(RM) -r $(BUILDROOT_INTERMEDIATES)

kdmx : submodule-update
	$(MAKE) -C agent-proxy/kdmx

.PHONY : submodule-update buildroot buildroot-update buildroot-config buildroot-build buildroot-tidy
