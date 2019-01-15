
Tally light driver for use with Ardour and cheap USB relay devices
==================================================================

This simple script connectes to asks Ardour for current 'recording enabled'
status via OSC and when recording is enabled toggles a USB relay to turn the
'Recording' lamp on.

It is compatible with the cheap chinese 'USB Relay' devices idenfied as::

  ID 16c0:05df Van Ooijen Technische Informatica HID device except mice, keyboards, and joysticks

Currently only the first relay on the device is supported (in case of devices
with multiple relays).

Usage
-----

First, to allow non-root user to use this script, add the provided
50-usbrelay.rules file to /etc/udev/rules.d. Update the file for your own needs
(mode 0666 is not good for everybody).

Just running the script would connect to the Ardour running on the local host
and use the first USB relay device detected.

See ``ardour_tally_relay.py --help`` for available options.
