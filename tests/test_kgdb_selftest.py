import kbuild
import ktest
import pytest

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm64'),
		   reason = 'Unexpected kernel single-step exception at EL1',
		   run = False)
def test_selftest():
	kbuild.config(kgdb=True)
	kbuild.build()

	#
	# From drivers/misc/kgdbts.c:
	#
	# When developing a new kgdb arch specific implementation
	# or using these tests for the purpose of regression
	# testing, several invocations are required.
	#
	# 1) Boot with the test suite enabled by using the kernel arguments
	#    "kgdbts=V1F100 kgdbwait"
	#

	qemu = ktest.qemu(kdb=False, append='kgdbwait kgdbts=V1F100')
	console = qemu.console

	console.expect('Registered I/O driver kgdbts')
	console.expect('Entering kdb')

	# Check that the self test starts to run. The failure detect
	# relies on all error paths calling WARN_ON().
	choices = ['WARNING.*kgdbts\.c', 'kgdbts:RUN']
	choice = console.expect(choices)
	assert choices

	# Ordering is difficult here since the Unregistered I/O... message
	# is aynschnronous. We solve that just by waiting for all of the
	# following strings to appear (in any order).
	choices += [
		'##INVALID##',
		'Unregistered I/O driver kgdbts',
		'Freeing unused kernel memory',
		'Starting logging',
		'OK',
		'Welcome to Buildroot',
		'buildroot login:',
	]

	num_forks = 0
	while len(choices) > 3:
		print(choices)
		choice = console.expect(choices)
		assert choices
		if 'login:' in choices[choice]:
			console.sendline('root')
			# After logging in then the prompt becomes a
			# valid choice (before that it's too easy to
			# mis-match)
			choices[2] = '#'
		elif '#' in choices[choice]:
			# Cause a sys_fork (if there are less than 100 forks
			# during the boot sequence the self test we started at
			# boot will not complete)
			console.sendline('date')
			num_forks += 1
			assert num_forks < 100

		if choice >= 3:
			del choices[choice]

	console.expect_prompt()

	#
	# From drivers/misc/kgdbts.c:
	#
	# 2) After the system boot run the basic test.
	#    echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts
	#

	console.sendline('echo kgdbts=V1 > /sys/module/kgdbts/parameters/kgdbts')
	choice = console.expect(['ERROR', 'Registered I/O driver kgdbts'])
	assert choice
	choices = [ 'WARNING.*kgdbts\.c', 'kgdbts:RUN',
			'Unregistered I/O driver kgdbts']
	choice = 0
	while choice != 2:
		choice = console.expect(choices)
		assert choices

	console.expect_prompt()

	#
	# From drivers/misc/kgdbts.c:
	#
	# 3) Run the concurrency tests.  It is best to use n+1
	#    while loops where n is the number of cpus you have
	#    in your system.  The example below uses only two
	#    loops.
	#
	#    ## This tests break points on sys_open
	#    while [ 1 ] ; do find / > /dev/null 2>&1 ; done &
	#    while [ 1 ] ; do find / > /dev/null 2>&1 ; done &
	#    echo kgdbts=V1S10000 > /sys/module/kgdbts/parameters/kgdbts
	#    fg # and hit control-c
	#    fg # and hit control-c
	#

	console.sendline('n=$((`nproc` + 1))')
	console.sendline('for i in `seq $n`')
	console.sendline('do')
	console.sendline('while [ 1 ] ; do find / > /dev/null 2>&1 ; done &')
	console.sendline('done')
	console.expect_prompt()
	console.sendline('jobs | tee j')
	console.expect_prompt()
	console.sendline('[ `cat j | wc -l` -eq $n ] && [ $n -gt 1 ] && echo OK || echo FAILED')
	choice = console.expect(['FAILED', 'OK'])
	assert choice
	console.expect_prompt()

	console.sendline('echo kgdbts=V1S10000 > /sys/module/kgdbts/parameters/kgdbts')
	#console.sendline('echo kgdbts=V1S1000 > /sys/module/kgdbts/parameters/kgdbts')

	choice = 0
	while choice != 2:
		choice = console.expect(choices)
		assert choices

	# TODO: We'd like to expect_prompt() here but until it has resync
	#       support its too risky!

	console.sendline('for i in `seq $n`; do kill %$i; done')
	console.expect_prompt()

	#
	# From drivers/misc/kgdbts.c:
	#
	#    ## This tests break points on do_fork
	#    while [ 1 ] ; do date > /dev/null ; done &
	#    while [ 1 ] ; do date > /dev/null ; done &
	#    echo kgdbts=V1F1000 > /sys/module/kgdbts/parameters/kgdbts
	#   fg # and hit control-c
	#

	console.sendline('n=$((`nproc` + 1))')
	console.sendline('for i in `seq $n`')
	console.sendline('do')
	console.sendline('while [ 1 ] ; do date > /dev/null 2>&1 ; done &')
	console.sendline('done')
	console.expect_prompt()
	console.sendline('jobs | tee j')
	console.expect_prompt()
	console.sendline('[ `cat j | wc -l` -eq $n ] && [ $n -gt 1 ] && echo OK || echo FAILED')
	choice = console.expect(['FAILED', 'OK'])
	assert choice
	console.expect_prompt()

	console.sendline('echo kgdbts=V1F1000 > /sys/module/kgdbts/parameters/kgdbts')

	choice = 0
	while choice != 2:
		choice = console.expect(choices)
		assert choices

	# TODO: We'd like to expect_prompt() here but until it has resync
	#       support its too risky!

	console.sendline('for i in `seq $n`; do kill %$i; done')
	console.expect_prompt()

	qemu.close()
