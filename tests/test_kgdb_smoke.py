import kbuild
import ktest

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

	console.expect('Waiting for connection from remote gdb...')
	gdb.connect_to_target()

	gdb.send('where\r')
	gdb.expect('kgdb_initial_breakpoint')
	gdb.expect('do_one_initcall')
	gdb.expect('ret_from_fork')
	gdb.expect_prompt()

	gdb.send('break do_sys_open\r')
	gdb.expect_prompt()

	gdb.send('continue\r')
	gdb.expect('hit Breakpoint')
	gdb.expect_prompt()

	gdb.send('info registers\r')
	gdb.expect('do_sys_open')
	gdb.expect_prompt()

	gdb.send('info thread\r')
	gdb.expect('oom_reaper')
	gdb.expect_prompt()

	gdb.send('thread 10\r')
	gdb.expect_prompt()
	gdb.send('where\r')
	gdb.expect('kthread')
	gdb.expect('ret_from_fork')
	gdb.expect_prompt()

	gdb.send('delete 1\r')
	gdb.expect_prompt()

	gdb.send('continue\r')
	console.expect_busybox()

	qemu.close()
