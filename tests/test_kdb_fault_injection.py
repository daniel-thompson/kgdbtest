import kbuild
import ktest
import pytest

@pytest.fixture(scope="module")
def kdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu()

	console = qemu.console
	console.expect_boot()
	console.expect_busybox()

	yield qemu

	qemu.close()

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'mips'),
                   reason = "Triggers breakpoint twice", run = False)
# RISC-V bug reported here: https://lore.kernel.org/all/ZJ2PBosSQtSX28Mf@wychelm/
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'riscv' and kbuild.get_version() >= (6, 4)),
                   reason = "Panics on resume")
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'),
                   reason = "Triggers breakpoint twice", run = False)
def test_BUG(kdb):
	'''
	Test how kdb reacts to a BUG()
	'''

	# Must use /bin/echo... if we use a shell built-in then the
	# kernel will kill off the shell when we resume
	kdb.console.sendline('/bin/echo BUG > /sys/kernel/debug/provoke-crash/DIRECT')

	kdb.console.expect('Entering kdb')
	# If we timeout here its probably because we've returned to the
	# shell prompt... thankfully that means we don't need any custom
	# error recovery to set us up for the next test!
	kdb.console.expect_kdb()

	kdb.console.send('go\r')
	kdb.console.expect('Catastrophic error detected')
	kdb.console.expect('type go a second time')
	kdb.console.expect_kdb()

	kdb.console.send('go\r')
	kdb.console.expect_prompt()

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'mips'),
                   reason = "Triggers breakpoint twice", run = False)
# RISC-V bug reported here: https://lore.kernel.org/all/ZJ2PBosSQtSX28Mf@wychelm/
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'riscv' and kbuild.get_version() >= (6, 4)),
                   reason = "Panics on resume")
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'x86'),
                   reason = "Triggers breakpoint twice", run = False)
def test_BUG_again(kdb):
	'''
	Repeat the BUG() test.

	This test effectively ensures there is nothing "sticky" about
	continuing past the catastrophic error (i.e. this is an important
	property for test suite robustness.
	'''
	test_BUG(kdb)

# RISC-V bug reported here: https://lore.kernel.org/all/ZJ2PBosSQtSX28Mf@wychelm/
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'riscv' and kbuild.get_version() >= (6, 4)),
                   reason = "Previous BUG() invocation kills this test")
def test_WARNING(kdb):
	'''
	Test that kdb does *not* enter during a WARN_ON()
	'''

	kdb.console.sendline('echo WARNING > /sys/kernel/debug/provoke-crash/DIRECT')
	kdb.console.expect('WARNING')
	#kdb.console.expect('lkdtm_WARNING')

	# riscv doesn't issue stack trace on warnings
	if kbuild.get_arch() != 'riscv':
		kdb.console.expect('vfs_write')

	kdb.console.expect_prompt()
