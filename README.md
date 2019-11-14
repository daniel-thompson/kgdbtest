kgdbtest - kernel console tests
===============================

Collection of fully automated kernel tests that test aspects of the
kernel that rely upon having access to a console. In particular this
allows us to test tools such as kgdb/kdb.

kgdbtest is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either [version 2 of the
License](LICENSE.md), or (at your option) any later version.

Prerequisites
-------------

kgdbtest requires a few special command lines tools together with some
additional python libraries.

On Fedora systems these can be installed as follows:

~~~
sudo dnf install -y \
	python3 \
	python3-pexpect \
	python3-pytest \
	socat
~~~

Likewise on debian systems:

~~~
sudo apt install -y \
	python3 \
	python3-pexpect \
	python3-pytest \
	socat
~~~

Buildroot
---------

kgdbtest relies on buildroot filesystems, normally loaded as an
initramfs. kgdbtest includes .config files to regenerate the
filesystem from scratch. The Makefile also has a few convenience
rules to help construct the filesystem.

~~~
ARCH=arm make buildroot
ARCH=arm64 make buildroot
ARCH=mips make buildroot
ARCH=x86 make buildroot
~~~

kgdbtest is configured to use a known working buildroot tree but
can adopt a different tree is desired:

~~~
ARCH=arm64 BUILDROOT=/path/to/buildroot/ make buildroot-config
ARCH=arm64 make buildroot-build buildroot-tidy
~~~

`buildroot-tidy` is a special rule, that saves diskspace by deleting
files that are not needed to run kgdbtest.

Once `buildroot-config` has been run it is possible to run all buildroot
rules directly from the build directory:

~~~
make -C buildroot/arm64 menuconfig
~~~

Choosing a cross-toolset
------------------------

kgdbtest does not impose any additional requirements beyond the
normal kbuild toolset discovery variables such as `ARCH` and
`CROSS_COMPILE`.

In general you should use whatever toolset you usually use for kernel
builds as the basis for any kgdb testing that you undertake.

If you are working on an architecture for which you do not have a
cross-compiler already installed then the buildroot tools for that
architecture can be used. For example:

~~~
ARCH=arm
CROSS_COMPILE=$PWD/buildroot/arm/host/bin/arm-linux-
export ARCH CROSS_COMPILE
~~~

Running tests
-------------

kgdbtest currently relies upon external environment variables. These are
set up automatically by the `Makefile`.

Assuming `$KGDBTESTDIR` points to the directory where kgdbtest is
installed, then from a pristine (or mrproper'ed) kernel source
directory try:

~~~
make -C $KGDBTESTDIR
~~~

This will run the default `test` rule, which will scan kgdbtest for all 
available tests and run them.

The Makefile behaviour can be made more verbose using `V=1` or `V=2`. At
level 1 the names of each test case are displayed as the test is run.
At level 2 all stdio capture is disabled, meaning the pexpect output
will be displayed live as the test runs.

The set of tests can be restricted using `K=<condition>`. A condition is
either a sub-string to match in the test name or a python operator. For
example:

~~~
make -C $KGDBTESTDIR V=2 K='kgdb and smoke'
~~~

git bisect
----------

By default kgdbtest will automatically configure and build the kernel
under test. This can be problematic for running automated git bisection
(`git bisect run`) because git cannot easily distinguish between an
untestable kernel revision and a failed test.

There are multiple ways to work around this but one simple approach is
to run the test suite twice, one with a "smoke test" job and the other
to run real tests. If the smoke test fails we can return an error
code that causes the bisection to skip the selected version (without
marking it good or bad).

For example the following simple wrapper script allows kgdbtest to be
used to manage a bisect.

~~~ sh
#
# kgdbtest-wrapper.sh
#
# Help run kgdbtest from git bisect run. For example:
#
#   git bisect run kgdbtest-wrapper.sh K='kdb and tab_complete' V=2
#

# Run a basic nop test... skip this revision if this fails
make -C ../kgdbtest "$@" K='kdb and nop'
[ 0 -ne $? ] && exit 125

# Now run the test that was requested
make -C ../kgdbtest "$@"
[ 0 -ne $? ] && exit 1
~~~

Interacting with the kernel debugger
------------------------------------

kgdbtest also provides a quick means to fire up a kernel and interact
with a kernel debugger. This is useful for ad-hoc experiments and to
gather information to add new tests to kgdbtest itself.

To launch a kernel and interact with kdb try:

~~~
make -C $KGDBTESTDIR interact
~~~

Alternatively if you wish to interact via kgdb try:

~~~
make -C $KGDBTESTDIR interact K=kgdb
~~~

This will launch the kernel (which will stop and wait for connection
from remote gdb). In the scroll back buffer you should find a canned
gdb command to run from another terminal. For example, for an arm64
kernel the canned command will look like (and can easily be search for
by the `>>> ` prefix:

~~~
...
+ (cd mod-rootfs; find . | cpio -H newc -AoF ../rootfs.cpio)
101159 blocks
+ gzip -f rootfs.cpio

>>> (cd /home/drt/Development/Kernel/linux/build-arm64; aarch64-linux-gnu-gdb vmlinux -ex "set pagination 0" -ex "target extended-remote |socat - UNIX:ttyS1.sock")

+| qemu-system-aarch64 -accel tcg,thread=multi  -M virt,gic_version=3 -cpu cortex-a57 -kernel arch/arm64/boot/Image -m 1G -smp 2 -nographic -monitor none -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon -chardev socket,id=ttyS1,path=ttyS1.sock,server,nowait -serial chardev:ttyS1 -initrd rootfs.cpio.gz -append " console=ttyAMA0,115200 kgdboc=ttyAMA1 nokaslr kgdbwait"
[    0.000000] Booting Linux on physical CPU 0x0000000000 [0x411fd070]
...
~~~

Finally the `nowait` keyword is also available and will prevent
`kgdbwait` appearing on the kernel command line when the system
boots:

~~~
make -C $KGDBTESTDIR interact K='nowait'
make -C $KGDBTESTDIR interact K='kgdb nowait'
~~~
