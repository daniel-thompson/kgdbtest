ifeq ("$(ARCH)", "")
export ARCH=x86
endif
ifeq ("$(notdir $(PWD))", "build-$(ARCH)")
  export KERNEL_DIR = $(dir $(PWD))
else
  export KERNEL_DIR = $(PWD)
endif
export KCONTEST_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

test :
	pytest-3 $(PYTEST_VERBOSE) $(PYTEST_RESTRICT) $(PYTEST_EXTRAFLAGS)

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

BUILDROOT ?= $(error BUILDROOT is not set)
buildroot-config :
	(cd $(KCONTEST_DIR)/buildroot/$(ARCH); $(MAKE) -C $(BUILDROOT) O=$$PWD olddefconfig)

# Use buildroot-tidy (rather than clean) so we can keep running tests whilst
# the rebuild happens
buildroot : buildroot-tidy
	make -C $(KCONTEST_DIR)/buildroot/$(ARCH)

# This is enough to save disk space (and force a rebuild) but leaves
# the cross-compilers and root images alone.
buildroot-tidy :
	$(RM) -r \
		$(KCONTEST_DIR)/buildroot/$(ARCH)/build \
		$(KCONTEST_DIR)/buildroot/$(ARCH)/staging \
		$(KCONTEST_DIR)/buildroot/$(ARCH)/target

.PHONY : buildroot-config buildroot buildroot-tidy
