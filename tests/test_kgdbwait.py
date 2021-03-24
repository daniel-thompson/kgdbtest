import kbuild
import ktest
import pytest

@pytest.fixture(scope='module')
def build():
	kbuild.config(kgdb=True)
	kbuild.build()

@pytest.fixture
def kdb(build):
	qemu = ktest.qemu(append='kgdbwait')

	console = qemu.console
	console.expect('Linux version.*$')
	console.expect('Calibrating delay loop')

	yield qemu

	qemu.close()

@pytest.fixture
def kgdb(build):
	qemu = ktest.qemu(second_uart=True, gdb=True, append='kgdbwait')

	qemu.console.expect('Linux version.*$')
	qemu.console.expect('Calibrating delay loop')
	qemu.console.expect('kdb>')
	qemu.debug.connect_to_target()

	yield qemu

	qemu.close()


@pytest.mark.parametrize('fn', (
	'panic',
	'kdb_init',
))
def test_kdb_breakpoint(kdb, fn):
	c = kdb.console.enter_kdb(sysrq=False)

	c.sendline(f'bp {fn}')
	c.expect(f'Instruction.*BP.*{fn}')
	c.expect('is enabled')
	c.expect_prompt()

	c.exit_kdb(shell=False)
	c.expect_busybox()

	c.enter_kdb()
	c.sendline('bc 0')
	c.expect('Breakpoint.*cleared')
	c.expect_prompt()

@pytest.mark.parametrize('fn', (
	'panic',
	'kdb_init',
))
def test_kgdb_breakpoint(kgdb, fn):
	c, d = kgdb.enter_gdb(sysrq=False)

	d.sendline(f'break {fn}')
	d.expect('Breakpoint 1')
	d.expect_prompt()

	kgdb.exit_gdb(shell=False)
	c.expect_busybox()

	kgdb.enter_gdb()
	d.sendline(f'clear {fn}')
	d.expect('Deleted breakpoint 1')
	d.expect_prompt()

	kgdb.exit_gdb()
