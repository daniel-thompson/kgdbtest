import os
import traceback
import sys

def get_version(short=False):
	makefile = os.environ['KERNEL_DIR'] + '/Makefile'
	with open(makefile) as f:
		for ln in f.readlines():
			if ln.startswith('VERSION'):
				version = int(ln.split('=')[1].strip())
			if ln.startswith('PATCHLEVEL'):
				patchlevel = int(ln.split('=')[1].strip())
			if ln.startswith('SUBLEVEL'):
				sublevel = int(ln.split('=')[1].strip())
			if ln.startswith('EXTRAVERSION'):
				extraversion = ln.split('=')[1].strip()
				break

	return (version, patchlevel, sublevel, extraversion)

def get_arch():
	if 'ARCH' in os.environ:
		return os.environ['ARCH']

	# TODO: Look up host architecture...
	return 'x86'

def get_kdir():
	# HACK: Still trying to come up with a nice way to handle the two
	#       directories involved (kernel and kgdbtest). For now we'll
	#       just hack things and rely on the kgdbtest Makefile to
	#       configure the environment variables we need to get
	#       things right.
	return os.environ['KERNEL_DIR'] + '/build-{}'.format(get_arch())

def get_cross_compile(tool=''):
	if tool:
		cross_tool = 'CROSS_' + tool.upper()
		if cross_tool in os.environ:
			return os.environ[cross_tool]

	if 'CROSS_COMPILE' in os.environ:
		return os.environ['CROSS_COMPILE'] + tool

	return '' + tool



def run(cmd, failmsg=None):
	'''Run a command (synchronously) raising an exception on
	failure.

	'''

	# Automatically manage bisect skipping
	if failmsg:
		try:
			run(cmd)
			return
		except:
			skip(failmsg)

	print('+ ' + cmd)
	(exit_code) = os.system(cmd)
	if exit_code != 0:
		raise Exception

def skip(msg):
	"""Report a catastrophic build error.

        A catastrophic build error occurs when we cannot build the software
        under test. This makes testing of any form impossible. We treat this
        specially (and completely out of keeping with pytest philosophy because
        it allows us to return a special error code that will cause git bisect
        to look for a kernel we can compile.
        """
	traceback.print_exc()
	print('### SKIP: %s ###' % (msg,))
	sys.exit(125)

def config(kgdb=False):
	need_olddefconfig=kgdb

	kdir = get_kdir()
	try:
		os.mkdir(kdir)
	except FileExistsError:
		pass
	os.chdir(kdir)

	if 'NOBUILD' in os.environ:
		return

	arch = get_arch()
	postconfig = None
	if 'NOCONFIG' in os.environ:
		defconfig = None
	elif 'arm' == arch:
		defconfig = 'multi_v7_defconfig'
	elif 'mips' == arch:
		# TODO: Advice from a MIPS guru on a better configuration
		#       (and the corresponding qemu launch command) would
		#       be very welcome.
		defconfig = 'malta_kvm_guest_defconfig generic/64r6.config'
		postconfig = '--enable CPU_MIPS64_R6 --enable MIPS_CPS'
	elif 'x86' == arch:
		defconfig = 'x86_64_defconfig'
	else:
		defconfig = 'defconfig'

	if defconfig:
		run('make -C .. O=$PWD {}'.format(defconfig),
			'Cannot configure kernel (wrong directory)')

	if postconfig:
		run('../scripts/config ' + postconfig,
			'Cannot enable {} specific features'.format(arch))

	if kgdb:
		# TODO (v4.17): Needed in linux-next at present
		#               (and harmless to unaffected kernels)
		run('../scripts/config ' +
                        '--enable RUNTIME_TESTING_MENU',
			'Cannot enable RUNTIME_TESTING_MENU')

		run('../scripts/config ' +
			'--enable DEBUG_INFO ' +
			'--enable DEBUG_FS ' +
                        '--enable KALLSYMS_ALL ' +
			'--enable MAGIC_SYSRQ ' +
			'--enable KGDB --enable KGDB_TESTS ' +
                        '--enable KGDB_KDB --enable KDB_KEYBOARD ' +
                        '--enable LKDTM',
			'Cannot configure kgdb extensions')

	if need_olddefconfig:
		run('make olddefconfig',
			'Cannot finalize kernel configuration')

def build():
	if 'NOBUILD' in os.environ:
		return

	run('make -s -j `nproc` all',
		'Cannot compile kernel')
	run('make -s -j `nproc` modules_install ' +
		'INSTALL_MOD_PATH=$PWD/mod-rootfs INSTALL_MOD_STRIP=1',
		'Cannot install kernel modules')
	run('unxz -c $KGDBTEST_DIR/buildroot/{}/images/rootfs.cpio.xz > rootfs.cpio'
			.format(get_arch()),
		'Cannot decompress rootfs')
	run('(cd mod-rootfs; find . | cpio -H newc -AoF ../rootfs.cpio)',
		'Cannot copy kernel modules into rootfs')
	# Compressing with xz would be expensive, gzip is enough here
	run('gzip -f rootfs.cpio',
		'Cannot recompress rootfs')

