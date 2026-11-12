# Troubleshooting

| Problem | Try |
|---|---|
| Installer error | It shows **Retry** and **Copy log**. Paste the log into a [bug report](https://github.com/uberdiz/Halo/issues/new?template=bug_report.yml). |
| "Not enough space" | HalOS needs 30 GB of unallocated or shrinkable space. Free space in Windows Disk Management, then retry. |
| Black screen after boot (NVIDIA) | At GRUB press `e`, add `nomodeset` to the `linux` line, boot, then report your GPU model. Pre-Turing NVIDIA GPUs use the open `nouveau` driver. |
| "Verification failed" / Secure Boot violation | Enrol the MOK (blue screen at first boot, password `halos`) or turn Secure Boot off in firmware. |
| Windows missing from boot menu | Boot HalOS, run `sudo grub-mkconfig -o /boot/grub/grub.cfg` (os-prober is enabled). Or pick Windows Boot Manager in the firmware boot menu. |
| SAINT doesn't answer | `systemctl --user status saint`; restart with `systemctl --user restart saint`. Logs: `journalctl --user -u saint`. |
| Local model is slow | Ask SAINT "is Ollama using my GPU?". If it says CPU, check `nvidia-smi` and that the model fits in VRAM. |
| No sound / mic | Settings → Sound; `wpctl status` lists devices. |

Still stuck? Open an issue with the output of `saint --selftest` if available, and `journalctl -b -p err`.
