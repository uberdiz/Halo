# Emergency recovery

1. **HalOS won't boot, Windows is fine:** in the firmware boot menu (often F12/F11/Esc) choose *Windows Boot Manager*. HalOS never deletes the Windows boot entry.
2. **Roll back a bad update:** in HalOS, Settings → Recovery restarts once into the offline recovery mode. Or use the Btrfs snapshots: `sudo snapper list`, then `sudo snapper rollback <n>` and reboot.
3. **From the USB stick:** boot the live image, open a terminal, `sudo mount -o subvol=@home /dev/<halos-partition> /mnt` and copy your files to an external drive.
4. **Remove HalOS entirely (keep Windows):** in Windows, Disk Management → delete the HalOS partitions; then `bcdedit /enum firmware` and `bcdedit /delete {id}` for the HalOS entry, or remove `EFI\Halo` from the EFI partition with `mountvol S: /S`.
5. **Reinstall without losing files:** run HalOS-Setup.exe → **Update**; `/home` is kept.

Your data in `/home` lives on its own Btrfs subvolume and is not touched by updates.
