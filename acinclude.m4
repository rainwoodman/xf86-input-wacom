dnl Macros for configuring the Linux Wacom package
dnl
AC_DEFUN(AC_WCM_CHECK_ENVIRON,[
dnl Variables for various checks
WCM_ARCH=unknown
WCM_KERNEL=unknown
WCM_ISLINUX=no
WCM_OPTION_MODVER=no
WCM_ENV_KERNEL=no
WCM_KERNEL_WACOM_DEFAULT=no
WCM_ENV_XF86=no
WCM_ENV_XF86V3=no
WCM_LINUX_INPUT=
WCM_PATCH_WACDUMP=
WCM_PATCH_WACOMDRV=
WCM_ENV_GTK=no
WCM_XIDUMP_DEFAULT=no
WCM_ENV_XLIB=no
WCM_XLIBDIR_DEFAULT=/usr/X11R6
XF86SUBDIR=xc/programs/Xserver/include
XF86V3SUBDIR=xc/programs/Xserver/hw/xfree86
dnl Check architecture
AC_MSG_CHECKING(for processor type)
WCM_ARCH=`uname -m`
AC_MSG_RESULT($WCM_ARCH)
dnl
dnl Check kernel type
AC_MSG_CHECKING(for kernel type)
WCM_KERNEL=`uname -s`
AC_MSG_RESULT($WCM_KERNEL)
dnl
dnl Check for linux
AC_MSG_CHECKING(for linux-based kernel)
islinux=`echo $WCM_KERNEL | grep -i linux | wc -l`
if test $islinux != 0; then
	WCM_ISLINUX=yes
fi
AC_MSG_RESULT($WCM_ISLINUX)
if test x$WCM_ISLINUX != xyes; then
	echo "***"
	echo "*** WARNING:"
	echo "*** Linux kernel not detected; linux-specific features will not"
	echo "*** be built including USB support in XFree86 and kernel drivers."
	echo "***"
fi
dnl
dnl Check for linux kernel override
AC_ARG_WITH(linux,
[  --with-linux     Override linux kernel check],
[ WCM_ISLINUX=$withval ])
dnl
dnl Handle linux specific features
if test x$WCM_ISLINUX = xyes; then
	WCM_KERNEL_WACOM_DEFAULT=yes
	WCM_LINUX_INPUT="-DLINUX_INPUT"
	AC_DEFINE(WCM_ENABLE_LINUXINPUT,1,[Enable the Linux Input subsystem])
else
	WCM_PATCH_WACDUMP="(no USB) $WCM_PATCH_WACDUMP"
	WCM_PATCH_WACOMDRV="(no USB) $WCM_PATCH_WACOMDRV"
fi
])
dnl
dnl
dnl
AC_DEFUN(AC_WCM_CHECK_MODVER,[
dnl Guess modversioning
AC_MSG_CHECKING(for kernel module versioning)
kernelrel=`uname -r`
moddir="/lib/modules/$kernelrel/kernel/drivers/usb"

if test -f "$moddir/hid.o.gz"; then
	zcat $moddir/hid.o.gz >config.hid.o
	printk=`nm config.hid.o | grep printk`
	rm config.hid.o
elif test -f "$moddir/hid.o"; then
	printk=`nm $moddir/hid.o | grep printk`
else
	echo "***"; echo "*** WARNING:"
	echo "*** unable to find hid.o or hid.o.gz in kernel module"
	echo "*** directory.  Unable to determine kernel module versioning."
	echo "***"
	printk=""
fi

if test -n "$printk"; then
	printk=`echo "$printk" | grep printk_R`
	if test -n "$printk"; then
		WCM_OPTION_MODVER=yes
		AC_MSG_RESULT(yes)
	else
		AC_MSG_RESULT(no)
	fi
else
	AC_MSG_RESULT([unknown; assuming no])
	WCM_OPTION_MODVER="unknown (assuming no)"
fi
])
AC_DEFUN(AC_WCM_CHECK_KERNELSOURCE,[
dnl Check for kernel build environment
AC_ARG_WITH(kernel,
[  --with-kernel=dir   Specify kernel source directory],
[
	WCM_KERNELDIR="$withval"
	AC_MSG_CHECKING(for valid kernel source tree)
	if test -f "$WCM_KERNELDIR/include/linux/input.h"; then
		AC_MSG_RESULT(ok)
		WCM_ENV_KERNEL=yes
	else
		AC_MSG_RESULT(missing input.h)
		AC_MSG_ERROR("Unable to find $WCM_KERNELDIR/include/linux/input.h")
	fi
],
[
	dnl guess directory
	AC_MSG_CHECKING(for kernel sources)
	WCM_KERNELDIR="/usr/src/linux-2.4"
	if test -f "$WCM_KERNELDIR/include/linux/input.h"; then
		WCM_ENV_KERNEL=yes
		AC_MSG_RESULT($WCM_KERNELDIR)
	else
		WCM_KERNELDIR="/usr/src/linux"
		if test -f "$WCM_KERNELDIR/include/linux/input.h"; then
			WCM_ENV_KERNEL=yes
			AC_MSG_RESULT($WCM_KERNELDIR)
		else
			AC_MSG_RESULT(not found)
			echo "***"
			echo "*** WARNING:"
			echo "*** Unable to guess kernel source directory"
			echo "*** Looked at /usr/src/linux-2.4"
			echo "*** Looked at /usr/src/linux"
			echo "*** Kernel modules will not be built"
			echo "***"
		fi
	fi
])])
AC_DEFUN(AC_WCM_CHECK_XFREE86SOURCE,[
dnl Check for XFree86 build environment
AC_ARG_WITH(xf86,
[  --with-xf86=dir   Specify XF86 build directory],
[
	WCM_XF86DIR="$withval";
	AC_MSG_CHECKING(for valid XFree86 build environment)
	if test -f $WCM_XF86DIR/$XF86SUBDIR/xf86Version.h; then
		WCM_ENV_XF86=yes
		AC_MSG_RESULT(ok)
	else
		AC_MSG_RESULT("xf86Version.h missing")
		AC_MSG_ERROR("Unable to find $WCM_XF86DIR/$XF86SUBDIR/xf86Version.h")
	fi
	WCM_XF86DIR=`(cd $WCM_XF86DIR; pwd)`
])])
AC_DEFUN(AC_WCM_CHECK_XFREE86V3SOURCE,[
dnl Check for XFree86 V3 build environment
AC_ARG_WITH(xf86v3,
[  --with-xf86v3=dir   Specify XF86 V3 build directory],
[
	WCM_XF86V3DIR="$withval";
	AC_MSG_CHECKING(for valid XFree86 V3 build environment)
	if test -f $WCM_XF86V3DIR/$XF86V3SUBDIR/xf86Version.h; then
		WCM_ENV_XF86V3=yes
		AC_MSG_RESULT(ok)
	else
		AC_MSG_RESULT("xf86Version.h missing")
		AC_MSG_ERROR("Unable to find $WCM_XF86V3DIR/$XF86V3SUBDIR/xf86Version.h")
	fi
	WCM_XF86V3DIR=`(cd $WCM_XF86V3DIR; pwd)`
])])
AC_DEFUN(AC_WCM_CHECK_GTK,[
dnl Check for GTK development environment
AC_ARG_WITH(gtk,
[  --with-gtk={1.2|2.0|yes|no}   Uses GTK 1.2 or 2.0 API],
[WCM_USE_GTK=$withval],[WCM_USE_GTK=yes])

if test "$WCM_USE_GTK" == "yes" || test "$WCM_USE_GTK" == "1.2"; then
	AC_CHECK_PROG(gtk12config,gtk-config,yes,no)
fi
if test "$WCM_USE_GTK" == "yes" || test "$WCM_USE_GTK" == "2.0"; then
	AC_CHECK_PROG(pkgconfig,pkg-config,yes,no)
	if test x$pkgconfig == xyes; then
		AC_MSG_CHECKING(pkg-config for gtk+-2.0)
		gtk20config=`pkg-config --exists gtk+-2.0 && echo yes`
		if test "$gtk20config" == "yes"; then
			AC_MSG_RESULT(yes)
		else
			AC_MSG_RESULT(no)
		fi
	fi
fi

dnl Default to best GTK available
if test "$WCM_USE_GTK" == "yes"; then
	if test "$gtk20config" == "yes"; then
		WCM_USE_GTK=2.0
	elif test "$gtk12config" == "yes"; then
		WCM_USE_GTK=1.2
	else
		echo "***"; echo "*** WARNING:"
		echo "*** unable to find any gtk development environment; are the "
		echo "*** development packages installed?  gtk will not be used."
		echo "***"
		WCM_USE_GTK=no
	fi
fi

dnl Handle GTK 1.2
if test "$WCM_USE_GTK" == "1.2"; then
	if test "$gtk12config" != "yes"; then
		echo "***"; echo "*** WARNING:"
		echo "*** unable to find gtk-config in path; are the development"
		echo "*** packages installed?  gtk will not be used."
		echo "***"
	else
		AC_MSG_CHECKING(for GTK version)
		gtk12ver=`gtk-config --version`
		if test $? != 0; then
			AC_MSG_RESULT(unknown)
			AC_MSG_ERROR(gtk-config failed)
		fi
		AC_MSG_RESULT($gtk12ver)
		WCM_ENV_GTK=$gtk12ver
		AC_DEFINE(WCM_ENABLE_GTK12,1,Use GTK 1.2 API)
		CFLAGS="$CFLAGS `gtk-config --cflags`"
		LIBS="$LIBS `gtk-config --libs`"
	fi
fi

dnl Handle GTK 2.0
if test "$WCM_USE_GTK" == "2.0"; then
	if test "$pkgconfig" != "yes"; then
		echo "***"; echo "*** WARNING:"
		echo "*** unable to find pkg-config in path; gtk 2.0 requires"
		echo "*** pkg-config to locate the proper development environment."
		echo "*** gtk will not be used."
		echo "***"
	elif test "$gtk20config" != "yes"; then
		echo "***"; echo "*** WARNING:"
		echo "*** unable to find gtk 2.0 registered with pkg-config;"
		echo "*** are the development packages installed?"
		echo "*** pkg-config is not very smart; if gtk has dependencies"
		echo "*** that are not installed, you might still get this error."
		echo "*** Try using pkg-config --debug gtk+-2.0  to see what it is"
		echo "*** complaining about.  Misconfigured systems may choke"
		echo "*** looking for gnome-config; if this is the case, you will"
		echo "*** need to install the Gnome development libraries even"
		echo "*** though we will not use them."
		echo "***"
	else
		AC_MSG_CHECKING(for GTK version)
		gtk20ver=`pkg-config --modversion gtk+-2.0`
		if test $? != 0; then
			AC_MSG_RESULT(unknown)
			AC_MSG_ERROR(pkg-config failed)
		fi
		AC_MSG_RESULT($gtk20ver)
		WCM_ENV_GTK=$gtk20ver
		AC_DEFINE(WCM_ENABLE_GTK20,1,Use GTK 2.0 API)
		CFLAGS="$CFLAGS `pkg-config --cflags gtk+-2.0`"
		LIBS="$LIBS `pkg-config --libs gtk+-2.0`"
	fi
fi
])
AC_DEFUN(AC_WCM_CHECK_XLIB,[
dnl Check for XLib development environment
WCM_XLIBDIR=
AC_ARG_WITH(xlib,
[  --with-xlib=dir   uses a specified X11R6 directory],
[WCM_XLIBDIR=$withval])

dnl handle default case
if test "$WCM_XLIBDIR" == "" || test "$WCM_XLIBDIR" == "yes"; then
	AC_MSG_CHECKING(for XLib include directory)
	if test -d $WCM_XLIBDIR_DEFAULT/include; then
		WCM_XLIBDIR=$WCM_XLIBDIR_DEFAULT
		AC_MSG_RESULT(found)
	else
		AC_MSG_RESULT(not found, tried $WCM_XLIBDIR_DEFAULT/include)
		WCM_XLIBDIR=no
	fi
fi

dnl check for header files
if test "$WCM_XLIBDIR" != "no"; then
	AC_MSG_CHECKING(for XLib header files)
	if test -f "$WCM_XLIBDIR/include/X11/Xlib.h"; then
		AC_MSG_RESULT(found)
		WCM_ENV_XLIB=yes
	else
		AC_MSG_RESULT(not found; tried $WCM_XLIBDIR/include/X11/Xlib.h)
		echo "***"; echo "*** WARNING:"
		echo "*** unable to find X11/Xlib.h; are the X11 development"
		echo "*** packages installed?  XLib dependencies will not be built."
		echo "***"
	fi
fi
])