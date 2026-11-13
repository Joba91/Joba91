import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from gimbal_profiles import FLIP,GIMBAL_PROJECTS
from studio_service import validate
from vision_usb_inventory import collect_usb_profile,product_family
from test_vision_usb_inventory import node,inventory

class FlipProfileTests(unittest.TestCase):
    def test_declared_firmware_does_not_authorize_factory_or_calibration(self):
        p=GIMBAL_PROJECTS[FLIP]
        self.assertEqual(p['firmware_declared'],'01.00.1500')
        self.assertFalse(p['calibration_available']);self.assertIsNone(p['internal_product_code'])
        for action in ('JointCoarse','LinearHall','Entrar modo fabrica','Salir modo fabrica','Escuchar progreso (20 s)'):
            with self.assertRaisesRegex(ValueError,'DJI Flip'):validate(FLIP,'01.00.1500',action,True)
    def test_product_descriptor_matching_is_strict(self):
        for value in ('DJI Flip','DJI Flip-SYNTHETIC','Flip-SYNTHETIC'):
            self.assertEqual(product_family(value),FLIP)
        for value in ('Flip 2','Flip2-SYNTHETIC','DJI Flip Pro','Mini 3 Pro','Air 3'):
            self.assertNotEqual(product_family(value),FLIP)
    def test_report_is_gimbal_scoped_and_never_a_calibration_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'flip.zip'
            result=collect_usb_profile(path,FLIP,'01.00.1500',collector=lambda **kw:inventory(node(product='DJI Flip-SYNTHETIC')))
            self.assertTrue(result['model_descriptor_matches']);self.assertFalse(result['calibration_performed'])
            self.assertEqual(result['factory_commands_sent'],0);self.assertEqual(result['service_commands_sent'],0)
            self.assertEqual(result['requested_calibrations'],['JointCoarse','LinearHall'])
            with ZipFile(path) as z:
                report=json.loads(z.read('DJI-REPAIR-informe.json'))
                self.assertIn('gimbal',report);self.assertNotIn('vision',report)
                self.assertEqual(report['modelo_declarado'],FLIP)
    def test_unknown_flip_pid_is_recorded_without_assuming_existing_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            row=node('USB\\VID_2CA3&PID_9999\\SYNTHETIC','DJI Flip-SYNTHETIC')
            result=collect_usb_profile(Path(folder)/'flip.zip',FLIP,'01.00.1500',collector=lambda **kw:inventory(row))
            self.assertEqual(result['devices'],[row]);self.assertFalse(result['usb_endpoints_verified'])
            self.assertFalse(result['calibration_available'])

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class FlipGuiTests(unittest.TestCase):
    def setUp(self):
        from studio_app import StudioApp
        self.app=StudioApp();self.app.update();self.app.model.set(FLIP);self.app.update()
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):
        if self.app.running:self.app.stop.set();self.wait_idle()
        self.app.close_window();self.temp.cleanup()
    def wait_idle(self):
        deadline=time.monotonic()+5
        while self.app.running and time.monotonic()<deadline:self.app.update();time.sleep(.01)
        self.assertFalse(self.app.running)
    def test_selection_opens_gimbal_workspace_and_retains_flip_in_event_loop(self):
        self.app.after(150,self.app.quit);self.app.mainloop()
        self.assertEqual(self.app.model.get(),FLIP);self.assertEqual(self.app.firmware.get(),'01.00.1500')
        self.assertEqual(self.app.tabs.select(),str(self.app.pages['Calibración']))
        self.assertTrue(self.app.flip_gimbal.winfo_manager());self.assertFalse(self.app.prepared.get())
        from studio_app import USB_PROFILE_ACTION
        button=self.app.operation_buttons[self.app.operation_actions.index('Identificar')]
        self.assertGreaterEqual(button.winfo_rooty(),self.app.action_canvas.winfo_rooty())
        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),self.app.action_canvas.winfo_rooty()+self.app.action_canvas.winfo_height())
    def test_only_inventory_and_offline_actions_enabled(self):
        from studio_app import USB_PROFILE_ACTION
        for button,action in zip(self.app.operation_buttons,self.app.operation_actions):
            self.assertEqual(str(button['state'])=='normal',action in (USB_PROFILE_ACTION,'Identificar','JointCoarse','LinearHall','Analizar','Generar','Convertir'),action)
    def test_no_entry_path_runs_another_aircraft_calibration_or_sensor_query(self):
        from studio_app import VISION_ACTIONS,USB_PROFILE_ACTION
        actions=['Entrar modo fabrica','Salir modo fabrica','Módulos','Diagnóstico','Parámetros','Cámara','Gimbal heredado']+[a for a in VISION_ACTIONS if a!=USB_PROFILE_ACTION]
        with patch('studio_app.messagebox.showinfo'),patch('studio_app.backend.open_serial_port') as opening,patch('studio_app.filedialog.askopenfilename') as files:
            for action in actions:self.app.dispatch(action)
            self.app.dispatch_vision('Capturar USB pasivo')
        opening.assert_not_called();files.assert_not_called();self.assertEqual(self.app.model.get(),FLIP)
    def test_inventory_uses_flip_firmware_and_gimbal_report_in_the_same_window(self):
        from studio_app import USB_PROFILE_ACTION
        dest=self.root/'flip.zip'
        def collect(*args,**kwargs):
            self.assertEqual(args[1:3],(FLIP,'01.00.1500'))
            return collect_usb_profile(*args,**kwargs,collector=lambda **kw:inventory(node(product='DJI Flip-SYNTHETIC')))
        with patch('studio_app.collect_usb_profile',side_effect=collect),patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)),patch('studio_app.backend.open_serial_port') as opening:
            self.app.dispatch(USB_PROFILE_ACTION);self.wait_idle()
        opening.assert_not_called();self.assertTrue(dest.is_file());self.assertIn('gimbal',self.app.report)
        self.assertNotIn('vision',self.app.report);self.assertEqual(len(self.app.flip_gimbal.nodes.get_children()),1)
        self.assertEqual(self.app.model.get(),FLIP);self.assertEqual(self.app.progress_value.get(),100)
        self.assertFalse(self.app.report['gimbal']['usb_profile']['calibration_available'])
    def test_cancelling_save_starts_no_worker(self):
        from studio_app import USB_PROFILE_ACTION
        with patch('studio_app.filedialog.asksaveasfilename',return_value=''),patch('studio_app.collect_usb_profile') as collect:
            self.app.dispatch(USB_PROFILE_ACTION)
        collect.assert_not_called();self.assertFalse(self.app.running)
    def test_bad_firmware_stops_before_dialog(self):
        self.app.firmware.set('unknown')
        from studio_app import USB_PROFILE_ACTION
        with patch('studio_app.messagebox.showerror') as error,patch('studio_app.filedialog.asksaveasfilename') as save:
            self.app.dispatch(USB_PROFILE_ACTION)
        error.assert_called_once();save.assert_not_called()
    def test_switching_models_clears_prepared_progress_and_old_results(self):
        self.app.firmware.set('01.00.1600');self.app.progress_value.set(100)
        self.app.report={'old':'flip'};self.app.model.set('Mavic 3');self.app.update()
        self.app.firmware.set('01.00.0600');self.app.prepared.set(True)
        self.app.model.set(FLIP);self.app.update()
        self.assertFalse(self.app.prepared.get());self.assertEqual(self.app.progress_value.get(),0)
        self.assertIsNone(self.app.report);self.assertEqual(self.app.firmware.get(),'01.00.1600')
        self.app.model.set('Mavic 3');self.app.update()
        self.assertEqual(self.app.firmware.get(),'01.00.0600');self.assertFalse(self.app.prepared.get())
        self.assertFalse(self.app.flip_gimbal.winfo_manager())

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class FlipQueryGuiTests(unittest.TestCase):
    setUp=FlipGuiTests.setUp
    tearDown=FlipGuiTests.tearDown
    wait_idle=FlipGuiTests.wait_idle
    def test_version_query_uses_own_transport_and_displays_both_module_versions(self):
        from test_flip_query import save_reference,Exchange
        from flip_gimbal_query import query_flip_modules,load_reference
        profile=save_reference(self.root/'profile.zip');out=self.root/'query.zip'
        ex=Exchange(load_reference(profile,'01.00.1500'))
        def query(*args,**kwargs):
            return query_flip_modules(*args,**kwargs,transport_factory=lambda ref:ex.transport,clock=ex.clock)
        with patch('studio_app.query_flip_modules',side_effect=query),patch('studio_app.filedialog.askopenfilename',return_value=str(profile)),patch('studio_app.filedialog.asksaveasfilename',return_value=str(out)),patch('studio_app.backend.open_serial_port') as legacy:
            self.app.dispatch('Identificar');self.wait_idle()
        legacy.assert_not_called();self.assertTrue(out.is_file())
        data=self.app.report['gimbal']['module_query']
        self.assertEqual(len(self.app.flip_gimbal.nodes.get_children()),2)
        self.assertEqual(data['bulk_out_bytes_confirmed'],26)
        self.assertFalse(data['calibration_available']);self.assertEqual(data['factory_commands_sent'],0)
        self.assertEqual(self.app.progress_value.get(),100)
        self.assertIn('calibración pendiente',self.app.connection_text.get())
    def test_cancelled_or_bad_reference_opens_no_transport_or_output_dialog(self):
        with patch('studio_app.filedialog.askopenfilename',return_value=''),patch('studio_app.filedialog.asksaveasfilename') as output,patch('studio_app.query_flip_modules') as query:
            self.app.dispatch('Identificar')
        output.assert_not_called();query.assert_not_called()
        bad=self.root/'bad.zip';bad.write_bytes(b'not a zip')
        with patch('studio_app.filedialog.askopenfilename',return_value=str(bad)),patch('studio_app.filedialog.asksaveasfilename') as output,patch('studio_app.messagebox.showerror') as error,patch('studio_app.query_flip_modules') as query:
            self.app.dispatch('Identificar')
        error.assert_called_once();output.assert_not_called();query.assert_not_called()
    def test_serial_mode_is_not_used_for_the_flip_probe(self):
        self.app.mode.set('port')
        with patch('studio_app.messagebox.showerror') as error,patch('studio_app.filedialog.askopenfilename') as files:
            self.app.dispatch('Identificar')
        error.assert_called_once();files.assert_not_called()

@unittest.skipUnless(os.environ.get('DISPLAY') or os.name=='nt','Requires a graphical display')
class FlipCalibrationGuiTests(unittest.TestCase):
    setUp=FlipGuiTests.setUp
    tearDown=FlipGuiTests.tearDown
    wait_idle=FlipGuiTests.wait_idle
    def modules_reference(self):
        from test_flip_query import save_reference,Exchange
        from flip_gimbal_query import load_reference,query_flip_modules
        profile=save_reference(self.root/'reference.zip');ref=load_reference(profile,'01.00.1500');ex=Exchange(ref)
        modules=self.root/'modules.zip'
        query_flip_modules(modules,profile,'01.00.1500',transport_factory=lambda r:ex.transport,clock=ex.clock)
        return modules
    def test_experimental_joint_runs_own_guarded_path_and_saves_gimbal_result(self):
        from test_flip_calibration import CalibrationFixture
        from flip_gimbal_calibration import run_flip_calibration,load_calibration_reference
        modules=self.modules_reference();dest=self.root/'cal.zip'
        fixture=CalibrationFixture(load_calibration_reference(modules,'01.00.1500'),'JointCoarse')
        def run(*args,**kw):return run_flip_calibration(*args,**kw,transport_factory=lambda r,a:fixture.transport,clock=fixture.clock,max_seconds=2)
        with patch('studio_app.filedialog.askopenfilename',return_value=str(modules)),patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)),patch('studio_app.messagebox.askyesno',return_value=True),patch('studio_app.run_flip_calibration',side_effect=run),patch('studio_app.backend.open_serial_port') as legacy:
            self.app.dispatch('JointCoarse');self.wait_idle()
        legacy.assert_not_called();self.assertTrue(dest.is_file());self.assertEqual(self.app.progress_value.get(),100)
        data=self.app.report['gimbal']['calibration_probe']
        self.assertEqual(data['state'],'equipo_informa_fin');self.assertTrue(data['experimental'])
        self.assertEqual(data['factory_commands_sent'],0);self.assertEqual(data['calibration_requests_attempted'],1)
        self.assertEqual(len(self.app.flip_gimbal.nodes.get_children()),1)
    def test_declining_operation_or_wrong_firmware_opens_no_transport(self):
        modules=self.modules_reference();dest=self.root/'cal.zip'
        with patch('studio_app.filedialog.askopenfilename',return_value=str(modules)),patch('studio_app.filedialog.asksaveasfilename',return_value=str(dest)),patch('studio_app.messagebox.askyesno',return_value=False),patch('studio_app.run_flip_calibration') as run:
            self.app.dispatch('LinearHall')
        run.assert_not_called();self.assertFalse(dest.exists());self.assertFalse(self.app.running)
        self.app.firmware.set('01.00.1600')
        with patch('studio_app.messagebox.showerror') as error,patch('studio_app.filedialog.askopenfilename') as files:
            self.app.dispatch('JointCoarse')
        error.assert_called_once();files.assert_not_called()
