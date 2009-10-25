# -*- coding: utf-8 -*-
#
# mididings
#
# Copyright (C) 2008-2009  Dominic Sacré  <dominic.sacre@gmx.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#

import _mididings
import main
import patch
import scene
import event
import util
import misc

import time
import weakref
import gc


class Engine(_mididings.Engine):
    def __init__(self, scenes, control, pre, post):
        self.in_ports = self.make_portnames(main._config['in_ports'], 'in_')
        self.out_ports = self.make_portnames(main._config['out_ports'], 'out_')

        _mididings.Engine.__init__(
            self, main._config['backend'],
            main._config['client_name'],
            misc.make_string_vector(self.in_ports),
            misc.make_string_vector(self.out_ports),
            main._config['verbose']
        )

        self.scene_names = {}

        for i, s in scenes.items():
            if isinstance(s, scene.Scene):
                init = [s.init_patch] if s.init_patch else []
                proc = s.patch
                if s.name:
                    self.scene_names[i] = s.name
            elif isinstance(s, tuple):
                init = [s[0]]
                proc = s[1]
            else:
                init = []
                proc = s

            init += patch.get_init_actions(proc)

            self.add_scene(i - main._config['data_offset'], patch.Patch(proc), patch.Patch(init))

        ctrl = patch.Patch(control) if control else None
        pre_patch = patch.Patch(pre) if pre else None
        post_patch = patch.Patch(post) if post else None
        self.set_processing(ctrl, pre_patch, post_patch)

        self.scene_switch_callback = None
        self.quit = False

        # delay before actually sending any midi data (give qjackctl patchbay time to react...)
        if main._config['start_delay'] != None:
            if main._config['start_delay'] > 0:
                time.sleep(main._config['start_delay'])
            else:
                raw_input("press enter to start midi processing...")

        main.TheEngine = weakref.proxy(self)

        gc.collect()
        gc.disable()

    def run(self, first_scene, scene_switch_callback):
        # hmmm...
        self.scene_switch_callback = scene_switch_callback
        self.start(util.scene_number(first_scene))

        if main._config['osc_port']:
            import liblo
            s = liblo.Server(main._config['osc_port'])
            s.add_method('/mididings/switch_scene', 'i', self.osc_switch_scene_cb)
            s.add_method('/mididings/quit', '', self.osc_quit_cb)
            while not self.quit:
                s.recv(1000)
        else:
            while True:
                time.sleep(3600)

    def process_file(self):
        self.start(0)

    def make_portnames(self, ports, prefix):
        if misc.issequence(ports):
            return ports
        else:
            return [prefix + str(n + main._config['data_offset']) for n in range(ports)]

    def scene_switch_handler(self, n, found):
        n += main._config['data_offset']
        name = self.scene_names[n] if n in self.scene_names else None

        if main._config['verbose']:
            if found:
                if name:
                    print "switching to scene %d: %s" % (n, name)
                else:
                    print "switching to scene %d" % n
            else:
                print "no such scene: %d" % n

        if found:
            if self.scene_switch_callback:
                self.scene_switch_callback(n)

            if main._config['osc_notify_port']:
                import liblo
                liblo.send(main._config['osc_notify_port'], '/mididings/scene', n)

    def osc_switch_scene_cb(self, path, args):
        self.switch_scene(args[0] - main._config['data_offset'])

    def osc_quit_cb(self, path, args):
        self.quit = True
