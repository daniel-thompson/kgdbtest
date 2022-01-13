import os
import traceback
import subprocess
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

def get_host_arch():
	output = subprocess.check_output('uname -m'.split()).decode()
	if 'aarch64' in output:
		return 'arm64'

    # If we can't prove otherwise then let's assume we have an x86 host
	return 'x86'

def get_arch():
	if 'ARCH' in os.environ:
		return os.environ['ARCH']

	return get_host_arch()

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

def config(kgdb=False, extra_config=None):
	kdir = get_kdir()
	try:
		os.mkdir(kdir)
	except FileExistsError:
		pass
	os.chdir(kdir)

	if 'NOCONFIG' in os.environ or 'NOBUILD' in os.environ :
		return

	arch = get_arch()
	defconfig = 'defconfig'
	if 'NOWERROR' not in os.environ:
		postconfig = '--enable WERROR'
	if 'NODEFCONFIG' in os.environ:
		defconfig = None
	elif 'arm' == arch:
		defconfig = 'multi_v7_defconfig'
	elif 'mips' == arch:
		# TODO: Advice from a MIPS guru on a better configuration
		#       (and the corresponding qemu launch command) would
		#       be very welcome.
		defconfig = 'malta_kvm_defconfig generic/64r6.config'
		postconfig += ' --enable CPU_MIPS64_R6 --enable MIPS_CPS'
		postconfig += ' --enable BLK_DEV_INITRD'

		# JFFS2_FS, FRAME_WARN and WERROR don't play nice together
		# (at least on v5.16/mips). Since JFFS2 isn't used or
		# tested by kgdbtest let's just disable it.
		postconfig += ' --disable JFFS2_FS'
	elif 'riscv' == arch:
		postconfig += ' --disable STRICT_KERNEL_RWX'
		postconfig += ' --disable STRICT_MODULE_RWX'
	elif 'x86' == arch:
		defconfig = 'x86_64_defconfig'

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

	self_test = True
	if self_test:
		run('../scripts/config ' +
                        '--enable PROVE_LOCKING ' +
			'--enable DEBUG_ATOMIC_SLEEP ',
			'Cannot enable PROVE_LOCKING and DEBUG_ATOMIC_SLEEP')

	if extra_config:
		with open('.config', 'a') as f:
			for config in extra_config:
				if config.startswith('CONFIG_'):
					print(config, file=f)
				else:
					print(f'CONFIG_{config}', file=f)

	run('make olddefconfig',
		'Cannot finalize kernel configuration')

last_config = None

def build():
	global last_config

	if 'NOBUILD' in os.environ:
		return

	# This is a quick and dirty bit of build avoidance. If the .config is
	# the same as the last time we built the tree then let's avoid all the
	# work.
	with open('.config') as f:
		new_config = f.read()
	if last_config == new_config:
		return
	last_config = new_config

	make = 'make -s -j `nproc` '
	if 'NICEBUILD' in os.environ:
		# Ensure everything the spreads across all CPUs treads lightly
		make = 'nice ' + make

	run(make + 'all',
		'Cannot compile kernel')
	run(make + 'modules_install ' +
		'INSTALL_MOD_PATH=$PWD/mod-rootfs INSTALL_MOD_STRIP=1',
		'Cannot install kernel modules')
	run('unxz -c $KGDBTEST_DIR/buildroot/{}/images/rootfs.cpio.xz > rootfs.cpio'
			.format(get_arch()),
		'Cannot decompress rootfs')
	run('(rm -rf mod-rootfs/*; cd mod-rootfs; find . | cpio -H newc -AoF ../rootfs.cpio)',
		'Cannot copy kernel modules into rootfs')
	# Compressing with xz would be expensive, gzip is enough here
	run('gzip -f rootfs.cpio',
		'Cannot recompress rootfs')

