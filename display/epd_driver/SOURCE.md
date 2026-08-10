`epd2in7.py` and `epdconfig.py` are vendored unmodified from Waveshare's official
e-Paper repo:

https://github.com/waveshareteam/e-Paper/blob/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd2in7.py
https://github.com/waveshareteam/e-Paper/blob/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py

Both carry an MIT license header in the file itself. Downloaded 2026-08-09.

Note: `epdconfig.py` auto-detects the platform at *import time* (greps
`/proc/cpuinfo` for "Raspberry") and will fail to import on non-Pi hardware
(e.g. a dev laptop) since it immediately tries to open SPI/GPIO. This package
is only importable on the actual Raspberry Pi.
