import kbuild
import ktest
import pytest

@pytest.mark.xfail(condition = kbuild.get_version() < (5, 8), run = False,
                   reason = 'Not implemented until 5.8-rc1')
@pytest.mark.skipif(kbuild.get_arch() not in ('arm', 'arm64', 'x86'),
                   reason = 'earlycon not configured for this arch')
def test_earlycon():
	kbuild.config(kgdb=True)
	kbuild.build()

	# Handle platforms that cannot auto-configure the earlycon
	arch = kbuild.get_arch()
	if 'x86' == arch:
		earlycon = "earlycon=uart8250,io,0x3f8"
	elif 'arm' ==  arch:
		earlycon = "earlycon=pl011,0x1c090000"
	else:
		earlycon = "earlycon"

	qemu = ktest.qemu(append=f'{earlycon} kgdboc_earlycon kgdbwait')
	console = qemu.console

	def expect_and_page(c, needle):
		choices = [needle, 'more>']

		choice = c.expect(choices)
		while choice == 1:
			c.send(' ')
			choice = c.expect(choices)
			print(choice)
			print(choices)
		print("Done")


	# This test is too low level to use the regular console helpers
	console.expect_kdb()
	console.sendline_kdb('bt')
	if 'x86' in kbuild.get_arch():
		# x86 uses earlycon with arguments and supports very early
		# consoles, expect to break whilst parsing early parameters
		expect_and_page(console, 'parse_early_param')
	elif 'arm64' in kbuild.get_arch():
		# Currently arm64 doesn't implement ARCH_HAS_EARLY_DEBUG
		# expect_and_page(console, 'console_init')
		pass
	expect_and_page(console, 'start_kernel')
	console.expect_kdb()
	console.sendline_kdb('go')

        # At this point kgdb has already fired up (on the earlycon). That
        # means the early boot messages have already passed by, hence we
        # need to set skip_early in the boot expectations.
	qemu.console.expect_boot(skip_early=True)
	qemu.console.expect_busybox()
	qemu.close()
