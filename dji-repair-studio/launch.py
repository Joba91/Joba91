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
        from vision_protocol import decode_bytes, analyze_capture
        from vision_interfaces import UnavailableIdentification, LocalCalibrationProvider
        with tempfile.TemporaryDirectory(prefix='dji-vision-smoke-') as directory:
            root=Path(directory);data=b'SYNTHETIC TEST DATA; NOT A CALIBRATION'
            (root/'example.bin').write_bytes(data)
            (root/'MD5SUMS').write_text(hashlib.md5(data,usedforsecurity=False).hexdigest()+'  example.bin\n',encoding='utf-8')
            inventory=inspect_package(root)
            app.vision.apply_report('package',inventory)
            from studio_service import packet
            ack=packet(4,10,0,0,1,b'\0',flags=0x80)
            text='测试记录\nLog: CmdAndAck:\nCMD: '+generated+'\nACK: '+ack.hex(' ')+' ####\n'
            log=root/'history.log';log.write_bytes(text.encode('gb18030'))
            history=analyze_capture(log)
            # Exercise the frozen capture pipeline with a synthetic receiver.
            # This never constructs PassiveVisionUsbTransport or opens USB.
            from vision_usb_passive import capture_passive
            class SyntheticClock:
                value=0
                def __call__(self):return self.value
            clock=SyntheticClock()
            synthetic_sensor=bytes([0,160,0,4,84,0,0,0,0,67,66,65,13,12,1,7,49,50,51,52])
            synthetic_frame=packet(0x12,0x2a,900,0x24,0x26,synthetic_sensor,flags=0)
            class SyntheticReceiver:
                attempts=0;timeouts=0;closed=False
                evidence={'synthetic':True,'no_usb_opened':True}
                def read(self):
                    clock.value+=1;self.attempts+=1
                    if self.attempts==1:return synthetic_frame
                    self.timeouts+=1;return b''
                def close(self):self.closed=True
            receiver=SyntheticReceiver();passive_progress=[]
            passive=capture_passive(root/'passive.bin','01.00.1100',transport_factory=lambda:receiver,
                clock=clock,progress=passive_progress.append)
            passive_frames=analyze_capture(root/'passive.bin','binary')
            vision_report={'test_data':'synthetic; not the user calibration package',
                'inventory_files':inventory['file_count'],'md5_state':inventory['integrity']['state'],
                'compatibility':LocalCalibrationProvider().compatibility(inventory,None).state,
                'identity':UnavailableIdentification().identify().state,
                'write_enabled':False,'usb_enabled':False,
                'framing_valid':decode_bytes(bytes.fromhex(generated))['valid_frames']==1,
                'historical_reader':{'format':history['format'],'encoding':history['encoding'],
                    'valid_frames':history['valid_frames'],'issues':history['issue_count']},
                'passive_capture_synthetic_test':{'state':passive['state'],'bytes':passive['received_bytes'],
                    'valid_frames':passive_frames['valid_frames'],
                    'decoded_sensor_records':passive_frames['perception_records']['counts'].get('decoded',0),
                    'receiver_closed':receiver.closed,'protocol_commands_sent':passive['protocol_commands_sent'],
                    'last_percent':passive_progress[-1]['percent'],'real_usb_opened':False}}
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
        if '--validate-vision-log-folder' in sys.argv:
            from collections import Counter
            directory=Path(sys.argv[sys.argv.index('--validate-vision-log-folder')+1])
            counts=Counter();encodings=Counter();associations=Counter();perception=Counter();ack_fingerprints=set();complete=True
            for path in sorted(directory.iterdir()):
                if not path.is_file() or path.suffix.lower()!='.log':continue
                result=analyze_capture(path);counts['files']+=1;counts['valid_frames']+=result['valid_frames'];counts['frame_issues']+=result['issue_count']
                encodings[result.get('encoding')]+=1
                counts['historical_sensor_labels']+=len(result.get('historical_sensors',{}).get('observations_preview',[]))
                counts['labeled_cmd']+=result.get('historical_traffic',{}).get('record_counts',{}).get('CMD',0)
                counts['labeled_ack']+=result.get('historical_traffic',{}).get('record_counts',{}).get('ACK',0)
                associations.update(result.get('historical_traffic',{}).get('association_counts',{}))
                perception.update(result.get('perception_records',{}).get('counts',{}))
                complete=complete and result['valid_frames']<=result['preview_limit']
                for frame in result['frames_preview']:
                    if frame.get('record_label')=='ACK':ack_fingerprints.add(frame['frame_sha256'])
            report['provided_log_corpus']={'counts':dict(counts),'encodings':dict(encodings),
                'association_counts':dict(associations),'perception_records':dict(perception),
                'distinct_labeled_ack':len(ack_fingerprints) if complete else None,
                'hardware_tested':False,'usb_operations':0}
        if '--smoke-test-probe' in sys.argv:
            from vision_services import probe_server
            # Explicit CLI validation against loopback only, never historical DJI servers.
            report['loopback_probe_worker']=probe_server('https://127.0.0.1:1',5)
        if sys.platform == 'win32':
            import usb.backend.libusb1
            import usb.backend.libusb0
            native = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'libusb-1.0.dll'
            report['usb_backend_cargado'] = usb.backend.libusb1.get_backend(find_library=lambda name: str(native)) is not None
            legacy=Path(getattr(sys,'_MEIPASS',Path(__file__).parent/'native'))/'libusb0.dll'
            report['libusb0_backend_cargado']=usb.backend.libusb0.get_backend(find_library=lambda name:str(legacy)) is not None
        app.close_window()
        path = Path(sys.argv[sys.argv.index('--smoke-test')+1])
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    app.mainloop()

if __name__ == '__main__':
    main()
