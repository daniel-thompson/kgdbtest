import kbuild
import ktest
import pytest

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm64' and
                                kbuild.get_version() < (4, 17)),
		   reason = 'Thread 10 has a PC of 0x0 (so cannot unwind)')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'),
		   reason = 'inconsistent lock state')
def test_kgdb():
	'''High-level kgdb smoke test.

	Tour a number of kgdb features to prove that basic functionality
	if working OK.
	'''

	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu(second_uart=True, gdb=True, append='kgdbwait')
	console = qemu.console
	gdb = qemu.debug

	console.expect_boot(want_gdb_message=True)
	gdb.connect_to_target()

	gdb.send('where\r')
	gdb.expect('kgdb_initial_breakpoint')
	gdb.expect(['init_kgdboc', 'configure_kgdboc'])
	gdb.expect_prompt()

	gdb.send('break do_sys_open\r')
	gdb.expect_prompt()

	gdb.send('continue\r')
	gdb.expect('hit Breakpoint')
	gdb.expect_prompt()

	gdb.send('info registers\r')
	# If the PC is not automatically shown symbolically in a
	# register dump then we must look it up explicitly.
	if kbuild.get_arch() in ('mips',):
		gdb.expect_prompt()
		gdb.send('info symbol $pc\r')
	# On x86_64 the PC lookup for this is __x64_sys_open (and on mips
	# it can be sys_open so we don't expect the 'do_'!
	gdb.expect('sys_open')
	gdb.expect_prompt()

	gdb.send('info thread\r')
	gdb.expect('oom_reaper')
	gdb.expect_prompt()

	gdb.send('thread 10\r')
	gdb.expect_prompt()
	gdb.send('where\r')
	gdb.expect('kthread')
	gdb.expect(['ret_from_fork', 'ret_from_kernel_thread', 'riscv.*entry[.]S'])
	gdb.expect_prompt()

	gdb.send('delete 1\r')
	gdb.expect_prompt()

	gdb.send('continue\r')
	console.expect_busybox()

	qemu.close()
