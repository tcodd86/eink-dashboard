# E-ink Dashboard

Shows the current time (updated every minute), current weather, a 7-day
forecast, today's Catholic Mass readings, and a Latin word of the day on a
Waveshare 2.7" e-Paper HAT connected to a Raspberry Pi 3. Navigation is via
the HAT's 4 physical buttons; the app starts automatically on boot via
systemd.

## Hardware

- Raspberry Pi 3 (any variant)
- Waveshare 2.7" e-Paper HAT (264x176, B/W), plugged directly onto the Pi's
  40-pin GPIO header -- no wiring needed.

## Prerequisites

- **Raspberry Pi OS Bookworm, 64-bit.** This matters for two reasons:
  - `catholic-mass-readings` requires Python 3.10+ (Bookworm ships 3.11;
    older Raspberry Pi OS releases ship older Python and won't work).
  - One of its dependencies (`curl_cffi`) ships prebuilt wheels for 64-bit
    ARM but may not for 32-bit, which would otherwise require a from-source
    compile with extra system packages.
- Internet access (for weather + Mass readings; the app degrades gracefully
  without it, see Limitations below, but won't have fresh data).

## Button mapping

The Waveshare user manual and spec sheet for this panel only document its
8-pin SPI interface -- neither mentions the 4 physical buttons on the HAT.
The GPIO pin numbers in `config.py` (`BUTTON_PINS`) were confirmed with
`button_test.py` on real hardware (button1/top = GPIO19, ... button4/bottom
= GPIO5 -- the reverse of the third-party writeup they were originally
sourced from). If buttons ever seem mismatched on your unit, re-run
`button_test.py` (see Setup below) and update `config.py`.

Button behavior is context-dependent:

| Button | Home screen | Forecast screen | Mass Readings menu | Latin Word screen | A reading screen |
|---|---|---|---|---|---|
| 1 (top) | Open 7-Day Forecast | Back to Home | Back to Home | Back to Home | Back to Home |
| 2 | Open Mass Readings menu | unused | Open First Reading | unused | Scroll up one page |
| 3 | Open Latin Word of the Day | unused | Open Responsorial Psalm | unused | Scroll down one page |
| 4 | unused | unused | Open Gospel | unused | Jump to next reading (First -> Psalm -> Gospel -> ...) |

On Sundays/solemnities, the Mass has an extra "Second Reading" beyond the
usual 3. Since there's no 5th button for it, it's appended onto the "First
Reading" screen below the First Reading, separated by a divider -- scroll
down to reach it.

The right-hand sidebar always shows an icon per button reflecting its
current function (blank where a button is unused), so you don't need to
memorize this table.

The Latin word of the day comes from Transparent Language's free RSS feed
(`feeds.feedblitz.com/latin-word-of-the-day`) -- an unofficial third-party
source, same caveat as the Mass readings scrape below: the app caches the
last successfully fetched word and keeps showing it if a day's fetch fails,
rather than showing nothing.

Any screen other than Home automatically returns to Home after 5 minutes
without a button press (`config.IDLE_TIMEOUT_SECONDS`).

## Setup

```bash
git clone https://github.com/tcodd86/eink-dashboard.git
cd eink-dashboard
./setup.sh
```

`setup.sh` installs system packages, enables SPI (reboots if it had to
change that), and creates a `.venv` with all Python dependencies. After it
finishes (and after any required reboot):

```bash
cp config_local.py.example config_local.py
```

Edit `config_local.py` and fill in your location's latitude/longitude (see
Configuration below). This file is gitignored -- it's kept out of version
control since it reveals your approximate location.

```bash
./.venv/bin/python3 button_test.py
```

Press each physical button top to bottom and confirm the GPIO numbers
printed match `BUTTON_PINS` in `config.py` (`button1`..`button4`, top to
bottom). Edit `config.py` if they don't match, then smoke-test the app:

```bash
./.venv/bin/python3 main.py
```

You should see the display clear and show the Home screen (time + weather)
within a few seconds. Press Ctrl+C to stop.

## Configuration

`config_local.py` (copied from `config_local.py.example`, gitignored):

- `LATITUDE` / `LONGITUDE` -- weather location. Get these from your zip code
  (e.g. `curl https://api.zippopotam.us/us/YOUR_ZIP`) or by right-clicking
  your location on Google Maps. Weather comes from
  [Open-Meteo](https://open-meteo.com), no API key needed.

Edit `config.py` for everything else:

- `TEMP_UNIT` -- `"fahrenheit"` or `"celsius"`.
- `WEATHER_REFRESH_SECONDS` / `READINGS_REFRESH_CHECK_SECONDS` /
  `CLOCK_REFRESH_SECONDS` -- polling/redraw cadence.
- `BUTTON_PINS` -- GPIO pin numbers, see above.
- `TIME_FORMAT` / `DATE_FORMAT` -- `strftime` patterns.

## Run automatically on boot

`systemd/eink-dashboard@.service` is a systemd *template* unit -- no
username is hardcoded in it. It expects the project to live at
`~/eink-dashboard` for whatever user you run it as; the username is passed
as the instance name (the part after `@`) when you enable it:

```bash
sudo cp systemd/eink-dashboard@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eink-dashboard@<username>.service
```

Replace `<username>` with the account you cloned/set up the project under
(check with `whoami`). If the project lives somewhere other than
`~/eink-dashboard` for that user, the template won't fit -- copy it to a
plain (non-`@`) unit file instead and hardcode `WorkingDirectory=`/
`ExecStart=` to the real path.

Check it's running (substituting your username again):

```bash
sudo systemctl status eink-dashboard@<username>.service
journalctl -u eink-dashboard@<username>.service -f
```

Reboot the Pi (`sudo reboot`) to confirm it starts automatically.

## Troubleshooting

- **`e-Paper init failed` / SPI errors**: SPI isn't enabled. Run
  `sudo raspi-config` -> Interface Options -> SPI -> enable, then reboot.
- **`PermissionError` on GPIO/SPI**: the service's user needs to be in the
  `gpio` and `spi` groups -- `groups <username>` to check;
  `sudo usermod -aG gpio,spi <username>` to fix, then log out/in or reboot.
- **Buttons don't do anything, or the wrong button does the wrong thing**:
  re-run `button_test.py` and fix `BUTTON_PINS` in `config.py`.
- **`ImportError: libopenjp2.so.7`**: `sudo apt-get install libopenjp2-7`
  (setup.sh already does this, but if you installed manually you may have
  missed it).
- **Reading screens show "Readings unavailable"**: `bible.usccb.org`
  returned an error (network issue, or their bot/WAF protection blocking
  the request -- this happened during development testing from a cloud IP,
  though a home residential IP is less likely to trigger it). The app
  keeps the last successfully fetched readings cached and retries
  automatically; check `journalctl -u eink-dashboard.service` for the
  actual error if it persists for more than a day.
- **`curl_cffi` fails to install**: you're likely on 32-bit Raspberry Pi OS;
  switch to 64-bit Bookworm (see Prerequisites).
- **`lgpio` fails to build** (`swig: No such file or directory`, or
  `cannot find -llgpio`): `gpiozero` needs a working `lgpio` to talk to the
  GPIO pins, but its pip package builds from source and that build chain is
  unreliable across Raspberry Pi OS versions. `setup.sh` avoids this by
  installing the pre-built `python3-lgpio` apt package and creating the venv
  with `--system-site-packages`. If you hit this error, your `.venv` was
  probably created before that fix -- delete and recreate it:
  `rm -rf .venv && ./setup.sh`.

## Known limitations (by design, for v1)

- **Every screen update does a full refresh** (brief black/white flash),
  including the once-a-minute clock tick. Investigated partial refresh:
  Waveshare's vendored V1 driver (`epd2in7.py`, what this panel actually
  uses -- confirmed by it working correctly this whole project) has no
  partial-refresh command path at all; that only exists in their `_V2`
  driver, which talks to a different, incompatible controller chip. True
  partial refresh isn't available on this specific panel's controller, not
  just unimplemented in the driver -- decided not to pursue hand-rolled LUT
  waveforms given the risk of poor visual quality without hardware to
  iterate against.
- **The display refreshes more often than the panel datasheet's stated
  180-second minimum** (once a minute on the Home screen) -- an explicit,
  informed tradeoff for this home project, at some undetermined cost to the
  panel's rated 1,000,000-cycle/5-year lifespan.
- **Long readings are paginated, not reflowed for the button count** --
  each page holds only what fits in a legible font at 264x176px.
- **Mass reading scraping is unofficial** (there's no public USCCB API);
  see the troubleshooting note above.
