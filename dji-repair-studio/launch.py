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
            from vision_usb_legacy import select_mi04,ALIAS_PREFIX
            from vision_support_bundle import write_support_bundle
            from types import SimpleNamespace
            from zipfile import ZipFile
            aliases=[SimpleNamespace(_ctx=SimpleNamespace(dev=SimpleNamespace(
                filename=(ALIAS_PREFIX+f'{index:04d}--0x2ca3-0x0020').encode()))) for index in range(1,7)]
            mapping={1:2,2:3,3:5,4:6,5:7,6:4}
            selected,selection=select_mi04(aliases,probe=lambda path:[f'USB\\VID_2CA3&PID_0020&MI_{mapping[int(path[-4:])]:02X}'])
            synthetic_bundle=write_support_bundle(root/'passive.bin',{'test_data':'synthetic','usb_capture':passive})
            with ZipFile(synthetic_bundle) as z:
                bundle_ok=z.testzip() is None and z.read('passive.bin')==synthetic_frame and json.loads(z.read('DJI-REPAIR-informe.json'))['test_data']=='synthetic'
            from vision_sensor_query import query_sensor_serials,sn_request
            sn_clock=SyntheticClock()
            class SyntheticSnReceiver:
                evidence={'synthetic':True,'no_usb_opened':True}
                closed=False;timeouts=0
                def __init__(self):self.tx_audit=[];self.pending=[]
                def read(self):
                    sn_clock.value+=.2
                    if self.pending:return self.pending.pop(0)
                    self.timeouts+=1;return b''
                def send_sn_query(self,selector,sequence):
                    request=sn_request(selector,sequence)
                    self.tx_audit.append({'selector':selector,'sequence':sequence,'hex':request.hex(' '),
                        'requested_bytes':28,'transferred_bytes':28,'status':'transferred'})
                    body=bytearray(synthetic_sensor);body[3]=selector
                    self.pending.append(packet(0x12,0x2a,900,0x24,0x26,body,flags=0))
                def close(self):self.closed=True
            sn_receiver=SyntheticSnReceiver();sn_progress=[]
            sn=query_sensor_serials(root/'sn.bin','01.00.1100',transport_factory=lambda:sn_receiver,
                clock=sn_clock,sequence_seed=10,progress=sn_progress.append)
            app.vision.apply_report('identity',sn)
            sn_bundle=write_support_bundle(root/'sn.bin',{'test_data':'synthetic','vision':{'identity':sn}})
            with ZipFile(sn_bundle) as z:
                sn_bundle_ok=z.testzip() is None and len(json.loads(z.read('DJI-REPAIR-informe.json'))['vision']['identity']['tx_audit'])==4
            from vision_hms_query import probe_hms,hms_subscription_request
            hms_clock=SyntheticClock()
            class SyntheticHmsReceiver:
                evidence={'synthetic':True,'no_usb_opened':True}
                closed=False;timeouts=0
                def __init__(self):self.tx_audit=[];self.pending=[]
                def subscribe_hms(self,sequence):
                    self.tx_audit.append({'hex':hms_subscription_request(sequence).hex(' '),'sequence':sequence,
                        'requested_bytes':14,'transferred_bytes':14,'status':'transferred'})
                    self.pending=[packet(0x1d,0x0a,sequence,0x21,5,b'\0',flags=0x80),
                        packet(0x1d,0x0a,900,0x21,6,bytes.fromhex('00 00 80 78 56 34 12 02 03'),flags=0),
                        packet(0x1d,0x0a,901,0x21,6,bytes.fromhex('00 01 80'),flags=0),
                        packet(0x1d,0x0a,902,0x21,8,b'\0\0\x80\x01\0\x14'+bytes.fromhex('80 03 51 1a')+bytes(16),flags=0)]
                def read(self):
                    hms_clock.value+=.2
                    if self.pending:return self.pending.pop(0)
                    self.timeouts+=1;return b''
                def close(self):self.closed=True
            hms_receiver=SyntheticHmsReceiver();hms_progress=[]
            hms_report=probe_hms(root/'hms.bin','01.00.1100',transport_factory=lambda:hms_receiver,
                clock=hms_clock,sequence_seed=10,progress=hms_progress.append)
            app.vision.apply_report('diagnostic',hms_report)
            hms_bundle=write_support_bundle(root/'hms.bin',{'test_data':'synthetic','vision':{'diagnostic':hms_report}})
            with ZipFile(hms_bundle) as z:
                hms_bundle_ok=z.testzip() is None and json.loads(z.read('DJI-REPAIR-informe.json'))['vision']['diagnostic']['hms']['complete_cycles']==3
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
                    'last_percent':passive_progress[-1]['percent'],'real_usb_opened':False},
                'legacy_alias_selection_synthetic_test':{'aliases':6,'selected_index':selection['selected_alias_index'],
                    'selected_mi':selection['selected_mi'],'correct_object':selected is aliases[-1],
                    'real_metadata_ioctls_executed':0},'support_bundle_synthetic_test':bundle_ok,
                'sn_query_synthetic_test':{'state':sn['state'],'rx_bytes':sn['received_bytes'],
                    'tx_bytes':sn['bulk_out_bytes_confirmed'],'queries_sent':sn['protocol_commands_sent'],
                    'rows_with_serial':sum(bool(q['serials_observed']) for q in sn['queries']),
                    'identity_confirmed':sn['current_device_confirmed'],'ui_rows':len(app.vision.current_sensor_records.get_children()),
                    'configuration_writes':sn['device_configuration_writes'],'factory_commands':sn['factory_commands_sent'],
                    'receiver_closed':sn_receiver.closed,'last_percent':sn_progress[-1]['percent'],
                    'support_bundle':sn_bundle_ok,'real_usb_opened':False},
                'hms_probe_synthetic_test':{'state':hms_report['state'],'rx_bytes':hms_report['received_bytes'],
                    'tx_bytes':hms_report['bulk_out_bytes_confirmed'],'requests_sent':hms_report['protocol_commands_sent'],
                    'complete_reference_cycles':hms_report['hms']['complete_cycles'],
                    'distinct_records':hms_report['hms']['distinct_records_shown'],'ui_rows':len(app.vision.hms_records.get_children()),
                    'health':hms_report['device_health'],'calibration':hms_report['calibration_status'],
                    'reset_all_commands':hms_report['global_unsubscribe_commands_sent'],
                    'receiver_closed':hms_receiver.closed,'last_percent':hms_progress[-1]['percent'],
                    'support_bundle':hms_bundle_ok,'real_usb_opened':False}}
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
                    if (frame.get('record_label'),frame['command_set_raw'],frame['command_id_raw'])==('CMD','24','26'):
                        counts['sn_query_requests']+=1
                        if any(hashlib.sha256(sn_request(s,frame['sequence_raw'])).hexdigest()==frame['frame_sha256'] for s in (4,8,64,128)):
                            counts['sn_queries_byte_matched']+=1
            report['provided_log_corpus']={'counts':dict(counts),'encodings':dict(encodings),
                'association_counts':dict(associations),'perception_records':dict(perception),
                'distinct_labeled_ack':len(ack_fingerprints) if complete else None,
                'hardware_tested':False,'usb_operations':0}
        if '--smoke-test-probe' in sys.argv:
            from vision_services import probe_server
            # Explicit CLI validation against loopback only, never historical DJI servers.
            report['loopback_probe_worker']=probe_server('https://127.0.0.1:1',5)
        if '--validate-hms-capture-folder' in sys.argv:
            directory=Path(sys.argv[sys.argv.index('--validate-hms-capture-folder')+1])
            files=sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower()=='.bin')
            if not 1<=len(files)<=8:raise ValueError('El corpus HMS debe contener 1–8 archivos binarios.')
            summaries=[]
            for path in files:
                if path.stat().st_size>1024**2:raise ValueError('Captura HMS de referencia demasiado grande.')
                result=analyze_capture(path,'binary');hms=result['hms']
                summaries.append({'bytes':result['source_bytes'],'valid_frames':result['valid_frames'],
                    'crc_issues':result['issue_count'],'family_counts':hms['family_counts'],
                    'opaque_records':hms['opaque_record_observations'],
                    'reference_vision_codes':len({r['alarm_code_raw'] for r in hms['records_preview']
                        if r['alarm_code_raw'] in ('0x1A510380','0x1A510382','0x1A510384','0x1A510385')}),
                    'health':hms['device_health'],'activity':hms['alarm_activity']})
            report['provided_hms_corpus']={'files':len(files),'captures':summaries,'real_usb_operations':0}
        if sys.platform == 'win32':
            import usb.backend.libusb1
            import usb.backend.libusb0
            native = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'libusb-1.0.dll'
            report['usb_backend_cargado'] = usb.backend.libusb1.get_backend(find_library=lambda name: str(native)) is not None
            legacy=Path(getattr(sys,'_MEIPASS',Path(__file__).parent/'native'))/'libusb0.dll'
            report['libusb0_backend_cargado']=usb.backend.libusb0.get_backend(find_library=lambda name:str(legacy)) is not None
            from vision_usb_legacy import windows_kernel32
            from vision_usb_parent import windows_cfgmgr32,read_parent_product
            import ctypes
            kernel=windows_kernel32()
            report['windows_metadata_api_loaded']=all(getattr(kernel,name,None) is not None for name in ('CreateFileW','DeviceIoControl','CloseHandle'))
            cm=windows_cfgmgr32()
            report['windows_parent_api_loaded']=all(getattr(cm,name,None) is not None for name in (
                'CM_Locate_DevNodeW','CM_Get_Parent','CM_Get_Device_IDW','CM_Get_DevNode_PropertyW'))
            # Synthetic native-width buffers exercise the frozen Windows build;
            # these methods never call cfgmgr32 or open a real device.
            class SyntheticParent:
                def CM_Locate_DevNodeW(self,out,instance,flags):
                    ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]=1;return 0
                def CM_Get_Parent(self,out,child,flags):
                    ctypes.cast(out,ctypes.POINTER(ctypes.c_uint32))[0]=2;return 0
                def CM_Get_Device_IDW(self,parent,out,size,flags):
                    out.value='USB\\VID_2CA3&PID_0020\\SYNTHETIC';return 0
                def CM_Get_DevNode_PropertyW(self,parent,key,kind,out,size,flags):
                    raw='Mini 4 Pro-SYNTHETIC\0'.encode('utf-16-le')
                    ctypes.cast(kind,ctypes.POINTER(ctypes.c_uint32))[0]=0x12
                    ctypes.cast(size,ctypes.POINTER(ctypes.c_uint32))[0]=len(raw)
                    ctypes.memmove(out,raw,len(raw));return 0
            parent=read_parent_product('USB\\VID_2CA3&PID_0020&MI_04\\SYNTHETIC',SyntheticParent())
            report['windows_parent_synthetic_test']={'product':parent['product'],
                'metadata_only':parent['metadata_only'],'real_pnp_queries':0}
        app.close_window()
        path = Path(sys.argv[sys.argv.index('--smoke-test')+1])
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    app.mainloop()

if __name__ == '__main__':
    main()
