import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from studio_service import packet
from vision_hms import parse_hms_frame,HmsTracker
from vision_hms_query import hms_subscription_request,HmsTransport,probe_hms
import test_passive_usb as passive_fixtures

def record(code=0x12345678,index=2,level=3):
    return code.to_bytes(4,'little')+bytes([index,level])
def hms(cycle=0,index=0,end=True,records=(),sender=0x1d,receiver=0x0a,version=0,flags=0):
    payload=bytes([version,cycle,index|(128 if end else 0)])+b''.join(records)
    return packet(sender,receiver,900,0x21,0x06,payload,flags=flags)
def ack(sequence=10,code=0,flags=0x80):
    return packet(0x1d,0x0a,sequence,0x21,0x05,bytes([code]),flags=flags)

class HmsFormatTests(unittest.TestCase):
    def test_record_fields_are_raw_and_mapping_remains_unvalidated(self):
        p=parse_hms_frame(hms(cycle=7,records=[record()]))
        self.assertEqual(p['cycle_index'],7);self.assertEqual(p['packet_index'],0);self.assertTrue(p['end_flag'])
        r=p['records'][0];self.assertEqual(r['alarm_code_raw'],'0x12345678')
        self.assertEqual((r['sensor_index_raw'],r['report_level_raw']),(2,3))
        self.assertFalse(r['vision_association_confirmed']);self.assertFalse(p['mini4_layout_validated'])
        self.assertEqual(r['device_health'],'desconocido')
    def test_empty_cycle_is_not_a_healthy_diagnosis(self):
        tracker=HmsTracker();tracker.observe(hms())
        r=tracker.result();self.assertEqual(r['complete_cycles'],1);self.assertEqual(r['records_preview'],[])
        self.assertEqual(r['device_health'],'desconocido');self.assertEqual(r['calibration_status'],'desconocido')
    def test_unknown_version_size_flags_crc_or_command_are_rejected(self):
        bad_crc=bytearray(hms());bad_crc[-1]^=1
        frames=[bytes(bad_crc),hms(version=1),hms(flags=0x80),
            packet(0x1d,0x0a,1,0x21,6,b'\0\0',flags=0),
            packet(0x1d,0x0a,1,0x21,6,b'\0\0\x80x',flags=0),
            packet(0x1d,0x0a,1,0x21,5,b'\0\0\x80',flags=0)]
        for f in frames:
            with self.subTest(frame=f.hex()),self.assertRaises(ValueError):parse_hms_frame(f)
    def test_low_bit_is_not_treated_as_end_flag(self):
        p=parse_hms_frame(hms(index=1,end=False))
        self.assertFalse(p['end_flag']);self.assertEqual(p['packet_index'],1)
        tracker=HmsTracker();tracker.observe(hms(index=1,end=False))
        self.assertEqual(tracker.result()['complete_cycles'],0)
    def test_unrecognized_level_is_preserved_without_severity_claim(self):
        p=parse_hms_frame(hms(records=[record(level=255)]))
        self.assertEqual(p['records'][0]['report_level_raw'],255)
        self.assertFalse(p['records'][0]['level_in_reference_range'])
    def test_contiguous_cycle_and_out_of_order_assembly(self):
        tracker=HmsTracker();tracker.observe(hms(index=1,records=[record()]))
        self.assertEqual(tracker.result()['complete_cycles'],0)
        tracker.observe(hms(index=0,end=False))
        r=tracker.result();self.assertEqual(r['complete_cycles'],1)
        self.assertTrue(r['records_preview'][0]['seen_in_complete_cycle'])
    def test_missing_part_never_completes_cycle(self):
        tracker=HmsTracker();tracker.observe(hms(index=0,end=False));tracker.observe(hms(index=2))
        self.assertEqual(tracker.result()['complete_cycles'],0);self.assertEqual(tracker.result()['incomplete_cycles'],1)
    def test_same_cycle_from_other_senders_or_recipients_does_not_fill_gaps(self):
        tracker=HmsTracker();tracker.observe(hms(index=0,end=False))
        tracker.observe(hms(index=1,sender=3));tracker.observe(hms(index=1,receiver=0x2a))
        self.assertEqual(tracker.result()['complete_cycles'],0)
    def test_duplicate_packets_do_not_inflate_records_or_cycles(self):
        tracker=HmsTracker();f=hms(records=[record()]);tracker.observe(f);tracker.observe(f)
        r=tracker.result();self.assertEqual(r['complete_cycles'],1);self.assertEqual(r['duplicate_packets'],1)
        self.assertEqual(r['record_observations'],1)
    def test_conflicting_packet_revokes_previously_completed_cycle(self):
        tracker=HmsTracker();tracker.observe(hms(records=[record()]))
        tracker.observe(hms(records=[record(code=0x11111111)]))
        r=tracker.result();self.assertEqual(r['complete_cycles'],0)
        self.assertFalse(r['records_preview'][0]['seen_in_complete_cycle'])
        self.assertFalse(r['cycles_preview'][0]['valid_reference_cycle'])
    def test_extra_packet_after_end_is_a_conflict(self):
        tracker=HmsTracker();tracker.observe(hms());tracker.observe(hms(index=1))
        self.assertEqual(tracker.result()['complete_cycles'],0)
        self.assertTrue(tracker.result()['issues_preview'])
    def test_parts_past_end_or_two_end_flags_never_complete(self):
        tracker=HmsTracker();tracker.observe(hms(index=2,end=False));tracker.observe(hms(index=1))
        tracker.observe(hms(index=0,end=False));self.assertEqual(tracker.result()['complete_cycles'],0)
    def test_records_are_aggregated_across_cycles_but_health_is_unknown(self):
        tracker=HmsTracker();tracker.observe(hms(cycle=0,records=[record()]));tracker.observe(hms(cycle=1,records=[record()]))
        r=tracker.result();self.assertEqual(r['complete_cycles'],2)
        self.assertEqual(r['distinct_records_shown'],1);self.assertEqual(r['records_preview'][0]['complete_cycle_observations'],2)
        self.assertEqual(r['state'],'desconocido')
    def test_abandoned_cycle_is_counted_and_not_joined_to_next(self):
        tracker=HmsTracker();tracker.observe(hms(cycle=255,end=False));tracker.observe(hms(cycle=0,index=1))
        self.assertEqual(tracker.result()['incomplete_cycles'],2);self.assertEqual(tracker.result()['complete_cycles'],0)
    def test_packet_record_source_limits_bound_memory(self):
        with patch('vision_hms.MAX_PACKETS',1):
            tracker=HmsTracker();tracker.observe(hms());tracker.observe(hms(cycle=1))
            self.assertTrue(tracker.result()['limits_reached']);self.assertEqual(tracker.result()['decoded_packets'],1)
        with patch('vision_hms.MAX_CYCLE_RECORDS',1):
            tracker=HmsTracker();tracker.observe(hms(records=[record(),record(code=1)]))
            self.assertEqual(tracker.result()['complete_cycles'],0);self.assertTrue(tracker.result()['limits_reached'])
        with patch('vision_hms.MAX_SOURCES',1):
            tracker=HmsTracker();tracker.observe(hms());tracker.observe(hms(sender=3))
            self.assertEqual(len(tracker.sources),1);self.assertTrue(tracker.result()['limits_reached'])
    def test_unknown_payload_stays_available_as_unknown(self):
        tracker=HmsTracker();tracker.observe(hms(version=9))
        r=tracker.result();self.assertEqual(r['unknown_packets'],1);self.assertEqual(r['complete_cycles'],0)
    def test_streaming_capture_analysis_includes_hms_without_usb(self):
        from vision_protocol import decode_bytes
        r=decode_bytes(hms(records=[record()])+hms(cycle=1))
        self.assertEqual(r['valid_frames'],2);self.assertEqual(r['hms']['complete_cycles'],2)
        self.assertEqual(r['hms']['device_health'],'desconocido')

class HmsTransportTests(unittest.TestCase):
    setUp=passive_fixtures.PassiveTransportTests.setUp
    def ready(self):
        out=self.device.cfg[0][0];out.write.side_effect=None;out.write.return_value=14
        return HmsTransport(),out
    def test_only_one_native_profile_subscription_no_reset_or_arbitrary_write(self):
        t,out=self.ready();request=t.subscribe_hms(10)
        self.assertEqual(request,packet(0x0a,0x1d,10,0x21,5,b'\x01',flags=0x40))
        self.assertFalse(hasattr(t,'write'));self.assertFalse(hasattr(t,'unsubscribe'))
        with self.assertRaises(ValueError):t.subscribe_hms(11)
        out.write.assert_called_once_with(request,timeout=500);t.close()
        for name in ('set_configuration','set_interface_altsetting','reset','detach_kernel_driver','ctrl_transfer','clear_halt','write'):
            getattr(self.device,name).assert_not_called()
    def test_bad_sequence_never_writes_and_closed_transport_is_rejected(self):
        t,out=self.ready()
        for value in (True,-1,65536,'10'):
            with self.assertRaises(ValueError):t.subscribe_hms(value)
        out.write.assert_not_called();t.close()
        with self.assertRaises(RuntimeError):t.subscribe_hms(1)
    def test_failed_write_records_uncertain_delivery_and_never_retries(self):
        for failure in (True,False):
            t,out=self.ready();out.write.side_effect=OSError('timeout') if failure else None
            out.write.return_value=7
            with self.assertRaises(OSError):t.subscribe_hms(10)
            self.assertNotEqual(t.tx_audit[0]['status'],'transferred')
            with self.assertRaises(ValueError):t.subscribe_hms(10)
            t.close()
    def test_wrong_product_cannot_send_any_subscription(self):
        self.product.return_value='Mavic 3'
        with self.assertRaises(RuntimeError):HmsTransport()
        self.device.cfg[0][0].write.assert_not_called()

class Clock:
    value=0
    def __call__(self):return self.value
class Receiver:
    def __init__(self,clock,chunks=(),on_send=None):
        self.clock=clock;self.chunks=list(chunks);self.tx_audit=[];self.timeouts=0;self.closed=False;self.on_send=on_send
        self.evidence={'synthetic':True,'interface':4}
    def subscribe_hms(self,sequence):
        request=hms_subscription_request(sequence)
        self.tx_audit.append({'hex':request.hex(' '),'sequence':sequence,'requested_bytes':14,'transferred_bytes':None,'status':'delivery_unknown'})
        if self.on_send:self.on_send()
        self.tx_audit[-1].update(transferred_bytes=14,status='transferred')
    def read(self):
        self.clock.value+=.2;item=self.chunks.pop(0) if self.chunks else b''
        if isinstance(item,Exception):raise item
        if not item:self.timeouts+=1
        return item
    def close(self):self.closed=True

class HmsProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'new.bin';self.clock=Clock();self.progress=[]
    def run_probe(self,chunks=(),on_send=None,**kwargs):
        self.receiver=Receiver(self.clock,chunks,on_send)
        return probe_hms(self.path,'01.00.1100',transport_factory=lambda:self.receiver,
            clock=self.clock,sequence_seed=10,progress=self.progress.append,**kwargs)
    def test_ack_and_records_are_received_without_inventing_vision_health(self):
        chunks=[ack(),hms(records=[record()]),hms(cycle=1)]
        r=self.run_probe(chunks)
        self.assertTrue(r['subscription_accepted_by_matching_ack']);self.assertTrue(r['probe_completed'])
        self.assertEqual(r['protocol_commands_sent'],1);self.assertEqual(r['bulk_out_bytes_confirmed'],14)
        self.assertEqual(self.path.read_bytes(),b''.join(chunks));self.assertEqual(r['hms']['complete_cycles'],2)
        self.assertEqual(r['hms']['distinct_records_shown'],1);self.assertEqual(r['state'],'desconocido')
        self.assertEqual(r['device_health'],'desconocido');self.assertEqual(r['global_unsubscribe_commands_sent'],0)
        self.assertTrue(self.receiver.closed);self.assertEqual(self.progress[-1]['percent'],100)
    def test_no_hms_data_is_unknown_not_healthy_or_faulty(self):
        r=self.run_probe();self.assertTrue(r['probe_completed']);self.assertEqual(r['received_bytes'],0)
        self.assertEqual(r['hms']['complete_cycles'],0);self.assertEqual(r['device_health'],'desconocido')
    def test_wrong_ack_sequence_is_observed_without_confirming_acceptance(self):
        r=self.run_probe([ack(sequence=11)])
        self.assertFalse(r['subscription_accepted_by_matching_ack']);self.assertTrue(r['probe_completed'])
    def test_matched_rejection_stops_immediately_and_keeps_code(self):
        r=self.run_probe([ack(code=7),hms()])
        self.assertEqual(r['state'],'error');self.assertEqual(r['stop_reason'],'suscripcion_rechazada')
        self.assertEqual(r['bulk_in_attempts'],1);self.assertEqual(r['subscription_ack_observations'][0]['return_code_raw'],7)
        self.assertLess(self.progress[-1]['percent'],100);self.assertTrue(self.receiver.closed)
    def test_other_recipient_data_are_preserved_but_not_assigned_to_this_client(self):
        f=hms(receiver=0x2a);r=self.run_probe([f])
        self.assertEqual(r['foreign_recipient_hms_packets'],1);self.assertEqual(r['hms']['packets_seen'],0)
        self.assertEqual(self.path.read_bytes(),f)
    def test_crc_failure_is_not_parsed_as_hms_and_raw_bytes_are_kept(self):
        f=bytearray(hms());f[-1]^=1;r=self.run_probe([bytes(f)])
        self.assertEqual(r['hms']['packets_seen'],0);self.assertEqual(self.path.read_bytes(),f)
    def test_fragmented_frame_and_incomplete_cycle_remain_distinct(self):
        f=hms(index=1);r=self.run_probe([f[:7],f[7:]])
        self.assertEqual(r['hms']['decoded_packets'],1);self.assertEqual(r['hms']['complete_cycles'],0)
    def test_send_failure_keeps_audit_and_stops_without_reads(self):
        def fail():raise OSError('write timeout')
        r=self.run_probe(on_send=fail)
        self.assertEqual(r['state'],'error');self.assertEqual(r['bulk_in_attempts'],0)
        self.assertTrue(r['bulk_out_delivery_unknown']);self.assertTrue(self.receiver.closed)
    def test_read_disconnect_keeps_already_received_data(self):
        r=self.run_probe([hms(),OSError('USB disconnected')])
        self.assertEqual(r['state'],'error');self.assertEqual(self.path.read_bytes(),hms())
        self.assertEqual(r['hms']['complete_cycles'],1);self.assertTrue(self.receiver.closed)
    def test_cancel_before_file_or_before_subscription_sends_no_command(self):
        factory=Mock()
        with self.assertRaises(InterruptedError):probe_hms(self.path,'01.00.1100',cancelled=lambda:True,transport_factory=factory)
        factory.assert_not_called();self.assertFalse(self.path.exists())
        calls=[False,True]
        r=self.run_probe(cancelled=lambda:calls.pop(0) if calls else True)
        self.assertEqual(r['protocol_commands_sent'],0);self.assertTrue(self.receiver.closed)
    def test_cancel_after_first_read_keeps_data_and_never_sends_reset(self):
        r=self.run_probe([hms()],cancelled=lambda:self.clock.value>=.2)
        self.assertEqual(r['stop_reason'],'detenida_por_usuario');self.assertEqual(r['protocol_commands_sent'],1)
        self.assertEqual(r['global_unsubscribe_commands_sent'],0);self.assertFalse(r['probe_completed'])
    def test_validation_and_no_overwrite_before_usb(self):
        factory=Mock();self.path.write_bytes(b'keep')
        for firmware,path in [('wrong',self.path),('01.00.1100',self.path.with_suffix('.txt'))]:
            with self.assertRaises(ValueError):probe_hms(path,firmware,transport_factory=factory)
        with self.assertRaises(FileExistsError):probe_hms(self.path,'01.00.1100',transport_factory=factory)
        factory.assert_not_called();self.assertEqual(self.path.read_bytes(),b'keep')
    def test_opening_diagnostics_are_kept_with_no_commands(self):
        from vision_usb_passive import UsbOpeningError
        diagnostics=[{'backend':'libusb0','stage':'check_product','message':'wrong model'}]
        r=probe_hms(self.path,'01.00.1100',transport_factory=Mock(side_effect=UsbOpeningError(diagnostics)))
        self.assertEqual(r['opening_diagnostics'],diagnostics);self.assertEqual(r['protocol_commands_attempted'],0)
    def test_byte_and_read_limits_stop_without_further_commands(self):
        with patch('vision_hms_query.MAX_BYTES',5):r=self.run_probe([hms()])
        self.assertEqual(r['stop_reason'],'limite_de_bytes');self.assertFalse(r['probe_completed'])
        self.path.unlink();self.clock=Clock()
        with patch('vision_hms_query.MAX_READS',1):r=self.run_probe()
        self.assertEqual(r['stop_reason'],'limite_de_lecturas');self.assertEqual(r['protocol_commands_sent'],1)
    def test_flush_and_close_errors_do_not_end_at_100(self):
        for operation in ('flush','close'):
            self.clock=Clock();receiver=Receiver(self.clock);progress=[]
            with patch('pathlib.Path.open') as output:
                if operation=='flush':output.return_value.__enter__.return_value.flush.side_effect=OSError('flush failed')
                else:receiver.close=Mock(side_effect=OSError('close failed'))
                r=probe_hms(self.path,'01.00.1100',transport_factory=lambda:receiver,clock=self.clock,progress=progress.append)
            self.assertEqual(r['state'],'error');self.assertFalse(r['probe_completed'])
            self.assertLess(progress[-1]['percent'],100)

if __name__=='__main__':unittest.main()
