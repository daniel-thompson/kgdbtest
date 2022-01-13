import kbuild
import ktest
import pytest

#@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm'), run = True,
#		   reason = 'Hangs during concurrency tests')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'), run = True,
		   reason = 'KGDB: BP remove failed')
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

        # We expect the test suite to start whilst initializing modules
        # so we must skip the late boot expectations.
	console.expect_boot(skip_late=True)

	# Older kernels have no async progress display so for these
	# kernels we just set a very long timeout (which means failures
	# will take a long time to report too)
	if kbuild.get_version() < (4, 17):
		console.timeout *= 5
		print('Kernel is below v4.17, extended timeout to {}'.format(
			console.timeout))

	console.expect('Registered I/O driver kgdbts')

	# Check that the self test starts to run. The failure detect
	# relies on all error paths calling WARN_ON().
	choices = ['WARNING.*kgdbts[.]c.*[/r/n]', 'KGDB: BP remove failed', 'kgdbts:RUN']
	choice = console.expect(choices)
	assert choice > 1

	# Ordering is difficult here since the Unregistered I/O... message
	# is aynschnronous. We solve that just by waiting for all of the
	# following strings to appear (in any order).
	choices += [
		'##INVALID##',
		'Unregistered I/O driver kgdbts',
		'Freeing unused kernel.*memory',
		'Starting.*log',
		'OK',
		'Welcome to Buildroot',
		'buildroot login:',
	]

	num_forks = 0
	while len(choices) > 4:
		choice = console.expect(choices)
		if choice > 3:
			print(f"Found '{console.match.group(0)}', still waiting for {choices[4:]}")
                # HACK: Ignore problems with hw_break (we allow kgdbts_V1
                #       to report them and would like to see the results
                #       of the single step tests here)
		assert choice > 1 or 'hw_break' in console.match.group(0)
		if 'login:' in choices[choice]:
			console.sendline('root')
			# After logging in then the prompt becomes a
			# valid choice (before that it's too easy to
			# mis-match)
			choices[3] = '#'
		elif '#' in choices[choice]:
			# Cause a sys_fork (if there are less than 100 forks
			# during the boot sequence the self test we started at
			# boot will not complete)
			console.sendline('date')
			num_forks += 1
			assert num_forks < 100

		if choice >= 4:
			del choices[choice]

	console.expect_prompt()

	qemu.close()
