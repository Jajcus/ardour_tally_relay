#!/usr/bin/python3

import argparse
import logging
import signal
import time
from logging import debug, error, info, warning

import pythonosc.osc_server
import pythonosc.udp_client
from pythonosc.dispatcher import Dispatcher

import hid

LOG_FORMAT = '%(message)s'
POLL_INTERVAL = 1

# Supported USB relay vendor-id and product-id
USB_VID = 0x16c0
USB_PID = 0x05df

ON_COMMAND = [0x00,0xff,0x01,0x00,0x00,0x00,0x00,0x00,0x00]
OFF_COMMAND = [0x00,0xfd,0x01,0x00,0x00,0x00,0x00,0x00,0x00]

class SignalReceived(Exception):
    pass

class OSCClientServer(pythonosc.udp_client.SimpleUDPClient,
                      pythonosc.osc_server.BlockingOSCUDPServer):
    def __init__(self, local_address, remote_address, dispatcher, service_cb):
        self._service_cb = service_cb
        self._remote_addr = remote_address
        pythonosc.osc_server.BlockingOSCUDPServer.__init__(self,
                                                           local_address,
                                                           dispatcher)
    def service_actions(self):
        pythonosc.osc_server.BlockingOSCUDPServer.service_actions(self)
        self._service_cb()
    def send(self, content):
        self.socket.sendto(content.dgram, self._remote_addr)

class OSCRelay:
    def __init__(self):
        self._last_ping = 0
        self._last_hb = 0
        self.args = None
        self.ardour_addr = None
        self.server = None
        self.rec_enable = False
        self.record_tally = False
        self.relay_device = None

    def _open_relay_device(self, just_print=False):
        device = None
        try:
            for devinfo in hid.enumerate():
                if device is not None:
                    try:
                        device.close()
                    except OSError as err:
                        pass
                if devinfo["vendor_id"] != USB_VID:
                    continue
                if devinfo["product_id"] != USB_PID:
                    continue
                device = hid.device()
                try:
                    device.open_path(devinfo["path"])
                except OSError as err:
                    warning("Cannot open device %r: %s", devinfo["path"], err)
                    continue
                report = device.get_feature_report(0,9)
                device_serial = bytes(report[1:6]).rstrip(b"\x00")
                device_serial = device_serial.decode("us-ascii", "replace")
                if just_print:
                    info("Device %r found, serial number: %r",
                         devinfo["path"], device_serial)
                elif self.args.serial:
                    if self.args.serial == device_serial:
                        break
                    else:
                        debug("Ignoring USB Relay device %r", device_serial)
                        continue
                else:
                    debug("Using the first device found: %r (serial: %r)",
                          devinfo["path"], device_serial)
                    break
            else:
                if just_print:
                    return
                raise FileNotFoundError("No matching USB Relay device found")
            self.relay_device, device = device, None
        finally:
            if device is not None:
                try:
                    device.close()
                except OSError as err:
                    debug("device.close(): %s", err)
                device = None

    def _close_relay_device(self):
        if self.relay_device is not None:
            try:
                device.close()
            except OSError as err:
                debug("device.close(): %s", err)
            self.relay_device = None

    def toggle_light(self):
        if self.args.mode == "master":
            on = self.rec_enable
        elif self.args.mode == "track":
            on = self.record_tally
        else:
            on = self.rec_enable and self.record_tally
        info("Turning the tally light %s", "ON" if on else "OFF")
        for i in 1, 2:
            if not self.relay_device:
                try:
                    self._open_relay_device()
                except OSError as err:
                    warning("Could not open the relay device: %s", err)
                    break
            command = ON_COMMAND if on else OFF_COMMAND
            try:
                self.relay_device.write(command)
                break
            except OSError as err:
                warning("Could not write to the relay device: %s", err)
                self._close_relay_device()

    def handle_rec_enable_toggle(self, address, on):
        on = bool(on)
        debug("message received{!r}".format((address, on)))
        if on != self.rec_enable:
            info("Master Record %s", "ON" if on else "OFF")
            self.rec_enable = on
            self.toggle_light()

    def handle_record_tally(self, address, on):
        on = bool(on)
        debug("message received{!r}".format((address, on)))
        if on != self.record_tally:
            info("Track Record %s", "ON" if on else "OFF")
            self.record_tally = on
            self.toggle_light()

    def handle_heartbeat(self, address, value):
        debug("message received{!r}".format((address, value)))
        self._last_hb = time.time()

    def handle_any(self, address, value):
        debug("message received{!r}".format((address, value)))

    def _start_server(self):
        dispatcher = Dispatcher()
        self.server = OSCClientServer(("0.0.0.0", self.args.port),
                                      self.ardour_addr,
                                      dispatcher,
                                      self._service_action)
        dispatcher.map("/rec_enable_toggle", self.handle_rec_enable_toggle)
        dispatcher.map("/record_tally", self.handle_record_tally)
        dispatcher.map("/heartbeat", self.handle_heartbeat)
        dispatcher.set_default_handler(self.handle_any)

    def _ping_ardour(self):
        debug("Asking Ardour for feedback")
        self.server.send_message("/set_surface/feedback", 24)
        self._last_ping = time.time()

    def _service_action(self):
        now = time.time()
        waited = now - max(self._last_ping, self._last_hb)
        if waited > self.args.interval:
            debug("no message received in %.3fs", waited)
            self._ping_ardour()
        if self._last_hb:
            waited = now - self._last_hb
            if waited > self.args.interval * 3:
                info("No heartbeat heard from Ardour in %.3fs", waited)
                self.rec_enable = False
                self.record_tally = False
                self._last_hb = 0
                self.toggle_light()

    def _signal_handler(self, signum, frame):
        info("Signal %i received. Exiting.", signum)
        # server.shutdown() is unusable here :-(
        raise SignalReceived()

    def main(self):
        parser = argparse.ArgumentParser(
                description="Toggle USB relay in response to Ardour OSC messages.",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--port", "-p", default=8000, type=int,
                            help="Local port to listen on.")
        parser.add_argument("--ardour", "-a", default="localhost:3819",
                            help="Ardour host to connect to, with optional port number.")
        parser.add_argument("--mode", choices=["master", "track", "both"],
                            default="both",
                            help="Turn the light on when master record is enabled, track record or both.")
        parser.add_argument("--serial", "-s",
                            help="USB relay serial number.")
        parser.add_argument("--interval", "-i", default=5.0, type=float,
                            help="Ardour 'ping' interval.")
        parser.add_argument("--debug", "-d", action="store_true",
                            help="Enable debug output.")
        parser.add_argument("--detect", action="store_true",
                            help="Detect connected USB Relay devices.")
        self.args = parser.parse_args()

        if self.args.debug:
            logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

        if self.args.detect:
            self._open_relay_device(just_print=True)
            return

        if ":" in self.args.ardour:
            host, port = self.args.ardour.split(":", 1)
            port = int(port)
            self.ardour_addr = (host, port)
        else:
            self.ardour_addr = (self.args.ardour, 3819)

        signal.signal(signal.SIGTERM, self._signal_handler)

        self.toggle_light()

        info("Talking to Ardour at %s:%i", *self.ardour_addr)

        self._start_server()
        self._ping_ardour()
        try:
            self.server.serve_forever(POLL_INTERVAL)
        except (KeyboardInterrupt, SignalReceived):
            self.rec_enable = False
            self.record_tally = False
            self.toggle_light()

if __name__ == "__main__":
    osc_relay = OSCRelay()
    osc_relay.main()
