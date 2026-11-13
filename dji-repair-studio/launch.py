"""One main window. --smoke-test validates startup without opening a drone."""
import json
import sys
import tkinter as tk
from pathlib import Path

def main():
    if '--usb-inventory-worker' in sys.argv:
        from vision_windows_pnp import inventory_worker
        raise SystemExit(inventory_worker(sys.argv[sys.argv.index('--usb-inventory-worker')+1]))
    if '--process-supervisor-worker' in sys.argv:
        import time
        path=Path(sys.argv[sys.argv.index('--process-supervisor-worker')+1])
        path.write_text('own supervisor self-test; no DJI or USB',encoding='utf-8')
        time.sleep(30)
        return
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
            from vision_image_receiver import TOPICS,PGM_HEADER
            from vision_images import validate_frames
            image_rows=[]
            for topic,name in TOPICS.items():
                image=root/name;image.write_bytes(PGM_HEADER+bytes([93])*307200)
                image_rows.append({'topic':topic,'file':name,'sha256':hashlib.sha256(image.read_bytes()).hexdigest()})
            checked=validate_frames(root,{'frames':image_rows})
            app.vision.apply_report('images',{'state':'confirmado','detail':'Autoprueba sintética; no son imágenes del dron.',
                'frames':[{**row,'image_path':str(root/row['file'])} for row in checked]})
            app.update_idletasks()
            image_test={'validated_files':len(checked),'ui_previews':len(app.vision.image_references),
                'preview_sizes':[[p.width(),p.height()] for p in app.vision.image_references],
                'real_usb_opened':False,'dji_code_loaded':False,'calibration_performed':False}
            vision_report={'test_data':'synthetic; not the user calibration package',
                'image_preview_synthetic_test':image_test,
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
            # Explicit Air 3 test data; no Windows queries or sensor commands.
            from vision_usb_inventory import collect_usb_profile
            app.model.set('Air 3');app.update()
            synthetic_pnp={'schema':1,'source':'windows_pnp_present','devices':[{
                'instance_id':'USB\\VID_2CA3&PID_0020\\SYNTHETIC','friendly_name':'Synthetic Air 3',
                'bus_product':'DJI Air 3-SYNTHETIC','parent':'SYNTHETIC_PARENT','service':'usbccgp',
                'hardware_ids':['USB\\VID_2CA3&PID_0020'],'problem_code':0,'status':'OK'}]}
            pnp=collect_usb_profile(root/'air3-metadata.zip','Air 3',app.vision.firmware.get(),
                collector=lambda **unused:synthetic_pnp)
            app.vision.apply_report('usb_profile',pnp)
            app.update()
            from studio_app import MINI4_ACTIVE_ACTIONS
            disabled=[action for button,action in zip(app.operation_buttons,app.operation_actions)
                if action in MINI4_ACTIVE_ACTIONS and str(button['state'])=='disabled']
            vision_report['air3_metadata_synthetic_test']={'model':app.model.get(),
                'firmware_declared':app.vision.firmware.get(),'ui_rows':len(app.vision.usb_nodes.get_children()),
                'mini4_actions_blocked':len(disabled),'service_commands_sent':pnp['service_commands_sent'],
                'endpoints_verified':pnp['usb_endpoints_verified'],'calibration_available':pnp['calibration_available'],
                'real_pnp_queries':0,'real_usb_opened':False,'support_bundle':Path(pnp['support_bundle']).is_file()}
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
            # Launch only our helper's pure self-test, never its DJI adapter.
            import subprocess
            from vision_images import receiver_path
            helper=receiver_path()
            report['receiver32_packaged']={'x86_header_validated':True,
                'sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'startup_tested':False}
            from windows_job import start_hidden_process
            import time
            with tempfile.TemporaryDirectory(prefix='dji-supervisor-test-') as folder:
                marker=Path(folder)/'ready.txt'
                command=[sys.executable]
                if not getattr(sys,'frozen',False):command.append(str(Path(__file__).resolve()))
                worker=start_hidden_process(command+['--process-supervisor-worker',str(marker)],folder)
                try:
                    deadline=time.monotonic()+10
                    while not marker.is_file() and worker.poll() is None and time.monotonic()<deadline:
                        time.sleep(.05)
                    ready=marker.is_file()
                    worker.terminate();code=worker.wait(timeout=3)
                    if not ready or code==0:raise RuntimeError('Falló la autoprueba del supervisor de procesos.')
                    report['windows_job_supervisor_test']={'worker_started':True,'child_tree_terminated':True,
                        'real_usb_opened':False,'dji_code_loaded':False}
                finally:
                    worker.close()
            from vision_windows_pnp import windows_inventory_api, native_inventory, DEVPROPKEY
            windows_inventory_api()
            class SyntheticInventory(SyntheticParent):
                ids = 'USB\\VID_2CA3&PID_0020\\SYNTHETIC\0\0'
                def CM_Get_Device_ID_List_SizeW(self, out, enumerator, flags):
                    assert enumerator == 'USB' and flags == 0x101
                    ctypes.cast(out, ctypes.POINTER(ctypes.c_uint32))[0] = len(self.ids)
                    return 0
                def CM_Get_Device_ID_ListW(self, enumerator, out, size, flags):
                    assert enumerator == 'USB' and flags == 0x101
                    for i, char in enumerate(self.ids): out[i] = char
                    return 0
                def CM_Get_DevNode_PropertyW(self, node, key, kind, out, size, flags):
                    key = ctypes.cast(key, ctypes.POINTER(DEVPROPKEY)).contents
                    bus = key.fmtid.data1 == 0x540b947e
                    value = 'DJI Air 3-SYNTHETIC' if bus else {14:'Synthetic fixture',6:'usbccgp',3:'USB\\VID_2CA3&PID_0020\0'}[key.pid]
                    data = (value+'\0').encode('utf-16-le')
                    ctypes.cast(kind,ctypes.POINTER(ctypes.c_uint32))[0] = 0x2012 if not bus and key.pid==3 else 0x12
                    ctypes.cast(size,ctypes.POINTER(ctypes.c_uint32))[0] = len(data)
                    ctypes.memmove(out, data, len(data)); return 0
                def CM_Get_DevNode_Status(self, status, problem, node, flags):
                    ctypes.cast(status,ctypes.POINTER(ctypes.c_uint32))[0] = 0x2000
                    ctypes.cast(problem,ctypes.POINTER(ctypes.c_uint32))[0] = 0
                    return 0
            synthetic_native = native_inventory(api_factory=SyntheticInventory)
            assert synthetic_native['collection_complete'] and not synthetic_native['property_errors']
            synthetic_row = synthetic_native['devices'][0]
            assert synthetic_row['hardware_ids'] == ['USB\\VID_2CA3&PID_0020']
            assert synthetic_row['bus_product'] == 'DJI Air 3-SYNTHETIC'
            report['native_pnp_abi_synthetic_test'] = {'wchar_bytes':ctypes.sizeof(ctypes.c_wchar),
                'device_count':len(synthetic_native['devices']), 'hardware_id_count':len(synthetic_row['hardware_ids']),
                'collection_complete':True, 'real_pnp_queries':0}
            from vision_usb_descriptors import collect_descriptors
            class SyntheticDescriptorList(list): pass
            descriptor_interface=SyntheticDescriptorList([
                SimpleNamespace(bEndpointAddress=4,bmAttributes=2,wMaxPacketSize=512,bInterval=0),
                SimpleNamespace(bEndpointAddress=0x85,bmAttributes=2,wMaxPacketSize=512,bInterval=0)])
            for key,value in {'bInterfaceNumber':3,'bAlternateSetting':0,'bInterfaceClass':255,
                              'bInterfaceSubClass':0x43,'bInterfaceProtocol':1,'bNumEndpoints':2}.items():
                setattr(descriptor_interface,key,value)
            descriptor_cfg=SyntheticDescriptorList([descriptor_interface])
            for key,value in {'bConfigurationValue':1,'wTotalLength':32,'bNumInterfaces':1,'bmAttributes':128,'bMaxPower':250}.items():
                setattr(descriptor_cfg,key,value)
            class SyntheticDescriptorDevice:
                idVendor=0x2ca3;idProduct=0x0020;bcdUSB=0x200;bcdDevice=0x504
                bDeviceClass=0;bDeviceSubClass=0;bDeviceProtocol=0;bMaxPacketSize0=64;bNumConfigurations=1
                _ctx=SimpleNamespace(dev=SimpleNamespace(filename=(ALIAS_PREFIX+'0003--0x2ca3-0x0020').encode()))
                def __getitem__(self,index):return descriptor_cfg
            parent_id='USB\\VID_2CA3&PID_0020\\SYNTHETIC'
            child_id='USB\\VID_2CA3&PID_0020&MI_03\\SYNTHETIC_CHILD'
            rows=[{'instance_id':parent_id},{'instance_id':child_id,'parent':parent_id}]
            descriptors=collect_descriptors(rows,enumerate_devices=lambda:[SyntheticDescriptorDevice()],
                probe=lambda alias:['USB\\VID_2CA3&PID_0020&MI_03'],probe_instance=lambda alias:child_id)
            assert descriptors['state']=='confirmado'
            aliases=descriptors['aliases']; assert aliases[0]['pnp_instance_matches']
            assert [e['bEndpointAddress'] for e in aliases[0]['configurations'][0]['interfaces'][0]['endpoints']]==[4,0x85]
            report['usb_descriptor_synthetic_test']={'aliases':1,'interfaces':1,'endpoints':2,
                'pnp_session_matched':True,'real_usb_operations':0,'transport_validated':False,'calibration_performed':False}
            from vision_usb_inventory import query_windows_pnp
            native_pnp = query_windows_pnp()
            assert native_pnp['collector_backend'] == 'cfgmgr32'
            assert 'worker_exit_code' in native_pnp
            report['native_pnp_worker_test'] = {
                'backend': 'cfgmgr32', 'worker_exit_code': native_pnp['worker_exit_code'],
                'collection_complete': native_pnp['collection_complete'],
                'stage': native_pnp['stage'], 'device_count': len(native_pnp['devices']),
                'error': native_pnp.get('error'), 'dji_code_loaded': False,
                'drone_service_commands': 0, 'real_dji_hardware_tested': False}
            if '--smoke-test-receiver' in sys.argv:
                with tempfile.TemporaryDirectory(prefix='dji-receiver-smoke-') as folder:
                    destination=Path(folder)/'self-test.json'
                    subprocess.run([str(helper),'--self-test',str(destination)],
                        check=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
                    report['receiver32_self_test']=json.loads(destination.read_text(encoding='utf-8'))
                    report['receiver32_packaged']['startup_tested']=True
        from gimbal_profiles import FLIP
        from studio_app import USB_PROFILE_ACTION
        app.model.set(FLIP);app.update()
        assert app.firmware.get()=='01.00.1500' and not app.prepared.get()
        assert app.tabs.select()==str(app.pages['Calibración'])
        with tempfile.TemporaryDirectory(prefix='dji-flip-smoke-') as folder:
            raw={'schema':1,'source':'windows_pnp_present','devices':[{
                'instance_id':'USB\\VID_2CA3&PID_0020\\SYNTHETIC','friendly_name':'Synthetic Flip',
                'status':'SYNTHETIC','bus_product':'DJI Flip-SYNTHETIC','parent':'SYNTHETIC_PARENT',
                'service':'usbccgp','hardware_ids':['USB\\VID_2CA3&PID_0020'],'problem_code':0}]}
            flip_zip=Path(folder)/'flip.zip'
            flip=collect_usb_profile(flip_zip,FLIP,'01.00.1500',collector=lambda **kw:raw)
            app.flip_gimbal.apply_report(flip);app.update()
            app.after(150,app.quit);app.mainloop()
            assert app.model.get()==FLIP
            allowed={a for b,a in zip(app.operation_buttons,app.operation_actions) if str(b['state'])=='normal'}
            assert allowed=={USB_PROFILE_ACTION,'Identificar','JointCoarse','LinearHall','Analizar','Generar','Convertir'}
            with ZipFile(flip_zip) as archive:
                stored=json.loads(archive.read('DJI-REPAIR-informe.json'))
            assert 'gimbal' in stored and 'vision' not in stored
            report['flip_gimbal_project_test']={'model':app.model.get(),'firmware_declared':app.firmware.get(),
                'gimbal_workspace_visible':True,'experimental_calibration_available':True,'ui_rows':len(app.flip_gimbal.nodes.get_children()),
                'gimbal_scoped_zip':True,'calibration_available':False,'factory_commands_sent':0,
                'service_commands_sent':0,'real_usb_operations':0,'model_preserved_in_event_loop':True}
        from flip_gimbal_query import query_flip_modules,FlipVersionTransport
        with tempfile.TemporaryDirectory(prefix='dji-flip-query-smoke-') as folder:
            qroot=Path(folder);parent_id='USB\\VID_2CA3&PID_0020\\SYNTHETIC'
            child_id='USB\\VID_2CA3&PID_0020&MI_04\\SYNTHETIC_CHILD'
            ep_ref=[{'bEndpointAddress':4,'bmAttributes':2,'wMaxPacketSize':512},
                    {'bEndpointAddress':0x85,'bmAttributes':2,'wMaxPacketSize':512}]
            iref={'bInterfaceNumber':4,'bAlternateSetting':0,'bInterfaceClass':255,'bInterfaceSubClass':0x43,
                  'bInterfaceProtocol':1,'bNumEndpoints':2,'endpoints':ep_ref}
            rows=[dict(raw['devices'][0]),dict(raw['devices'][0])]
            rows[0].update(instance_id=parent_id,bus_product='DJI-SYNTHETIC')
            rows[1].update(instance_id=child_id,parent=parent_id,bus_product='BULK Interface')
            profile={'modelo_declarado':FLIP,'firmware_declarado':'01.00.1500','gimbal':{'usb_profile':{
                'devices':rows,'collection_complete':True,'descriptor_inventory':{'state':'confirmado','errors':[],
                'aliases':[{'pnp_interface_number':4,'complete':True,'pnp_instance_matches':True,
                'configurations':[{'bConfigurationValue':1,'interfaces':[iref]}]}]}}}}
            reference_path=qroot/'profile.zip'
            with ZipFile(reference_path,'x') as z:z.writestr('DJI-REPAIR-informe.json',json.dumps(profile))
            qclock=SyntheticClock();pending=[];released=[]
            def out_write(req,timeout):
                assert timeout==500
                payload=b'\0\0'+b'SYNTHETIC-MODULE'.ljust(16,b'\0')+bytes(4)+(0x04000007).to_bytes(4,'little')
                pending.append(packet(req[5],10,int.from_bytes(req[6:8],'little'),0,1,payload,flags=128))
                return len(req)
            def in_read(size,timeout):
                assert size==512 and timeout==200
                qclock.value+=.25
                return pending.pop(0) if pending else b''
            class QueryList(list):pass
            out_ep=SimpleNamespace(bEndpointAddress=4,bmAttributes=2,wMaxPacketSize=512,write=out_write)
            in_ep=SimpleNamespace(bEndpointAddress=0x85,bmAttributes=2,wMaxPacketSize=512,read=in_read)
            iface=QueryList([out_ep,in_ep])
            for key,val in iref.items():
                if key!='endpoints':setattr(iface,key,val)
            cfg=QueryList([iface]);cfg.bConfigurationValue=1
            dev=SimpleNamespace(get_active_configuration=lambda:cfg)
            util=SimpleNamespace(claim_interface=lambda d,i:None,release_interface=lambda d,i:released.append(i),dispose_resources=lambda d:None)
            def transport_factory(ref):
                return FlipVersionTransport(ref,enumerator=lambda:[dev],selector=lambda ds:(ds[0],{'synthetic':True}),
                    parent_reader=lambda d:ref,util=util)
            events=[]
            query=query_flip_modules(qroot/'query.zip',reference_path,'01.00.1500',transport_factory=transport_factory,
                clock=qclock,progress=events.append)
            assert query['state']=='confirmado' and released==[4]
            assert query['rx_bytes']==78 and query['bulk_out_bytes_confirmed']==26
            assert query['factory_commands_sent']==query['gimbal_calibration_commands_sent']==0
            app.flip_gimbal.apply_module_report(query);app.update()
            assert len(app.flip_gimbal.nodes.get_children())==2
            with ZipFile(qroot/'query.zip') as z:
                assert z.read('query.bin') and 'module_query' in json.loads(z.read('DJI-REPAIR-informe.json'))['gimbal']
            report['flip_module_query_synthetic_test']={'modules':2,'rx_bytes':78,'bulk_out_bytes':26,'last_percent':events[-1]['percent'],
                'released_interface':4,'gimbal_scoped_zip':True,'factory_commands':0,'calibration_commands':0,
                'calibration_available':False,'real_usb_operations':0,'ui_rows':2}
        from flip_gimbal_calibration import run_flip_calibration,FlipCalibrationTransport
        # Standalone synthetic workshop trace, not a real Flip calibration.
        with tempfile.TemporaryDirectory(prefix='dji-flip-cal-smoke-') as folder:
            croot=Path(folder);reference_path=croot/'modules.zip'
            # Recreate the preceding synthetic module report (its temporary folder has closed).
            with ZipFile(reference_path,'x') as z:
                z.writestr('DJI-REPAIR-informe.json',json.dumps({'modelo_declarado':FLIP,'firmware_declarado':'01.00.1500','gimbal':{'module_query':query}}))
                z.writestr('modules.bin',bytes.fromhex(''.join(p['hex'].replace(' ','') for p in query['packet_audit'] if p['direccion']=='RX')))
            pending.clear();released.clear()
            def calibration_write(req,timeout):
                if req[9:11]==b'\0\1':return out_write(req,timeout)
                assert req[9:12]==b'\4\10\1'
                seq=int.from_bytes(req[6:8],'little')
                pending.append(packet(4,10,seq,4,8,b'\1',flags=128)+
                    packet(4,10,700,4,0x30,b'\x52\1',flags=0)+packet(4,10,701,4,0x30,b'\x64\0',flags=0))
                return len(req)
            out_ep.write=calibration_write
            def calibration_factory(ref,routine):
                return FlipCalibrationTransport(ref,routine,enumerator=lambda:[dev],selector=lambda ds:(ds[0],{'synthetic':True}),
                    parent_reader=lambda d:{k:ref[k] for k in ('product','child_instance_sha256','parent_instance_sha256')},util=util)
            events=[]
            trial=run_flip_calibration(croot/'joint.zip',reference_path,'01.00.1500','JointCoarse',
                transport_factory=calibration_factory,clock=qclock,progress=events.append,max_seconds=2)
            assert trial['state']=='equipo_informa_fin' and released==[4]
            assert trial['bulk_out_bytes_complete']==40 and trial['calibration_requests_attempted']==1
            assert trial['factory_commands_sent']==0 and trial['calibration_performed'] is None
            app.flip_gimbal.apply_calibration_report(trial);app.update()
            with ZipFile(croot/'joint.zip') as z:assert 'calibration_probe' in json.loads(z.read('DJI-REPAIR-informe.json'))['gimbal']
            report['flip_calibration_synthetic_test']={'routine':'JointCoarse','single_calibration_request':True,
                'bulk_out_bytes':40,'last_percent':events[-1]['percent'],'device_reported_completion':True,
                'factory_commands':0,'fixed_imu_coefficients_written':False,'released_interface':4,
                'gimbal_scoped_zip':True,'ui_rows':len(app.flip_gimbal.nodes.get_children()),'real_usb_operations':0,
                'physical_flip_tested':False}
        app.close_window()
        path = Path(sys.argv[sys.argv.index('--smoke-test')+1])
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    app.mainloop()

if __name__ == '__main__':
    main()
