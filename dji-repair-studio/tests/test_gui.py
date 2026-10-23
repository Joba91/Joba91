import os
import time
import tkinter as tk
import unittest
from unittest.mock import patch
from studio_app import StudioApp
from studio_service import packet

class Device:
    def __init__(self, outcome='success'):
        self.pending=b'';self.closed=False;self.sent=[];self.outcome=outcome
    def write(self,req):
        self.sent.append(req)
        if self.outcome=='disconnect':raise OSError('USB disconnected')
        if req[9:11]==b'\0\1':
            payload=b'\0\0'+b'TEST-HW'.ljust(16,b'\0')+bytes(4)+(0x04000007).to_bytes(4,'little')
            self.pending=packet(req[5],req[4],int.from_bytes(req[6:8],'little'),0,1,payload,flags=128)
        else:
            self.pending=packet(req[5],req[4],int.from_bytes(req[6:8],'little'),4,8,b'\1',flags=128)
            self.pending+=packet(4,10,10,4,0x30,b'\x52\1',flags=128)
            self.pending+=packet(4,10,11,4,0x30,b'\x64'+(b'\3' if self.outcome=='fail' else b'\0'),flags=128)
        return len(req)
    def read(self,size):
        data=self.pending;self.pending=b''
        if not data:time.sleep(.005)
        return data
    def close(self):self.closed=True

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class GuiTests(unittest.TestCase):
    def setUp(self):self.app=StudioApp();self.app.update()
    def tearDown(self):
        if self.app.running:self.app.stop.set();self.wait_idle()
        self.app.close_window()
    def wait_idle(self):
        deadline=time.monotonic()+5
        while self.app.running and time.monotonic()<deadline:
            self.app.update();time.sleep(.01)
        self.assertFalse(self.app.running)
    def test_one_main_window_no_old_brand_and_sidebar_actions(self):
        self.app.after(300,self.app.quit);self.app.mainloop()
        texts=[self.app.title()]
        def walk(widget):
            for child in widget.winfo_children():
                self.assertNotIsInstance(child,tk.Toplevel)
                if 'text' in child.keys():texts.append(str(child.cget('text')))
                walk(child)
        walk(self.app)
        self.assertNotIn('yandron',' '.join(texts).lower())
        for button in self.app.operation_buttons:
            self.assertLess(button.winfo_rootx(),self.app.tabs.winfo_rootx())
        self.assertEqual(len(self.app.operation_buttons),20)
    def test_offline_tools_remain_inside_main_window(self):
        self.app.dispatch('Analizar')
        self.assertIn('"payload": "01"',self.app.packet_output.get('1.0','end'))
        self.app.dispatch('Generar')
        self.assertTrue(self.app.packet_output.get('1.0','end').startswith('55 0d'))
        self.assertFalse(self.app.running)
    def test_module_worker_updates_table_progress_and_releases_device(self):
        device=Device()
        with patch('studio_app.backend.open_serial_port',return_value=device):
            self.app.dispatch('Módulos')
            self.assertTrue(all(str(b['state'])=='disabled' for b in self.app.operation_buttons))
            self.wait_idle()
        self.assertEqual(len(self.app.results.get_children()),4)
        self.assertEqual(self.app.progress_value.get(),100)
        self.assertTrue(device.closed)
        self.assertEqual(len(device.sent),4)
        self.assertTrue(all(str(b['state'])=='normal' for b in self.app.operation_buttons))
    def test_failed_io_does_not_show_100(self):
        device=Device('disconnect')
        with patch('studio_app.backend.open_serial_port',return_value=device):
            self.app.dispatch('Identificar');self.wait_idle()
        self.assertTrue(device.closed)
        self.assertEqual(self.app.percent_text.get(),'Sin confirmar')
    def test_calibration_success_and_failure_display_received_progress(self):
        self.app.firmware.set('01.00.0600');self.app.prepared.set(True)
        for outcome,percentage in [('success',100),('fail',20)]:
            with self.subTest(outcome=outcome):
                device=Device(outcome)
                with patch('studio_app.backend.open_serial_port',return_value=device),patch('studio_app.messagebox.askyesno',return_value=True):
                    self.app.dispatch('JointCoarse');self.wait_idle()
                self.assertTrue(device.closed)
                self.assertEqual(self.app.progress_value.get(),percentage)
                self.assertEqual(self.app.progress_state.failed,outcome=='fail')
    def test_unvalidated_model_cannot_start_calibration(self):
        for model in ('Mavic 4 Pro','Mavic 3 Classic'):
            self.app.model.set(model)
            with patch('studio_app.messagebox.showerror') as error,patch('studio_app.backend.open_serial_port') as opening:
                self.app.dispatch('JointCoarse')
            error.assert_called_once();opening.assert_not_called()
