import kbuild
import os
import pexpect
import random
import string
import sys
import time
import warnings
from types import MethodType

def unique_tag(prefix=''):
	"""
	Generate an short string that can be used to synchronize the prompt.

	When we expect a prompt there is a risk we will match a previously issued
	prompt. By forcing a unique(ish) tag to appear in the output we can
	guarantee that we matched the more recently issued prompt.
	"""
	return prefix + ''.join(
		    [random.choice(string.ascii_uppercase) for i in range(8)])

def expect_boot(self, bootloader=()):
	for msg in bootloader:
		self.expect(msg)
	self.expect('Linux version.*$')
	self.expect('Calibrating delay loop')
	self.expect('NET: Registered protocol family 2')
        # We need a wildcard here because some newer kernels now say:
        # "Free unused kernel image memory".
	self.expect('Freeing unused kernel.*memory')

def expect_busybox(self):
	self.expect('Starting logging')
	self.expect('OK')
	self.expect('Welcome to Buildroot')
	self.expect(['debian-[^ ]* login:', 'buildroot login:'])
	self.sendline('root')

	self.expect_prompt()

	self.sendline('mount -t debugfs none /sys/kernel/debug')
	self.expect_prompt()

def expect_prompt(self):
	self.expect('# ')

def sysrq(self, ch):
	"""
	Use the shell to run a sysrq command
	"""
	self.send('echo {} > /proc/sysrq-trigger\r'.format(ch))

def expect_kdb(self, sync=True):
	"""
	Manage the pager until we get a kdb prompt (or timeout)

	It is not usually necessary to call this method directly. When kdb
	is active the methods to enter/exit kdb will replace expect_prompt()
	with this function. This allows test cases to wait for a prompt
	regardless of whether the command interpretter is a shell or kdb.

	Set sync to False for test cases that rely upon a "clean" command
	history and will not trigger the pager. This is useful for testing
	command history and escape sequence handling.
	"""
	if sync:
		if 1 == self.expect(['kdb>', 'more>']):
			self.send('q')
			self.expect('kdb>')

		tag = unique_tag('SYNC_KDB_')
		self.send(tag + '\r')
		self.expect('Unknown[^\r\n]*' + tag)

	self.expect('kdb>')

def enter_kdb(self):
	"""
	Trigger the debugger and wait for the kdb prompt.

	Once we see the prompt we update expect_prompt() accordingly.
	"""
	self.sysrq('g')
	self.expect('Entering kdb')
	self.expect_kdb()

	self.old_expect_prompt = self.expect_prompt
	self.expect_prompt = self.expect_kdb

	# Allow chaining...
	return self

def exit_kdb(self):
	"""
	Revert to normal running.

	This function is intended to be called from a finally: clause
	meaning the current state of the command interpreter and pager
	is unknown. We do our best to robustly recover in order to
	minimise the risk of cascaded failures.
	"""
	if self.expect_prompt == self.expect_kdb:
		# Make sure we break out of the pager (q is enough to break out
		# but if we're *not* in the pager we need the \r to make the q
		# harmless
		self.send('q\r')
		self.expect('kdb>')

		# Now we have got the prompt back we can exit kdb
		self.send('go\r')
		self.expect_prompt = self.old_expect_prompt
	else:
		warnings.warn(UserWarning("Cannot exit from kdb (already exited?)"))
		# If we're not running in kdb its reasonable to look for a shell prompt

	# We should now be running again but whether or not we get a
	# prompt depends on how the debugger was triggered. This
	# technique ensures we are fully up to date with the input.
	tag = unique_tag()
	self.send('echo "SYNC"_"SHELL"_"{}"\r'.format(tag))
	self.expect('SYNC_SHELL_{}'.format(tag))
	self.expect_prompt()

def gdb_connect_to_target(self):
	self.expect_prompt()
	self.send('target extended-remote | socat - UNIX:ttyS1.sock\r')
	self.expect('Remote debugging using')
	self.expect_prompt()

def gdb_expect_prompt(self):
	self.expect('[(]gdb[)] ')
	self.sendline('printf "force_gdb_sync"')
	# No newline means the output here will be unique
	self.expect('force_gdb_sync[^\r\n]*[(]gdb[)] ')

def bind_methods(c, d):
	# TODO: Can we use introspection to find methods to bind?
	c.expect_boot = MethodType(expect_boot, c)
	c.expect_busybox = MethodType(expect_busybox, c)
	c.expect_prompt = MethodType(expect_prompt, c)
	c.sysrq = MethodType(sysrq, c)
	c.enter_kdb = MethodType(enter_kdb, c)
	c.expect_kdb = MethodType(expect_kdb, c)
	c.exit_kdb = MethodType(exit_kdb, c)

	if d:
		d.connect_to_target = MethodType(gdb_connect_to_target, d)
		d.expect_prompt = MethodType(gdb_expect_prompt, d)


class ConsoleWrapper(object):
	def __init__(self, console, debug=None):
		bind_methods(console, debug)
		self.console = console
		self.debug = debug
	
	def close(self):
		if self.debug:
			self.debug.close()
		self.console.close()

def qemu(kdb=True, append=None, gdb=False, gfx=False, interactive=False, second_uart=False):
	'''Create a qemu instance and provide pexpect channels to control it'''

	arch = kbuild.get_arch()

	if arch == 'arm' or arch == 'arm64':
		tty = 'ttyAMA'
	else:
		tty = 'ttyS'

	cmdline = ''
	if gfx:
		cmdline += ' console=tty0'
	cmdline += ' console={}0,115200'.format(tty)
	if kdb:
		cmdline += ' kgdboc='
		if gfx:
			cmdline += 'kms,kbd,'
		if not second_uart:
			cmdline += '{}0'.format(tty)
		else:
			cmdline += '{}1'.format(tty)
	if gdb:
		cmdline += ' nokaslr'
	if append:
		cmdline += ' ' + append

	# Heavily broken out so we can easily slot in support for other
	# architectures.
	if arch == 'arm':
		cmd = 'qemu-system-arm'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -M vexpress-a15 -cpu cortex-a15'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel arch/arm/boot/zImage'
		cmd += ' -dtb arch/arm/boot/dts/vexpress-v2p-ca15-tc1.dtb'
	elif arch == 'arm64':
		cmd = 'qemu-system-aarch64'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -M virt,gic_version=3 -cpu cortex-a57'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel arch/arm64/boot/Image'
	elif arch == 'mips':
		cmd = 'qemu-system-mipsel'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -M malta'
		# TODO: Does MIPS have a defconfig that boots SMP qemu systems?
		cmd += ' -m 1G'
		cmd += ' -kernel vmlinux'

	elif arch == 'x86':
		cmd = 'qemu-system-x86_64'
		cmd += ' -enable-kvm'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel arch/x86/boot/bzImage'
	else:
		assert False

	if not gfx:
		cmd += ' -nographic'
	cmd += ' -monitor none'
	cmd += ' -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon'
	if second_uart:
		cmd += ' -chardev socket,id=ttyS1,path=ttyS1.sock,server,nowait'
		cmd += ' -serial chardev:ttyS1'
	cmd += ' -initrd rootfs.cpio.gz'
	cmd += ' -append "{}"'.format(cmdline)

	if gdb:
		gdbcmd = kbuild.get_cross_compile('gdb')
		gdbcmd += ' vmlinux'
		gdbcmd += ' -ex "set pagination 0"'

	if interactive:
		if gdb:
			gdbcmd += ' -ex "target extended-remote |' + \
					'socat - UNIX:ttyS1.sock"'
			print ('\n>>> (cd {}; {})\n'.format(
					kbuild.get_kdir(), gdbcmd))

		print('+| ' + cmd)
		os.system(cmd)
		return None

	print('+| ' + cmd)
	qemu = pexpect.spawn(cmd, encoding='utf-8', logfile=sys.stdout)

	if gdb:
		print('+| ' + gdbcmd)
		gdb = pexpect.spawn(gdbcmd,
				encoding='utf-8', logfile=sys.stdout)
	else:
		gdb = None

	return ConsoleWrapper(qemu, gdb)
