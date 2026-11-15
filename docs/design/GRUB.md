# Aurora boot menu (engineering)

Original dark violet background, restrained orange selection and the
canonical Localzet logo, with the existing Russian/English/recovery boot
entries. The build renders PNGs from original SVGs and creates PFF2 fonts
from Ubuntu's DejaVu Sans. No downloaded themes or proprietary fonts.

The Live config attempts the native GRUB gfxmenu path only if font, graphics
and module initialization succeed. Native text menu remains the fallback.
The five-second timeout, default normal entry and diagnostic kernel args
are unchanged. Both Live and installed GRUB configs are syntax checked.

The installed theme lives on the newly created target's own /boot; only the
existing blank-SSD install path is supported. No modification of another
disk, its EFI loader or firmware boot entries. No additional authorization
to partition a disk. Verify graphical rendering, keyboard selection and
text fallback on real firmware as well as actual QEMU boot; syntax and
boot success alone are not visual acceptance.

Reference: https://www.gnu.org/software/grub/manual/grub/html_node/Theme-file-format.html
