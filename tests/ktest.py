import kbuild
import pexpect
import sys
import time
from types import MethodType

def expect_boot(self, bootloader=()):
	for msg in bootloader:
		self.expect(msg)
	self.expect('Linux version.*$')
	self.expect('Calibrating delay loop')
	self.expect('NET: Registered protocol family 2')
	self.expect('io scheduler [^ ]* registered .default.')
	self.expect('Freeing unused kernel memory')

def expect_busybox(self):
	self.expect('Starting logging')
	self.expect('OK')
	self.expect('Welcome to Buildroot')
	self.expect(['debian-[^ ]* login:', 'buildroot login:'])
	self.send('root\r')

	self.expect_prompt()

def expect_prompt(self):
	self.expect('# ')

def gdb_connect_to_target(self):
	self.expect_prompt()
	self.send('target extended-remote | socat - UNIX:ttyS1.sock\r')
	self.expect('Remote debugging using')
	self.expect_prompt()

def gdb_expect_prompt(self):
	self.expect('[(]gdb[)] ')

def sysrq(self, ch):
	self.send('echo {} > /proc/sysrq-trigger\r'.format(ch))

def bind_methods(c, d):
	# TODO: Can we use introspection to find methods to bind?
	c.expect_boot = MethodType(expect_boot, c)
	c.expect_busybox = MethodType(expect_busybox, c)
	c.expect_prompt = MethodType(expect_prompt, c)
	c.sysrq = MethodType(sysrq, c)

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

def qemu(second_uart=False, gdb=False, append=None):
	'''Create a qemu instance and provide pexpect channels to control it'''

	cmdline = ''
	cmdline += ' console=ttyS0,115200'
	if not second_uart:
		cmdline += ' kgdboc=ttyS0'
	else:
		cmdline += ' kgdboc=ttyS1'
	if gdb:
		cmdline += ' nokaslr'
	if append:
		cmdline += ' ' + append

	# Heavily broken out so we can easily slot in support for other
	# architectures.
	cmd = 'qemu-system-x86_64'
	#cmd = 'QEMU_AUDIO_DRV=none ' + cmd
	cmd += ' -enable-kvm'
	cmd += ' -m 1G'
	cmd += ' -smp 2'
	cmd += ' -nographic -monitor none'
	cmd += ' -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon'
	if second_uart:
		cmd += ' -chardev socket,id=ttyS1,path=ttyS1.sock,server,nowait'
		cmd += ' -serial chardev:ttyS1'
	cmd += ' -kernel arch/x86/boot/bzImage'
	cmd += ' -initrd rootfs.cpio.gz'
	cmd += ' -append "{}"'.format(cmdline)
	print('+| ' + cmd)
	qemu = pexpect.spawn(cmd, encoding='utf-8', logfile=sys.stdout)

	if gdb:
		gdbcmd = 'gdb vmlinux'
		gdbcmd += ' -ex "set pagination 0"'
		print('+| ' + gdbcmd)
		gdb = pexpect.spawn(gdbcmd,
				encoding='utf-8', logfile=sys.stdout)
	else:
		gdb = None

	return ConsoleWrapper(qemu, gdb)
