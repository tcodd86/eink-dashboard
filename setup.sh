#!/usr/bin/env bash
# One-shot provisioning for the e-ink dashboard on Raspberry Pi OS (Bookworm, 64-bit).
# Run from inside the eink-dashboard/ directory: ./setup.sh
set -euo pipefail

echo "== Checking Python version (3.10+ required) =="
python3 --version
python3 -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10+ required -- see README prerequisites'"

echo "== Installing system dependencies =="
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libopenjp2-7 fonts-dejavu-core git

echo "== Enabling SPI =="
REBOOT_NEEDED=0
if ! (grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null || grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null); then
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled -- a reboot is required before the display will work."
    REBOOT_NEEDED=1
else
    echo "SPI already enabled."
fi

echo "== Creating virtual environment (.venv) =="
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "== Setting up local config =="
if [ ! -f config_local.py ]; then
    cp config_local.py.example config_local.py
    echo "Created config_local.py -- edit it now and fill in your latitude/longitude."
else
    echo "config_local.py already exists, leaving it alone."
fi

echo
echo "== Setup complete =="
echo "Next steps:"
echo "  1. Edit config_local.py with your latitude/longitude (see README Configuration)."
if [ "$REBOOT_NEEDED" -eq 1 ]; then
    echo "  2. Reboot now: sudo reboot"
    echo "  3. After rebooting, run: ./.venv/bin/python3 button_test.py"
else
    echo "  2. Run: ./.venv/bin/python3 button_test.py"
fi
echo "     Confirm the printed GPIO numbers match config.BUTTON_PINS -- edit config.py if not."
echo "  3. Smoke test the app: ./.venv/bin/python3 main.py   (Ctrl+C to stop)"
echo "  4. Install it as a service -- see README.md 'Run automatically on boot'"
