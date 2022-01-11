import kbuild
import os
import pexpect
import random
import string
import sys
import time
import warnings
import pytest
from types import MethodType

# We'd really like to upgrade these to fail words... but we have too many
# of these right now.
WARN_WORDS = [
	'WARNING',
	'BUG',
]

# These are signatures of something very bad happening. If we ever see
# these when we are waiting for a prompt then we need to fail the test
# immediately.
FAIL_WORDS = [
	'Critical breakpoint error',
	'BP remove failed',
	'breakpoint remove failed',
]

def unique_tag(prefix=''):
	"""
	Generate an short string that can be used to synchronize the prompt.

	When we expect a prompt there is a risk we will match a previously issued
	prompt. By forcing a unique(ish) tag to appear in the output we can
	guarantee that we matched the more recently issued prompt.
	"""
	return prefix + ''.join(
		    [random.choice(string.ascii_uppercase) for i in range(8)])

def expect_boot(self, bootloader=(), skip_early=False, skip_late=False):
	for msg in bootloader:
		self.expect(msg)

	if not skip_early:
		self.expect('Linux version.*$')
		self.expect('Calibrating delay loop')

	self.expect('[Uu]npack.*initramfs')
	if not skip_late:
		# Memory is not *always* freed after unpacking the initramfs so
		# we must also look for other common messages that indicate we
		# moved on from unpacking the initramfs.
		self.timeout *= 2
		self.expect(['Freeing initrd memory',
			     'io scheduler.*registered',
			     'Registered I/O driver kgdboc'])
		self.timeout //= 2

		# We need a wildcard here because some newer kernels now say:
		# "Free unused kernel image memory".
		self.expect('Freeing unused kernel.*memory')

def expect_busybox(self):
	self.expect('Starting .*: OK')
	self.expect('Welcome to Buildroot')
	self.expect(['debian-[^ ]* login:', 'buildroot login:'])
	self.sendline('root')

	self.expect_prompt()

	self.sendline('mount -t debugfs none /sys/kernel/debug')
	self.expect_prompt()

def expect_clean_output_until(self, prompt):
	if not isinstance(prompt, list):
		prompt = [ prompt ]

	prompts = prompt + WARN_WORDS + FAIL_WORDS
	silent = False
	choice = self.expect(prompts)
	while choice >= len(prompt):
		msg = f'Observed {prompts[choice]} when waiting for {prompt}'
		if choice >= (len(prompt) + len(WARN_WORDS)):
			pytest.fail(msg)
		else:
			warnings.warn(msg)
		choice = self.expect(prompts)

	return choice

def expect_prompt(self, sync=True):
	if sync:
		self.expect_clean_output_until('# ')

		tag = unique_tag('SYNC_SHELL_')
		# The SYNC_SHELL_ABCD"EFGH" quoting ensures we can only match
		# the output of the echo command (e.g. we never accidentally
		# match a local character echo).
		self.send(f'echo {tag[:-4]}"{tag[-4:]}"\r')
		self.expect_clean_output_until(tag)

	self.expect_clean_output_until('# ')

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
		if 1 == self.expect_clean_output_until(['kdb>', 'more>']):
			self.send('q')
			self.expect_clean_output_until('kdb>')

		tag = unique_tag('SYNC_KDB_')
		self.send(tag + '\r')
		self.expect_clean_output_until('Unknown[^\r\n]*' + tag)

	self.expect_clean_output_until('kdb>')

def sendline_kdb(self, s=''):
	"""
	Works similar to the regular pexpect sendline() but sends
	carriage return rather than os.linesep (usually a line feed).
	"""
	self.send(s)
	self.send('\r')

def inside_kdb(self):
	return self.expect_prompt == self.expect_kdb

def enter_kdb(self, sysrq=True):
	"""
	Trigger the debugger and wait for the kdb prompt.

	Once we see the prompt we update expect_prompt() accordingly.
	"""
	if sysrq:
		self.sysrq('g')
	self.expect('Entering kdb')
	self.expect_kdb()

	self.old_expect_prompt = self.expect_prompt
	self.expect_prompt = self.expect_kdb
	self.old_sendline = self.sendline
	self.sendline = self.sendline_kdb

	# Allow chaining...
	return self

def exit_kdb(self, resume=True, shell=True):
	"""
	Revert to normal running.

	This function is intended to be called from a finally: clause
	meaning the current state of the command interpreter and pager
	is unknown. We do our best to robustly recover in order to
	minimise the risk of cascaded failures.
	"""
	if resume and self.expect_prompt == self.expect_kdb:
		# Make sure we break out of the pager (q is enough to break out
		# but if we're *not* in the pager we need the \r to make the q
		# harmless
		self.send('q\r')
		self.expect('kdb>')

		# Now we have got the prompt back we can exit kdb
		self.send('go\r')
		self.expect_prompt = self.old_expect_prompt
		self.sendline = self.old_sendline
	elif not resume:
		warnings.warn("Cannot exit from kdb (already exited?)")
		# If we're not running in kdb its reasonable to look for a shell prompt

	if shell:
		# The console should be running again but we don't know
		# whether we have a prompt to let's force one and rely
		# on expect_prompt() to resynchronize for us.
		self.sendline('')
		self.expect_prompt()

def gdb_connect_to_target(self):
	self.expect_prompt()
	self.send(f'target extended-remote {self.connection}\r')
	self.expect('Remote debugging using')
	self.expect_prompt()

def gdb_expect_prompt(self):
	self.expect('[(]gdb[)] ')

	tag = unique_tag('SYNC_GDB_')
	# This printf has no newline which means the next gdb prompt will be
	# on the same line as the tag thus we will not match local character
	# echo by mistake.
	self.sendline(f'printf "{tag}"')
	self.expect(f'{tag}[^\r\n]*[(]gdb[)] ')

def bind_methods(c, d):
	# TODO: Can we use introspection to find methods to bind?
	c.expect_boot = MethodType(expect_boot, c)
	c.expect_busybox = MethodType(expect_busybox, c)
	c.expect_clean_output_until = MethodType(expect_clean_output_until, c)
	c.expect_prompt = MethodType(expect_prompt, c)
	c.sysrq = MethodType(sysrq, c)
	c.enter_kdb = MethodType(enter_kdb, c)
	c.expect_kdb = MethodType(expect_kdb, c)
	c.sendline_kdb = MethodType(sendline_kdb, c)
	c.inside_kdb = MethodType(inside_kdb, c)
	c.exit_kdb = MethodType(exit_kdb, c)

	if d:
		d.connect_to_target = MethodType(gdb_connect_to_target, d)
		d.expect_prompt = MethodType(gdb_expect_prompt, d)


class ConsoleWrapper(object):
	def __init__(self, console, debug=None, monitor=None):
		bind_methods(console, debug)
		self.console = console
		self.debug = debug
		self.monitor = monitor

	def close(self):
		if self.monitor:
			self.monitor.close()
		if self.debug:
			self.debug.close()
		self.console.close()

	def enter_gdb(self, sysrq=True):
		(console, gdb) = (self.console, self.debug)

		if sysrq:
			# This should always provoke a gdb prompt to appear
			console.sysrq('g')
		else:
			# gdb should be stopped but we don't know whether we
			# have a prompt so let's force one and rely on
			# expect_prompt() to resynchronize for us)
			gdb.sendline('')
		gdb.expect_prompt()

		return (console, gdb)

	def exit_gdb(self, shell=False):
		(console, gdb) = (self.console, self.debug)

		gdb.sendline('continue')

		if shell:
			# The console should be running again but we don't know
			# whether we have a prompt to let's force one and rely
			# on expect_prompt() to resynchronize for us.
			console.sendline('')
			console.expect_prompt()

def qemu(kdb=True, append=None, gdb=False, gfx=False, interactive=False, second_uart=False):
	'''Create a qemu instance and provide pexpect channels to control it'''

	arch = kbuild.get_arch()
	host_arch = kbuild.get_host_arch()

	if arch == 'arm' or arch == 'arm64':
		tty = 'ttyAMA'
	else:
		tty = 'ttyS'

	if arch == 'arm64' or arch == 'riscv':
		second_uart = False

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
	if arch == 'arm':
		# The versatile boot process no longer contains sneaky
		# ordering tricks to allow the console to come up without an
		# -EPROBE_DEFER. Putting it another way... we'll see timeouts
		# in several tests unless we have an earlycon.
		cmdline += ' earlycon=pl011,0x1c090000'
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
		if host_arch == 'arm64':
			cmd += ' -cpu host -M virt,gic_version=3,accel=kvm'
		else:
			cmd += ' -accel tcg,thread=multi '
			cmd += ' -M virt,gic_version=3 -cpu cortex-a57'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel arch/arm64/boot/Image'
	elif arch == 'mips':
		cmd = 'qemu-system-mips64el'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -cpu I6400 -M malta'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel vmlinux'
	elif arch == 'riscv':
		cmd = 'qemu-system-riscv64'
		cmd += ' -accel tcg,thread=multi'
		cmd += ' -machine virt'
		cmd += '  -m 1G -smp 2'
		cmd += ' -kernel arch/riscv/boot/Image'
	elif arch == 'x86':
		cmd = 'qemu-system-x86_64'
		if host_arch == 'x86':
			cmd += ' -enable-kvm'
		cmd += ' -m 1G -smp 2'
		cmd += ' -kernel arch/x86/boot/bzImage'
	else:
		assert False

	if not gfx:
		cmd += ' -nographic'
	if second_uart:
		cmd += ' -monitor none'
		cmd += ' -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon'
		cmd += ' -chardev socket,id=ttyS1,path=ttyS1.sock,server,nowait'
		cmd += ' -serial chardev:ttyS1'
	elif gdb:
		cmd += ' -S -chardev pty,id=ttyS0 -serial chardev:ttyS0'
	else:
		cmd += ' -monitor none'
		cmd += ' -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon'

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
		time.sleep(5)
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

	if gdb and not second_uart:
		monitor = qemu
		monitor.expect('char device redirected to (/dev/pts/[0-9]*) .label')
		uart_pty = monitor.match.group(1)

		dmx = pexpect.spawn(f'kdmx -p {uart_pty}', encoding='utf-8', logfile=sys.stdout)
		dmx.expect('(/dev/pts/[0-9]*) is slave pty for terminal emulator')
		console_pty = dmx.match.group(1)
		dmx.expect('(/dev/pts/[0-9]*) is slave pty for gdb')
		gdb_pty = dmx.match.group(1)
		print(f'Demuxing from {uart_pty} to {console_pty}^{gdb_pty}')

		console = pexpect.spawn(f'picocom {console_pty}', encoding='utf-8', logfile=sys.stdout)
		gdb.connection = gdb_pty;

		# Attach the kdmx process to the monitor (otherwise it will be
		# closed when the function exits.
		monitor.dmx = dmx

		# Set everything running
		monitor.expect('[(]qemu[)]')
		monitor.sendline('cont')
		monitor.expect('[(]qemu[)]')

		return ConsoleWrapper(console, gdb, monitor)
	else:
		if gdb:
			gdb.connection = '|socat - UNIX:ttyS1.sock'
		return ConsoleWrapper(qemu, gdb)
