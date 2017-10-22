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

def test_continue(kgdb):
	(console, gdb) = (kgdb.console, kgdb.debug)
	
	console.sysrq('g')
	gdb.expect_prompt()
	gdb.send('continue\r')
	console.send('\r')
	console.expect_prompt()
