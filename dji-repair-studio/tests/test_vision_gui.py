import hashlib
import json
import os
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_app import StudioApp
from test_vision import USER_FRAME

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class VisionGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        with patch('vision_services.subprocess.run') as probe,patch('studio_app.backend.open_serial_port') as device:
            self.app=StudioApp();self.app.update()
        probe.assert_not_called();device.assert_not_called()
    def tearDown(self):
        if self.app.running:self.app.stop.set();self.wait_idle()
        self.app.close_window();self.temp.cleanup()
    def wait_idle(self):
        deadline=time.monotonic()+5
        while self.app.running and time.monotonic()<deadline:self.app.update();time.sleep(.01)
        self.assertFalse(self.app.running)
    def import_package(self):
        (self.root/'sensor.bin').write_bytes(b'sensor-data')
        (self.root/'MD5SUMS').write_text(hashlib.md5(b'sensor-data',usedforsecurity=False).hexdigest()+'  sensor.bin\n')
        with patch('studio_app.filedialog.askdirectory',return_value=str(self.root)):
            self.app.dispatch('Importar carpeta visión');self.wait_idle()
    def test_import_capture_and_export_all_results_with_no_usb_or_network(self):
        with patch('studio_app.backend.open_serial_port') as device,patch('vision_services.subprocess.run') as probe:
            self.import_package()
            self.assertEqual(self.app.model.get(),'Mini 4 Pro')
            self.assertEqual(self.app.vision.reports['package']['integrity']['state'],'confirmado')
            self.assertEqual(self.app.vision.reports['package']['compatibility']['state'],'desconocido')
            self.assertEqual(len(self.app.vision.inventory.get_children()),2)
            capture=self.root/'capture.bin';capture.write_bytes(USER_FRAME)
            with patch('studio_app.filedialog.askopenfilename',return_value=str(capture)):
                self.app.dispatch('Analizar captura visión');self.wait_idle()
            self.assertEqual(self.app.vision.reports['capture']['valid_frames'],1)
            dest=self.root/'report.json'
            with patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)):self.app.save_report()
            saved=json.loads(dest.read_text())
            self.assertIn('package',saved['vision']);self.assertIn('capture',saved['vision'])
            probe.assert_not_called();device.assert_not_called()
        self.assertFalse(any(isinstance(w,tk.Toplevel) for w in self.app.winfo_children()))
    def test_failed_import_replaces_previous_inventory(self):
        self.import_package()
        with patch('studio_app.filedialog.askdirectory',return_value=str(self.root/'missing')):
            self.app.dispatch('Importar carpeta visión');self.wait_idle()
        self.assertEqual(self.app.vision.reports['package']['state'],'error')
        self.assertEqual(len(self.app.vision.inventory.get_children()),0)
        self.assertIn('falló',self.app.vision.source.get())
    def test_binary_sensor_table_and_export_preserve_historical_status(self):
        from test_sensor_records import SensorRecordTests
        from test_history import log_pair
        from vision_history import analyze_dji_log
        query,record=SensorRecordTests().frames()
        result=analyze_dji_log(log_pair(query,record,'msg:Log: frontleft=ABCTAC10071234\n'))
        self.app.vision.apply_report('capture',result)
        view=self.app.vision
        self.assertEqual(view.tabs.select(),str(view.sensor_page))
        row=view.sensor_records.item(view.sensor_records.get_children()[0])
        self.assertEqual(row['values'][:2],['ABCTAC10071234','coincide'])
        self.assertIn('1 SN convertidos',view.sensor_summary.get())
        self.assertEqual(view.reports['capture']['identity']['state'],'desconocido')
    def test_new_capture_clears_old_sensor_table(self):
        from test_sensor_records import SensorRecordTests
        from test_history import log_pair
        from vision_history import analyze_dji_log
        query,record=SensorRecordTests().frames()
        self.app.vision.apply_report('capture',analyze_dji_log(log_pair(query,record)))
        self.app.vision.apply_report('capture',{'state':'error','detail':'Unreadable capture'})
        self.assertEqual(self.app.vision.sensor_records.get_children(),())
        self.assertIn('0 SN convertidos',self.app.vision.sensor_summary.get())
    def test_passive_capture_requires_declared_firmware_before_usb_or_save_dialog(self):
        with patch('studio_app.messagebox.showerror') as error,patch('studio_app.capture_passive') as capture,patch('studio_app.filedialog.asksaveasfilename') as save:
            self.app.dispatch('Capturar USB pasivo')
        error.assert_called_once();capture.assert_not_called();save.assert_not_called()
        self.assertFalse(self.app.running)
    def test_passive_capture_saves_received_bytes_and_exportable_receipt(self):
        from test_passive_usb import Receiver,Clock
        from test_sensor_records import sample
        from studio_service import packet
        from vision_usb_passive import capture_passive
        clock=Clock();frame=packet(0x12,0x2a,900,0x24,0x26,sample(),flags=0)
        receiver=Receiver(clock,[frame]);dest=self.root/'new-usb.bin'
        self.app.vision.firmware.set('01.00.1100')
        def simulated_capture(*args,**kwargs):
            return capture_passive(*args,**kwargs,transport_factory=lambda:receiver,clock=clock)
        with patch('studio_app.capture_passive',side_effect=simulated_capture),patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)),patch('studio_app.backend.open_serial_port') as legacy:
            self.app.dispatch('Capturar USB pasivo');self.wait_idle()
        legacy.assert_not_called();self.assertEqual(dest.read_bytes(),frame)
        data=self.app.vision.reports['capture'];self.assertEqual(data['origin'],'live_usb_passive')
        self.assertEqual(data['usb_capture']['protocol_commands_sent'],0)
        self.assertEqual(data['perception_records']['counts']['decoded'],1)
        self.assertIn('Recepción USB actual',self.app.vision.sensor_provenance.get())
        self.assertEqual(len(self.app.vision.sensor_records.get_children()),1)
        self.assertEqual(self.app.progress_value.get(),100)
        from zipfile import ZipFile
        bundle=dest.with_suffix('.zip');self.assertTrue(bundle.is_file())
        with ZipFile(bundle) as z:
            self.assertEqual(z.read(dest.name),frame)
            saved=json.loads(z.read('DJI-REPAIR-informe.json'))
            self.assertEqual(saved['vision']['capture']['usb_capture']['protocol_commands_sent'],0)
            self.assertEqual(saved['version'],'1.2.5')
    def test_failed_open_still_creates_zip_with_the_complete_error_report(self):
        from vision_usb_passive import capture_passive,UsbOpeningError
        from zipfile import ZipFile
        dest=self.root/'failed-usb.bin';self.app.vision.firmware.set('01.00.1100')
        diagnostics=[{'backend':'libusb0','stage':'identify_libusb0_interfaces','message':'No unique MI04',
                      'exception_type':'LegacyInterfaceError'}]
        def failed_capture(*args,**kwargs):
            return capture_passive(*args,**kwargs,transport_factory=lambda:(_ for _ in ()).throw(UsbOpeningError(diagnostics)))
        with patch('studio_app.capture_passive',side_effect=failed_capture),patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)):
            self.app.dispatch('Capturar USB pasivo');self.wait_idle()
        self.assertEqual(self.app.report['resultado']['estado'],'error')
        with ZipFile(dest.with_suffix('.zip')) as z:
            self.assertEqual(z.read(dest.name),b'')
            saved=json.loads(z.read('DJI-REPAIR-informe.json'))
            self.assertEqual(saved['vision']['capture']['usb_capture']['opening_diagnostics'],diagnostics)
            self.assertEqual(saved['resultado']['estado'],'error')
    def test_vision_tab_reveals_its_sidebar_actions(self):
        self.app.select_page('Visión Mini 4 Pro')
        self.app.after(100,self.app.quit);self.app.mainloop()
        canvas=self.app.action_canvas
        for button in self.app.operation_buttons[-6:]:
            self.assertGreaterEqual(button.winfo_rooty(),canvas.winfo_rooty())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),canvas.winfo_rooty()+canvas.winfo_height())
    def test_mini4_active_operations_never_open_transport(self):
        self.app.connection_text.set('consulta_completada')
        self.app.model.set('Mini 4 Pro')
        self.assertIn('consulta activa no habilitada',self.app.connection_text.get())
        self.assertTrue(all(str(b['state'])=='disabled' for b in self.app.operation_buttons[:11]))
        self.assertTrue(all(str(b['state'])=='normal' for b in self.app.operation_buttons[-6:]))
        with patch('studio_app.messagebox.showinfo'),patch('studio_app.backend.open_serial_port') as device:
            for action in ('Identificar','Módulos','JointCoarse','Entrar modo fabrica','Cámara','Parámetros'):
                self.app.dispatch(action)
            device.assert_not_called()
        self.assertFalse(self.app.running)
    def test_unavailable_identity_is_not_simulated_success(self):
        with patch('studio_app.backend.open_serial_port') as device:
            self.app.dispatch('Identificación visión');self.wait_idle()
        device.assert_not_called()
        self.assertEqual(self.app.report['resultado']['estado'],'desconocido')
        self.assertFalse(self.app.vision.reports['identity']['data']['usb_enabled'])
    def test_server_only_runs_on_requested_action(self):
        self.app.vision.url.set('https://authorized.example:8443')
        with patch('studio_app.AuthorizedServiceProvider.probe',return_value={'state':'error','detail':'Test server unavailable','source':'Test mock'}) as probe:
            self.app.dispatch('Comprobar servidor visión');self.wait_idle()
        probe.assert_called_once_with(5.)
        self.assertEqual(self.app.vision.reports['server']['state'],'error')
    def test_secret_bearing_url_never_leaves_ui(self):
        self.app.vision.url.set('https://user:secret@example.com')
        with patch('studio_app.messagebox.showerror'),patch('studio_app.AuthorizedServiceProvider.probe') as probe:
            self.app.dispatch('Comprobar servidor visión')
        probe.assert_not_called();self.assertFalse(self.app.running)
