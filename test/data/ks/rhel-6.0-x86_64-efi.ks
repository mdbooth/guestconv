install
text
cdrom

lang en_GB.UTF-8
keyboard uk
timezone --utc Europe/London

rootpw password
authconfig --enableshadow --passalgo=sha512

bootloader --location=partition --driveorder=vda --append="console=tty0 console=ttyS0,115200 crashkernel=auto rd_NO_PLYMOUTH"

selinux --enforcing
network --bootproto dhcp

poweroff

clearpart --all --initlabel
autopart

%packages
@core
%end
