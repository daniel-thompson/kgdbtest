import kbuild
import ktest
import pytest
from types import MethodType

def enter_gdb(self):
	(console, gdb) = (self.console, self.debug)

	console.sysrq('g')
	gdb.expect_prompt()

	return (console, gdb)

def exit_gdb(self):
	(console, gdb) = (self.console, self.debug)

	gdb.sendline('continue')

	# We should now be running again but whether or not we get a
	# prompt depends on how the debugger was triggered. This
	# technique ensures we are fully up to date with the input.
	console.send('echo "FORCE"_"IO"_"SYNC"\r')
	console.expect('FORCE_IO_SYNC')
	console.expect_prompt()

@pytest.fixture(scope="module")
def kgdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu(second_uart=True, gdb=True)

	qemu.enter_gdb = MethodType(enter_gdb, qemu)
	qemu.exit_gdb = MethodType(exit_gdb, qemu)

        # Wait for qemu to boot
	qemu.console.expect_boot()
	qemu.console.expect_busybox()

        # Ensure debugger it attached
	qemu.console.sysrq('g')
	qemu.debug.connect_to_target()
	qemu.debug.send('continue\r')
	qemu.console.send('\r')
	qemu.console.expect_prompt()

	yield qemu

	qemu.close()

def test_nop(kgdb):
	(console, gdb) = kgdb.enter_gdb()
	kgdb.exit_gdb()

def test_continue(kgdb):
	(console, gdb) = (kgdb.console, kgdb.debug)
	
	console.sysrq('g')
	gdb.expect_prompt()

	gdb.send('continue\r')
	console.send('\r')
	console.expect_prompt()

def test_info_registers(kgdb):
	(console, gdb) = kgdb.enter_gdb()

	gdb.sendline('info registers')
	# Without doing architecture specific checks we can only really
	# look for the PC/IP being inside the kgdb_breakpoint function.
	gdb.expect('kgdb_breakpoint')
	gdb.expect_prompt()

	kgdb.exit_gdb()

def test_info_target(kgdb):
	(console, gdb) = kgdb.enter_gdb()

	gdb.sendline('info target')
	gdb.expect('Debugging a target over a serial line')
	gdb.expect_prompt()

	kgdb.exit_gdb()
