#!/usr/bin/env python3

import argparse
import kbuild
import ktest
import sys

def main(argv):
	kgdb = 'kgdb' in argv[1:]
	nowait = 'nowait' in argv[1:]

	kbuild.config(kgdb=True)
	kbuild.build()
	ktest.qemu(interactive=True,
		   gdb=kgdb,
		   append='' if nowait else 'kgdbwait',
		   second_uart=kgdb)

if __name__ == '__main__':
	try:
		sys.exit(main(sys.argv))
	except KeyboardInterrupt:
		sys.exit(1)
	sys.exit(127)
