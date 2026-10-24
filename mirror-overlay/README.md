# PlayGTA5 offline

Complete archived website with both map options and a bundled Windows x64 Python runtime.
Extract the entire ZIP before running. No Python installation is required.

## Launch on this PC

Double-click `Launch-Local.cmd`. It opens http://localhost:8000/ in your default
browser and accepts connections only from this PC. Keep the server window open.

## Serve other PCs on your network

1. On the server PC, right-click `Setup-LAN-Firewall.cmd` and select **Run as administrator** once.
2. Double-click `Launch-LAN.cmd`. It accepts connections on port 8080 without opening a browser.
3. On the other PC, open the network URL printed in the server window, e.g. http://192.168.1.100:8080/.

Use the server's Ethernet/Wi-Fi IPv4 address from `ipconfig`, rather than a VPN
address. The firewall rule allows bundled Python on TCP 8080 from the local
subnet, including when Ethernet is marked Public. Run firewall setup again if
you move the extracted folder. Ctrl+C stops either server.

### Client browser setting for LAN HTTP

WebGPU and shared-memory WebAssembly require a secure browser context.
On each client PC, open:

- Chrome: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
- Edge: `edge://flags/#unsafely-treat-insecure-origin-as-secure`

Add the exact server origin, e.g. `http://192.168.1.100:8080`, enable the setting,
and restart the browser. A trusted HTTPS setup is the alternative. This setting
is unnecessary for localhost. The server supplies the required COOP/COEP headers.

## macOS

The bundled `runtime/` is Windows-only; on macOS the launchers use the system `python3`
(3.9+; install with `xcode-select --install` or `brew install python`).

- This Mac only: double-click `Launch-Local.command`. It opens http://localhost:8000/.
- Other computers on your network: double-click `Launch-LAN.command` (port 8080). If the
  macOS firewall is on, click **Allow** when asked whether Python may accept incoming
  connections. No setup script is needed. Find this Mac's address with `ipconfig getifaddr en0`.
- If Finder refuses to open a `.command` file, right-click it and choose **Open**, or run
  `xattr -d com.apple.quarantine *.command && chmod +x *.command` in this folder.
- Use Google Chrome. `Launch-Local.command` opens it when it's installed, otherwise your default
  browser. Safari stalls at 6% on the loading screen. LAN clients also need Chrome for the secure-origin flag below.

## Controls and requirements

Use a browser and GPU supporting WebGPU and the site's WebAssembly features.
At the title screen: Space opens map selection, 5 selects GTA V Map, and 6
selects the site's GTA VI Map (`env_test`). Enter selects Story Mode.

### Controller

Xbox, PlayStation and other standard controllers work in Chrome (USB or Bluetooth). Press any
button once after the page opens so the browser detects it. The game only understands keyboard
and mouse, so the page translates the controller into PC keys: movement is on/off rather than
gradual, and on-screen hints still show keyboard keys.

| Controller | Start menu | On foot (PC key) | Driving (PC key) |
|---|---|---|---|
| Left stick | | Move (W A S D) | Steer (A D) |
| Right stick | | Camera and aim, wheel selection (mouse) | Camera and aim (mouse) |
| RT / R2 | | Shoot (left mouse) | Accelerate (W) |
| LT / L2 | | Aim (right mouse) | Brake, reverse (S) |
| RB / R1 | | Cover (Q) | Shoot (left mouse) |
| LB / L1 | | Weapon wheel (Tab) | Aim (right mouse) |
| LB + RB | | Special ability (Caps Lock) | Pressed together: special ability; one after the other: aim and shoot |
| L3 + R3 | | Special ability (Caps Lock) | Special ability (Caps Lock) |
| A / Cross | Story Mode | Sprint (Shift); select in menus (Enter) | Held: switches to on foot |
| B / Circle | Back | Reload, melee (R); back in menus (Backspace) | |
| X / Square | Sandbox Mode | Jump (Space) | Handbrake (Space) |
| Y / Triangle | | Enter vehicle (F); switches to driving | Exit vehicle (F); switches to on foot |
| L3 | | Stealth (Ctrl) | |
| R3 | | Interact (E) | Horn (E) |
| D-pad up | | Phone (Up) | Phone (Up) |
| D-pad down | | Switch character (Alt; pick with the right stick) | Switch character |
| D-pad left / right | GTA V Map / GTA VI Map | Menus, phone (Left / Right) | Left: radio wheel (Q); right: Right |
| Back / Share | | Tap: change camera (V); hold: switch on foot / driving | same |
| Start / Options, Home / PS | | Pause menu (Esc) | Pause menu (Esc) |

The page can't see whether you're in a vehicle, so it tracks it itself: Y flips between on foot
and driving, holding A (sprint) switches to on foot (a tap, as in menus, doesn't), and the current mode is shown bottom right
(and briefly in the middle of the screen when it changes). If it's wrong (for example Y pressed
with no car nearby, or thrown from a bike), hold A to sprint or hold Back for half a second to switch.
While driving, a bumper aims or shoots about 0.15 s after it's pressed, so the page can tell
a single bumper from LB + RB together. Franklin's special ability only works while driving.

The mapping lives in `mirror/playgta5.com/index.html` (search for `PAD_KEYS`); the unmodified page
is saved next to it as `index.html.orig`.

Direct map URLs: `/?mode=sandbox` and `/?mode=sandbox&map=env_test`.
The client PC runs the game with its own CPU/GPU; the server supplies the files.
Do not open index.html with file://. No CDN is required for archived game assets.

If port 8000 or 8080 is occupied, stop the other server. Custom LAN port example:
`runtime\python.exe serve_local.py --host 0.0.0.0 --port 8081`.
For a custom port, also update the firewall rule and browser origin.

To remove the firewall rule, run in administrator PowerShell:
`Remove-NetFirewallRule -Name PlayGTA5-Offline-LAN-8080`.

Source: https://playgta5.com/ — archived 2026-10-06, build 8b0b5899ed.
The map names follow the site's labels; `env_test` provenance is unverified.
Server startup, headers and range/batch I/O were checked; gameplay is untested.
Python's license is included in runtime/LICENSE.txt.
