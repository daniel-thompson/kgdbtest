TODO
====

 * Add support for additional architectures
   - ARCH=arm
   - ARCH=arm64
 * Automatically build and install a kernel module to make it easier to
   stimulate specific kernel behaviours
   - BUG()
   - WARN()
 * Improve test coverage
   - Exercise every kdb command at least once
   - kdb/ftrace
   - kgdb peek/poke
   - kgdb breakpoint in module
   - kgdb register modification (HARD)
   - parameterize kgdb smoke test to cover kernels built with and
     without kdb support.
   - kgdb entry on panic()
 * Provide Makefile rules to automatically create rootfs.cpio.xz .
