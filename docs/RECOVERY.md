# Emergency recovery

1. **HalOS won't boot, Windows is fine:** in the firmware boot menu (often F12/F11/Esc) choose *Windows Boot Manager*. HalOS never deletes the Windows boot entry.
2. **Boot the recovery entry:** the GRUB menu has *HalOS (recovery)*; it boots offline to a shell with `/` mounted. Roll back a bad update with Btrfs snapshots: `snapper list`, then `snapper rollback <n>` and reboot.
3. **From the USB stick:** boot the live image, open a terminal, `sudo mount -o subvol=@home /dev/<halos-partition> /mnt` and copy your files to an external drive.
4. **Remove HalOS entirely (keep Windows):** in Windows, Disk Management → delete the HalOS partitions; then `bcdedit /enum firmware` and `bcdedit /delete {id}` for the HalOS entry, or remove `EFI\HalOS` from the EFI partition with `mountvol S: /S`.
5. **Reinstall without losing files:** run HalOS-Setup.exe → **Update**; `/home` is kept.

Your data in `/home` lives on its own Btrfs subvolume and is not touched by updates.
