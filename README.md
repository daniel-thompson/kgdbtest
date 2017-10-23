kcontest - kernel console tests
===============================

Collection of fully automated kernel tests that test aspects of the
kernel that rely upon having access to a console. In particular this
allows us to test tools such as kgdb/kdb.

kcontest is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either [version 2 of the
License](LICENSE.md), or (at your option) any later version.

Prerequisites
-------------

kcontext requires a few special command lines tools together with some
additional python libraries.

On Fedora systems these can be installed as follows:

~~~
sudo dnf install \
	python3 \
	python3-pexpect \
	python3-pytest \
	socat
~~~

Buildroot
---------

TODO (but see the defconfig files in `buildroot/`).

Running tests
-------------

kcontest currently relies upon external environment variables. These are
set up automatically by the `Makefile`.

Assuming kcontest is installed in $HOME/Projects/kcontest, then from a 
kernel source directory (without anything "valuable" in the
current .config) try:

~~~
make -C $HOME/Projects/kcontest test
~~~

This will scan kcontest for all available tests and run them.
