# playgta5 Source Code
This code is grabbed from playgta5.com before it got took down. You can run this locally or make it public hehe.
This github page serves as archival for the original V1 port of the game,

# V2 of Grand-V is releasing on a new github page,

https://github.com/SebasKitten/Grand-V

# Credits
Shoutout to Sebas Furbastian on Telegram for scrapping this code. Idk what is his GitHub but here's the Telegram and X.

Telegram: @SebasKitten

X: @Sebas_Kitten

# Link
Telegram: https://t.me/reGRANDTA

Discord: https://discord.gg/hrbcPjjZfj


# Disclaimer
I don't host the `.\mirror` folder since it has copyrighted content from Rockstar Games. Please find the files by yourself.

No copyrighted file is included in this repo. If Rockstar Games or any affiliated group think this repo has copyright infringement things, email me at shadany7824@gmail.com for me to took it down.

And don't email me for asking the mirror folder. I will not reply to the email.

# How to use
1. Download the ZIP or just `git clone` it. It should have all this file and folders.
<p align="center">
  <img src="media/Screenshot 2026-10-07 172103.png" alt="playgta5 SC">
</p>

2. Paste your `.mirror` folder at your desired path. (It should have 19.7 GB of file size. Check the pic below.)
<p align="center">
  <img src="media/Screenshot 2026-10-07 172216.png" alt="Folder Properties">
</p>
<p align="center">
  <img src="media/Screenshot 2026-10-07 172718.png" alt="Folder Properties">
</p>
<p align="center">
  <img src="media/Screenshot 2026-10-07 172758.png" alt="Folder Properties">
</p>

3. Run the `Launch-Local.cmd` and it will automatically open the URL at `http://localhost:8000/`.

4. Voila!

## macOS launchers and controller support (mirror-overlay)
`mirror-overlay/` holds updated files for the portable `mirror` folder (no game assets):
macOS launchers (`Launch-Local.command`, `Launch-LAN.command`), the server with macOS
fixes (`serve_local.py`), its `README.md`, and the game page with Xbox/PlayStation
controller support (`index.html`). After you've added your `mirror` folder, copy them in:

```
cp mirror-overlay/Launch-*.command mirror-overlay/serve_local.py mirror-overlay/README.md mirror/
cp mirror-overlay/index.html mirror/mirror/playgta5.com/index.html
```

The controller layout is in `mirror-overlay/README.md`.

## macOS
1. Install Python 3.9+ if you don't have it: `xcode-select --install` (or `brew install python`).
2. Double-click `Launch-Local.command` (or run `./Launch-Local.command` in Terminal). It opens `http://localhost:8000/`.
3. If macOS says the file can't be opened because it's from an unidentified developer, right-click it and choose **Open**, or run:
   `xattr -d com.apple.quarantine Launch-Local.command && chmod +x Launch-Local.command`
4. The launcher opens Google Chrome when it's installed, otherwise your default browser. Use Chrome: Safari stalls at 6% on the loading screen. The bundled `runtime/` folder is Windows-only and is ignored on macOS.

# Requirement
Scripts require standard-library Python 3.11 or newer. The bundled Python path
in the commands above is specific to the original PC; the portable ZIP instead
provides `runtime\python.exe` and the double-click launcher. On macOS the `.command`
launchers use the system `python3` (3.9 or newer).
Completed files and `.part` transfers are retained for resumption. Final checks
cover inventory sizes, runtime hash samples, WASM signature, HTTP isolation,
range reads and both batch formats. Actual gameplay requires separate browser
validation. A public client snapshot is not the site's original development repository.

To resume with the current uncapped settings, append `--workers 32 --rate-mib 0`
to the downloader command. Content lengths from HTTP take precedence over the
source manifest when it is stale; mismatches are recorded explicitly.
