#!/usr/bin/env python3

import argparse
import kbuild
import ktest
import sys

def main(argv):
	parser = argparse.ArgumentParser()

	parser.add_argument('--kdb', action='store_true',
		help='Interact using kdb')
	parser.add_argument('--kgdb', action='store_true',
		help='Interact using kgdb (in a seperate xterm)')

	args = parser.parse_args(argv[1:])

	# For now we'll ignore args.kdb (until we have args.kgdb we
	# don't really care.

	kbuild.config(kgdb=True)
	kbuild.build()
	ktest.qemu(interactive=True, gdb=args.kgdb, append='kgdbwait', second_uart=args.kgdb)

if __name__ == '__main__':
	try:
		sys.exit(main(sys.argv))
	except KeyboardInterrupt:
		sys.exit(1)
	sys.exit(127)
