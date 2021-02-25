#!/usr/bin/env python3

import argparse
import kbuild
import ktest
import sys

def main(argv):
	kgdb = 'kgdb' in argv[1:]
	nowait = 'nowait' in argv[1:]
	gfx = 'gfx' in argv[1:] or 'graphics' in argv[1:]

	configs = []
	args = []

	for arg in argv[1:]:
		if arg in ('kgdb', 'nowait', 'gfx', 'graphics'):
			continue

		# UPPERCASE= is treated as a config options,
		# lowercase= or MixedCased= becomes a kernel option

		stem = arg.split('=')[0]
		if stem == stem.upper():
			configs.append(arg)
		else:
			args.append(arg)

	if not nowait:
		args.append('kgdbwait')

	kbuild.config(kgdb=True, extra_config=configs)
	kbuild.build()
	ktest.qemu(interactive=True,
		   gdb=kgdb,
		   gfx=gfx,
		   append=' '.join(args),
		   second_uart=kgdb)

if __name__ == '__main__':
	try:
		sys.exit(main(sys.argv))
	except KeyboardInterrupt:
		sys.exit(1)
	sys.exit(127)
