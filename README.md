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

kcontext requires a few special command lines tools together with some
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
filesystem from scratch. The Makefile also has a few convience
rules to help construct the filesystem.

~~~
ARCH=arm BUILDROOT=/path/to/buildroot/ make buildroot-config
ARCH=arm make buildroot

ARCH=arm64 BUILDROOT=/path/to/buildroot/ make buildroot-config
ARCH=arm64 make buildroot

ARCH=x86 BUILDROOT=/path/to/buildroot/ make buildroot-config
ARCH=x86 make buildroot
~~~

Alternatively once buildroot-config has been run it is possible
to run all buildroot rules directly from the build directory:

~~~
make -C buildroot/arm menuconfig
~~~

Finally the Makefile has a special rule, `buildroot-tidy`, that
saves diskspace by deleting files that are not needed to run
kcontext.

Running tests
-------------

kgdbtest currently relies upon external environment variables. These are
set up automatically by the `Makefile`.

Assuming kgdbtest is installed in
$HOME/Projects/daniel-thompson/kgdbtest, then from a kernel source 
directory (without anything "valuable" in the current .config) try:

~~~
make -C $HOME/Projects/daniel-thompson/kgdbtest
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
make -C $HOME/Projects/daniel-thompson/kgdbtest V=2 K='kgdb and smoke'
~~~
