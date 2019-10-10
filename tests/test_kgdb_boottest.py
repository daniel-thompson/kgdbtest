import kbuild
import ktest
import pytest

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm'), run = True,
		   reason = 'Hangs during concurrency tests')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm64'), run = True,
		   reason = 'Unexpected kernel single-step exception at EL1')
def test_kgdbts_boot():
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

	# Older kernels have no async progress display so for these
	# kernels we just set a very long timeout (which means failures
	# will take a long time to report too)
	if kbuild.get_version() < (4, 17):
		console.timeout *= 10
		print('Kernel is below v4.17, extended timeout to {}'.format(
			console.timeout))

	console.expect('Registered I/O driver kgdbts')
	console.expect('Entering kdb')

	# Check that the self test starts to run. The failure detect
	# relies on all error paths calling WARN_ON().
	choices = ['WARNING.*kgdbts[.]c', 'kgdbts:RUN']
	choice = console.expect(choices)
	assert choice

	# Ordering is difficult here since the Unregistered I/O... message
	# is aynschnronous. We solve that just by waiting for all of the
	# following strings to appear (in any order).
	choices += [
		'##INVALID##',
		'Unregistered I/O driver kgdbts',
		'Freeing unused kernel.*memory',
		'Starting logging',
		'OK',
		'Welcome to Buildroot',
		'buildroot login:',
	]

	num_forks = 0
	while len(choices) > 3:
		choice = console.expect(choices)
		print('Got {} from {}'.format(choice, choices))
		assert choice
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

	qemu.close()
