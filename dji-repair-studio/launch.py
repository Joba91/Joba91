"""One main window. --smoke-test validates startup without opening a drone."""
import json
import sys
import tkinter as tk
from pathlib import Path

def main():
    if '--vision-probe-worker' in sys.argv:
        from vision_services import probe_worker
        probe_worker(sys.argv[sys.argv.index('--vision-probe-worker')+1],sys.argv[sys.argv.index('--vision-probe-worker')+2])
        return
    from studio_app import StudioApp
    app = StudioApp()
    if '--smoke-test' in sys.argv:
        app.update()
        app.offline('Generar')
        generated = app.packet_output.get('1.0', 'end').strip()
        app.offline('Analizar')
        analyzed = json.loads(app.packet_output.get('1.0', 'end'))
        import hashlib
        import tempfile
        from vision_packages import inspect_package
        from vision_protocol import decode_bytes
        from vision_interfaces import UnavailableIdentification, LocalCalibrationProvider
        with tempfile.TemporaryDirectory(prefix='dji-vision-smoke-') as directory:
            root=Path(directory);data=b'SYNTHETIC TEST DATA; NOT A CALIBRATION'
            (root/'example.bin').write_bytes(data)
            (root/'MD5SUMS').write_text(hashlib.md5(data,usedforsecurity=False).hexdigest()+'  example.bin\n',encoding='utf-8')
            inventory=inspect_package(root)
            app.vision.apply_report('package',inventory)
            vision_report={'test_data':'synthetic; not the user calibration package',
                'inventory_files':inventory['file_count'],'md5_state':inventory['integrity']['state'],
                'compatibility':LocalCalibrationProvider().compatibility(inventory,None).state,
                'identity':UnavailableIdentification().identify().state,
                'write_enabled':False,'usb_enabled':False,
                'framing_valid':decode_bytes(bytes.fromhex(generated))['valid_frames']==1}
        report = {
            'interfaz': app.title(),
            'ventanas_principales': 1 + sum(isinstance(w, tk.Toplevel) for w in app.winfo_children()),
            'generador': generated,
            'analizador_payload': analyzed['payload'],
            'python': sys.version,
            'usb_backend_cargado': None,
            'operaciones_usb_ejecutadas': 0,
            'vision': vision_report,
        }
        if '--smoke-test-probe' in sys.argv:
            from vision_services import probe_server
            # Explicit CLI validation against loopback only, never historical DJI servers.
            report['loopback_probe_worker']=probe_server('https://127.0.0.1:1',5)
        if sys.platform == 'win32':
            import usb.backend.libusb1
            native = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'libusb-1.0.dll'
            report['usb_backend_cargado'] = usb.backend.libusb1.get_backend(find_library=lambda name: str(native)) is not None
        app.close_window()
        path = Path(sys.argv[sys.argv.index('--smoke-test')+1])
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    app.mainloop()

if __name__ == '__main__':
    main()
