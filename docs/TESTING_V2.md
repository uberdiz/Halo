# Testing HalOS v2 on a real PC

Work through this on the laptop after installing. Mark each item `[Y]`, or `[N — what happened]`.

## 1. Install without a USB, replacing the old HalOS / SAINT OS (Windows stays)

**Before you start (school laptop):**
- If the laptop is managed by the school, check first. Signs of this:
  - "Some settings are managed by your organization"
  - BitLocker that you can't pause
  - no administrator rights
- Setup needs administrator rights.
- If BitLocker is on, have the recovery key ready (aka.ms/myrecoverykey).

**Install steps:**
1. [ ] Download **HalOS-Setup.exe** from the newest release: https://github.com/uberdiz/Halo/releases
   (pre-releases are listed too).
2. [ ] Run it. The checks page shows only ✓ or ! items.
3. [ ] Choose a mode on the choice page.
   - If Setup ran on this laptop before, the first option is **Update HalOS: replace the older HalOS or SAINT
     OS, keep Windows**. Pick it.
   - If that option isn't there (the old HALOLIVE partition was removed), pick **Just try it**. It makes a new
     6 GB HALOLIVE partition.
4. [ ] Download.
   - Setup finds the newest release on its own.
   - It downloads the 3 parts ("Part 1 of 3…"), joins them, and checks the ISO.
   - If you stop it partway, Retry carries on from where it was.
5. [ ] Type **UPDATE** (or **INSTALL**), then wait. The PC restarts into HalOS live.
6. [ ] Secure Boot only: a blue MOK screen appears.
   - Choose Enroll MOK, then Continue, then Yes.
   - Type the password **halo**.
   - Choose Reboot.
7. [ ] In the live session, open the installer.
   - The first choice is **replace the HalOS (or SAINT OS) already installed**.
   - It names the two old HalOS partitions.
   - It says that Windows isn't touched.
8. [ ] Continue. A warning says the old HalOS Home files are erased. Answer Yes.
   - The installer has 3 pages.
   - Then restart.
9. [ ] The PC still starts Windows by default. Windows and your files are fine.
10. [ ] Press F12 at startup and pick HalOS. It boots to the desktop.
    - From Windows, an admin PowerShell can also run `restart_into_halos.ps1`, which starts HalOS once.
11. [ ] If the old HalOS was installed by the standard installer pages, the first choice in step 7 isn't shown.
    In that case:
    - Use **Other options…** and then "Replace a partition".
    - Pick the old Linux partition. **Never** pick a Windows partition, HALOLIVE, or Windows' EFI partition.

## 2. Claude Code with your Claude sign-in, no API key (no credits used)

SAINT and AIDE remove `ANTHROPIC_API_KEY` and the other API-billing settings before they start Claude Code. This
means Claude Code can only use your Claude Pro/Max sign-in.

1. [ ] Open a terminal (Konsole) and run `claude`.
   - When it asks how to sign in, choose **Claude account with subscription** (Pro or Max).
   - Do **not** choose "Anthropic Console / API key".
   - The browser opens. Sign in, then come back.
2. [ ] Run `claude auth status`. It shows your Claude account, not an API key.
3. [ ] Run `echo $ANTHROPIC_API_KEY`. It prints nothing.
   - Even if it printed a key, SAINT would still drop it. Test that too:
   - Run `ANTHROPIC_API_KEY=sk-test saint`.
   - The agent still works on the subscription.
4. [ ] In SAINT, say or type **"ask claude to make a folder called Test on the desktop and put a note in it"**.
   - SAINT says "On it…".
   - The steps show at the top right and on the **Agent** page.
5. [ ] On the Agent page, follow up on the same run: **"now rename it to Test2"**.
   - It continues the same session.
6. [ ] Sign out (`claude auth logout`) and repeat step 4.
   - SAINT says how to sign in ("run `claude` and choose your Claude account…").
   - It does not use a key.
7. [ ] In AIDE (the code editor), open a folder and ask the AI panel: "explain this project".
   - The provider is **Claude Code**.
   - The reply shows "▸ Read …" steps.
8. [ ] Check where the usage went:
   - It shows under your plan's usage at https://claude.ai/settings/usage.
   - Your Anthropic Console has no new API charges at https://console.anthropic.com.

## 3. SAINT controls the OS (trust levels)

1. [ ] Settings › What SAINT may do: each category shows **Ask / Ask if risky / Trusted**.
2. [ ] "turn on dark mode", "set the volume to 30", "open my Downloads folder".
   - Each one happens.
   - A ✓ step card appears.
3. [ ] "delete the Test2 folder". It **always** asks, even when Files is set to Trusted.
4. [ ] "undo that". The folder comes back from the trash.
5. [ ] "tile my windows" with 3 or more windows open. They split the screen.
6. [ ] "run `ls ~` in the terminal". It asks first, unless Shell is Trusted.
7. [ ] Background mode: "in the background, open Firefox and take a screenshot".
   - Your mouse and keyboard aren't taken over.
   - The screenshot appears.

## 4. Desktop and HalOS apps

1. [ ] **Boot time:** run `systemd-analyze` and write down the total. Target: under 15 s to the desktop on an SSD.
2. [ ] **Wallpaper:** the living wallpaper moves while SAINT speaks or music plays, and stays still otherwise.
3. [ ] **Window animations:** opening and closing a window shows the halo.
4. [ ] **Icons:** the panel and Files use the HalOS icons, in both dark and light theme.
5. [ ] **HalOS Settings:** search for "bluetooth". Only Bluetooth comes up, not Night Light.
6. [ ] **HalOS Files:**
   - Search a filename.
   - Search a word inside a document.
   - Preview a file.
7. [ ] **Camera presence** (Settings › Camera, off by default). Turn it on, then:
   - Walk away: the screen locks.
   - Come back: the screen wakes to the lock screen. It does **not** unlock.
   - Look away from a video: it pauses.

## 5. Bring everything (migration)

1. [ ] In HalOS, open **Bring everything**. It reads the Windows disk directly.
   - If C: is BitLocker-locked, first run `packaging\windows-host\export_for_halos.ps1 -Destination E:\` in
     Windows (it only reads), then point the wizard at that drive.
2. [ ] Check that these came across:
   - files
   - browser bookmarks and passwords (Firefox/Chromium)
   - wallpaper
   - SAINT memory and history
   - Claude Code settings
3. [ ] **Agents** page:
   - It detects this laptop's CPU, RAM and GPU.
   - It suggests models that fit.
   - Install one, and it answers.

## 6. If something goes wrong

- On the installer's failure screen, use **Copy log** and paste the log into a GitHub issue.
- In HalOS, run `saintos-diagnose`. It writes a report you can attach.
- If HalOS doesn't start: Windows is unchanged.
  - Use F12, then HALOLIVE, to get back to the live system.
  - Or remove HalOS's partitions in Disk Management.
