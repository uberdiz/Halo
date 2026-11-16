# Troubleshooting

| Problem | Try |
|---|---|
| Installer error | It shows **Retry** and **Copy log**. Paste the log into a [bug report](https://github.com/uberdiz/Halo/issues/new?template=bug_report.yml). |
| "Not enough space" | HalOS needs 30 GB of unallocated or shrinkable space. Free space in Windows Disk Management, then retry. |
| Black screen after boot (NVIDIA) | At GRUB press `e`, add `nomodeset` to the `linux` line, boot, then report your GPU model. Pre-Turing NVIDIA GPUs use the open `nouveau` driver. |
| "Verification failed" / Secure Boot violation | Enrol the MOK (blue screen at first boot, password `halo`) or turn Secure Boot off in firmware. |
| Blue "Perform MOK management" screen after an update | An update tried to install a new kernel, and this PC's key has to be approved first. Enroll MOK → Continue → Yes → type `halo` (nothing shows while you type) → Enter → Reboot. Then run the update again. |
| GRUB: "bad shim signature" / "you need to load the kernel first" | Older installs: an update left an unsigned kernel in /boot. Start HALOLIVE (F12), open Konsole, run the three commands under *Repair an unsigned kernel* below. |
| Windows missing from boot menu | Boot HalOS, run `sudo grub-mkconfig -o /boot/grub/grub.cfg` (os-prober is enabled). Or pick Windows Boot Manager in the firmware boot menu. |
| SAINT doesn't answer | `systemctl --user status saint`; restart with `systemctl --user restart saint`. Logs: `journalctl --user -u saint`. |
| Local model is slow | Ask SAINT "is Ollama using my GPU?". If it says CPU, check `nvidia-smi` and that the model fits in VRAM. |
| No sound / mic | Settings → Sound; `wpctl status` lists devices. |

### Repair an unsigned kernel (from HALOLIVE)

```bash
D=$(lsblk -rno PATH,FSTYPE | awk '$2=="btrfs"{print $1; exit}'); sudo mount -o subvol=@ "$D" /mnt
curl -fsSLo /tmp/kh https://raw.githubusercontent.com/uberdiz/Halo/main/packaging/arch/pkgbuilds/halo-calamares-config/halo-kernel-hook
sudo bash /tmp/kh /mnt /run/archiso/bootmnt/halo/boot/x86_64/vmlinuz-linux
```

If the last command prints a `mokutil` line, run it too (password `halo`), restart and enroll the key on the blue screen. Otherwise just restart.

Still stuck? Open an issue with the output of `saint --selftest` if available, and `journalctl -b -p err`.
