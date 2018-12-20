import kbuild
import ktest
import pytest

@pytest.fixture(scope="module")
def kernel():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu(kdb=False)

	console = qemu.console
	console.expect_boot()
	console.expect_busybox()

	# Older kernels have no async progress display so for these
	# kernels we just set a very long timeout (which means failures
	# will take a long time to report too)
	if kbuild.get_version() < (4, 17):
		console.timeout *= 10
		print('Kernel is below v4.17, extended timeout to {}'.format(
			console.timeout))

	yield qemu

	qemu.close()

#@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm'), run = True,
#		   reason = 'Hangs during concurrency tests')

def test_kgdbts_V1(kernel):
	'''
	From drivers/misc/kgdbts.c:

	2) After the system boot run the basic test.
	   echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts
	'''
	kernel.console.sendline('echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts')
	choice = kernel.console.expect(['ERROR', 'Registered I/O driver kgdbts'])
	assert choice
	choices = [ 'WARNING.*kgdbts\.c', 'kgdbts:RUN',
			'Unregistered I/O driver kgdbts']
	choice = 0
	while choice != 2:
		choice = kernel.console.expect(choices)
		assert choice

	kernel.console.expect_prompt()

def test_kgdbts_V1S10000(kernel):
	'''
	From drivers/misc/kgdbts.c:

	3) Run the concurrency tests.  It is best to use n+1
	   while loops where n is the number of cpus you have
	   in your system.  The example below uses only two
	   loops.

	   ## This tests break points on sys_open
	   while [ 1 ] ; do find / > /dev/null 2>&1 ; done &
	   while [ 1 ] ; do find / > /dev/null 2>&1 ; done &
	   echo kgdbts=V1S10000 > /sys/module/kgdbts/parameters/kgdbts
	   fg # and hit control-c
	   fg # and hit control-c
	'''
	kernel.console.sendline('n=$((`nproc` + 1))')
	kernel.console.sendline('for i in `seq $n`')
	kernel.console.sendline('do')
	kernel.console.sendline('while [ 1 ] ; do find / > /dev/null 2>&1 ; done &')
	kernel.console.sendline('done')
	kernel.console.expect_prompt()
	kernel.console.sendline('jobs | tee j')
	kernel.console.expect_prompt()
	kernel.console.sendline('[ `cat j | wc -l` -eq $n ] && [ $n -gt 1 ] && echo OK || echo FAILED')
	choice = kernel.console.expect(['FAILED', 'OK'])
	assert choice
	kernel.console.expect_prompt()

	kernel.console.sendline('echo kgdbts=V1S10000 > /sys/module/kgdbts/parameters/kgdbts')
	#kernel.console.sendline('echo kgdbts=V1S1000 > /sys/module/kgdbts/parameters/kgdbts')
	choice = kernel.console.expect(['ERROR', 'Registered I/O driver kgdbts'])
	assert choice

	choices = [ 'WARNING.*kgdbts\.c', 'kgdbts:RUN',
			'Unregistered I/O driver kgdbts']
	choice = 0
	while choice != 2:
		choice = kernel.console.expect(choices)
		assert choice

	# TODO: We'd like to expect_prompt() here but until it has resync
	#       support its too risky!

	kernel.console.sendline('for i in `seq $n`; do kill %$i; done')
	kernel.console.expect_prompt()

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm64'), run = True,
		   reason = 'Unexpected kernel single-step exception at EL1')
def test_kgdbts_V1F1000(kernel):
	'''
	From drivers/misc/kgdbts.c:

	   ## This tests break points on do_fork
	   while [ 1 ] ; do date > /dev/null ; done &
	   while [ 1 ] ; do date > /dev/null ; done &
	   echo kgdbts=V1F1000 > /sys/module/kgdbts/parameters/kgdbts
	   fg # and hit control-c
	'''
	kernel.console.sendline('n=$((`nproc` + 1))')
	kernel.console.sendline('for i in `seq $n`')
	kernel.console.sendline('do')
	kernel.console.sendline('while [ 1 ] ; do date > /dev/null 2>&1 ; done &')
	kernel.console.sendline('done')
	kernel.console.expect_prompt()
	kernel.console.sendline('jobs | tee j')
	kernel.console.expect_prompt()
	kernel.console.sendline('[ `cat j | wc -l` -eq $n ] && [ $n -gt 1 ] && echo OK || echo FAILED')
	choice = kernel.console.expect(['FAILED', 'OK'])
	assert choice
	kernel.console.expect_prompt()

	kernel.console.sendline('echo kgdbts=V1F1000 > /sys/module/kgdbts/parameters/kgdbts')
	choice = kernel.console.expect(['ERROR', 'Registered I/O driver kgdbts'])
	assert choice

	choices = [ 'WARNING.*kgdbts\.c', 'kgdbts:RUN',
			'Unregistered I/O driver kgdbts']
	choice = 0
	while choice != 2:
		choice = kernel.console.expect(choices)
		assert choice

	# TODO: We'd like to expect_prompt() here but until it has resync
	#       support its too risky!

	kernel.console.sendline('for i in `seq $n`; do kill %$i; done')
	kernel.console.expect_prompt()
