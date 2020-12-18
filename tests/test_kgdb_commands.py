import kbuild
import ktest
import pytest
from types import MethodType

@pytest.fixture(scope="module")
def kgdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu(second_uart=True, gdb=True)

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
	try:
		gdb.sendline('info registers')
		# Without doing architecture specific checks we can
		# only really look for the PC/IP being inside the
		# kgdb_breakpoint function (and even that doesn't work
		# for architectures where the PC doesn't get shown
		# symbolically).
		if kbuild.get_arch() not in ('mips',):
			gdb.expect('kgdb_breakpoint')
	finally:
		gdb.expect_prompt()
		kgdb.exit_gdb()

def test_info_target(kgdb):
	(console, gdb) = kgdb.enter_gdb()
	try:
		gdb.sendline('info target')
		gdb.expect('Debugging a target over a serial line')
	finally:
		gdb.expect_prompt()
		kgdb.exit_gdb()

def test_info_thread(kgdb):
	(console, gdb) = kgdb.enter_gdb()
	try:
		gdb.sendline('info thread')
		# One of the CPUs should be stopped in kgdb_breakpoint()
		gdb.expect('[(].*CPU.*[)][^\r\n]*kgdb_breakpoint')

		# Look for a few common thread names
		gdb.expect('[(]init[)]')
		gdb.expect('[(]kthreadd[)]')
		gdb.expect('[(]kworker/0:0[)]')

		# Check the shell process is in kgdb_breakpoint()
		gdb.expect('[(]sh[)][^\r\n]*kgdb_breakpoint')
	finally:
		gdb.expect_prompt()
		kgdb.exit_gdb()

def test_print_variable(kgdb):
	(console, gdb) = kgdb.enter_gdb()
	try:
		gdb.sendline('print kgdb_single_step')
		assert 0 == gdb.expect(['[$][0-9]+ = 0',
					'Cannot access memory at address'])
	finally:
		gdb.expect_prompt()
		kgdb.exit_gdb()
