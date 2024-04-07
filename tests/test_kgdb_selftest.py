import kbuild
import ktest
import pytest

kgdbts_choices = [
	'Unregistered I/O driver kgdbts',
	'kgdbts:RUN',
	'WARNING.*kgdbts[.]c.*[\r\n]',
	'KGDB: BP remove failed',
]
KGDBTS_RUNNING = 1
KGDBTS_WARNING =  2
KGDBTS_FATAL = 3

@pytest.fixture(scope="module")
def build():
	kbuild.config(kgdb=True)
	kbuild.build()

@pytest.fixture()
def kernel(build):
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
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'), run = True,
		   reason = 'hw_access breakpoints not trapping')
def test_kgdbts_V1(kernel):
	'''
	From drivers/misc/kgdbts.c:

	2) After the system boot run the basic test.
	   echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts
	'''
	kernel.console.sendline('echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts')
	choice = kernel.console.expect(['ERROR', 'Registered I/O driver kgdbts'])
	assert choice

	try:
		choice = KGDBTS_RUNNING
		while choice:
			choice = kernel.console.expect(kgdbts_choices)
			assert(choice <= KGDBTS_RUNNING)
	finally:
		count = 100
		while choice >= KGDBTS_RUNNING and \
		      choice < KGDBTS_FATAL and \
		      count:
			choice = kernel.console.expect(kgdbts_choices)
			count -= 1
		kernel.console.expect_prompt()

# These XFAILs do not reproduce reliably but it occurs frequently enough
# to make the suite verdict unreliable so for now we have to mark them
# accordingly. On x86 the failure rate is guestimated at ~15%.
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'riscv'),
		   reason = 'bad unlock balance detected')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'),
		   reason = 'plant and detach test likely to fail')
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

	choice = KGDBTS_RUNNING
	while choice:
		choice = kernel.console.expect(kgdbts_choices)
		if choice == KGDBTS_WARNING and \
		   'hw_break' in kernel.console.match.group(0):
			print('>>> Ignoring hw_break error (will be reported by kgdbtest_V1 instead)\n')
			continue
		assert(choice <= KGDBTS_RUNNING)

	kernel.console.expect_prompt(no_history=True)
	kernel.console.sendline('for i in `seq $n`; do kill %$i; done; sleep 1')
	kernel.console.expect_prompt()

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'riscv'),
		   reason = 'fails approximately ~50% of the time')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'),
		   reason = 'fails approximately ~30% of the time')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm64'),
           reason = 'BUG: scheduling while atomic occasionally when running in CI')
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

	choice = KGDBTS_RUNNING
	while choice:
		choice = kernel.console.expect(kgdbts_choices)
		if choice == KGDBTS_WARNING and \
		   'hw_break' in kernel.console.match.group(0):
			print('>>> Ignoring hw_break error (will be reported by kgdbtest_V1 instead)\n')
			continue
		assert(choice <= KGDBTS_RUNNING)

	kernel.console.expect_prompt(no_history=True)
	kernel.console.sendline('for i in `seq $n`; do kill %$i; done; sleep 1')
	kernel.console.expect_prompt()
