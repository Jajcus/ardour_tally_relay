
Tally light driver for use with Ardour and cheap USB relay devices
==================================================================

This simple script connectes to asks Ardour for current 'recording enabled'
status via OSC and when recording is enabled toggles a USB relay to turn the
'Recording' lamp on.

It is compatible with the cheap chinese 'USB Relay' devices idenfied as::

  ID 16c0:05df Van Ooijen Technische Informatica HID device except mice, keyboards, and joysticks

Currently only the first relay on the device is supported (in case of devices
with multiple relays).

Requirements
------------

* Compatible USB device
* Ardour 5 or other compatible version
* Python 3.5 or newer
* `hidapi <https://pypi.org/project/hidapi/>`_ Python module
* `python-osc <https://github.com/attwad/python-osc>`_ Python module

Usage
-----

Installation
............

First, to allow non-root user to use this script, add the provided
50-usbrelay.rules file to /etc/udev/rules.d. Update the file for your own needs
(mode 0666 is not good for everybody).

Just running the script would connect to the Ardour running on the local host
and use the first USB relay device detected. Use the ``--ardour`` option to
point to a different host running Ardour.

See ``ardour_tally_relay.py --help`` for other options.

Ardour configuration
....................

To make Ardour work with this script OSC control surface support must be
enabled. To do that enter Preferences / Control Surfaces, select 'Open Sound
Control (OSC)' and check 'Enable'.

The defaults in 'Show Protocol Settings' dialog should work, but setting the
Port Mode to 'Auto' may make sense. This will allow to use any local port for
``ardour_tally_relay`` and using other OSC servers on the same host, without
any further configuration in Ardour.
