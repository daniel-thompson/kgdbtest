import kbuild
import ktest
import pytest
from types import MethodType

def set_cmd_enable(self, value):
	exit_and_reenter = self.inside_kdb()
	if exit_and_reenter:
		self.exit_kdb()

	value = str(value)

	self.sendline()
	self.expect_prompt()
	self.sendline(f'echo {value} > /sys/module/kdb/parameters/cmd_enable')
	self.expect_prompt()

	self.sendline('cat /sys/module/kdb/parameters/cmd_enable')
	self.expect(value)
	self.expect_prompt()

	if exit_and_reenter:
		self.enter_kdb()

@pytest.fixture(scope="module")
def kdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu()

	console = qemu.console
	console.expect_boot()
	console.expect_busybox()
	# Now we have booted our expectations should be met quickly
	console.timeout = 5

	console.set_cmd_enable = MethodType(set_cmd_enable, console)

	yield qemu

	qemu.close()

@pytest.mark.xfail(condition = kbuild.get_version() < (5, 7),
		   reason = 'Not implemented until 5.7-rc1')
def test_set_prompt(kdb):
	c = kdb.console

	# Check for permission denied
	c.set_cmd_enable(0)
	c.enter_kdb()
	try:
		c.sendline('set PROMPT=O\\K\\ kdb>\\ ')
		c.expect('Permission denied')
		c.expect_prompt()
	finally:
		c.exit_kdb()

	# Check for permission granted (and restore the prompt)
	c.set_cmd_enable(1)
	c.enter_kdb()
	try:
		c.sendline('set PROMPT=O\\K\\ kdb>\\ ')
		c.expect('OK')
		c.expect_prompt()

		c.sendline('set PROMPT=[%d]kdb>\\ ')
		c.expect_prompt()
	finally:
		c.exit_kdb()

def test_set_arbitrary(kdb):
	c = kdb.console

	# Check permission is *not* denied
	c.set_cmd_enable(0)
	c.enter_kdb()
	try:
		c.sendline('set ARBITRARY=1')
		choice = c.expect(['Permission denied', 'kdb>'])
		assert choice
	finally:
		c.exit_kdb()
		c.set_cmd_enable(1)

def test_md(kdb):
	c = kdb.console.enter_kdb()
	try:
		# Check md is enabled by default
		c.sendline('md4c1 kdb_cmd_enabled')
		c.expect(' 00000001')
		c.expect_prompt()

		# Check we can revoke permission
		c.set_cmd_enable(0)
		c.sendline('md4c1 kdb_cmd_enabled')
		c.expect('Permission denied')
		c.expect_prompt()
	finally:
		c.exit_kdb()
		c.set_cmd_enable(1)

def test_mm(kdb):
	c = kdb.console.enter_kdb()
	try:
		# Check mm is enabled by default
		c.sendline('mm4c1 kdb_cmd_enabled 0')
		c.expect(' = 0x0')
		c.expect_prompt()

		# If the above command worked then we will no longer
		# have permission to modify memory ;-)
		c.sendline('mm4c1 kdb_cmd_enabled 1')
		c.expect('Permission denied')
		c.expect_prompt()
	finally:
		c.exit_kdb()
		c.set_cmd_enable(1)
