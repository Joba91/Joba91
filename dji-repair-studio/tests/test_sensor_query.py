import tempfile
import hashlib
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from studio_service import packet
from studio_protocol import checksum
from vision_sensor_query import sn_request,SensorSnTransport,query_sensor_serials,SELECTORS
from vision_sensor_records import request_selector
from test_sensor_records import sample
import test_passive_usb as passive_fixtures

def response(selector=4,sequence=900):
    return packet(0x12,0x2a,sequence,0x24,0x26,sample(selector),flags=0)

class SnTransportTests(unittest.TestCase):
    setUp=passive_fixtures.PassiveTransportTests.setUp
    def ready(self):
        out=self.device.cfg[0][0];out.write.side_effect=None;out.write.return_value=28
        return SensorSnTransport(),out
    def test_only_four_exact_sn_requests_are_accepted(self):
        t,out=self.ready()
        for sequence,selector in enumerate(SELECTORS):
            frame=t.send_sn_query(selector,sequence)
            self.assertEqual(frame,sn_request(selector,sequence));self.assertEqual(len(frame),28)
            self.assertEqual(request_selector(frame),selector)
            self.assertEqual(checksum(frame[:-2],0x3692,0x8408),int.from_bytes(frame[-2:],'little'))
        self.assertEqual(out.write.call_count,4);self.assertFalse(hasattr(t,'write'))
        self.assertTrue(all(x['status']=='transferred' for x in t.tx_audit));t.close()
        for name in ('set_configuration','set_interface_altsetting','reset','detach_kernel_driver','ctrl_transfer','clear_halt','write'):
            getattr(self.device,name).assert_not_called()
    def test_request_bytes_match_four_historical_frame_hashes(self):
        expected={4:'e5b87b85a330aee4832ae43435a970ab8103ec88413fe6941c329b5020893dbe',
            8:'ef5770cc097f92b9ccbfc1cabda94e6b7dac625788ad1048c292d82d0daa18f1',
            64:'b8412b1f708a209605dadb9ac72559f8965f639581e90638e3e18a5c48db8826',
            128:'5c8530953b1438d92d9ca5310c1d1c16e7962d626e1d4962440cf0d21eae3826'}
        for selector,digest in expected.items():
            self.assertEqual(hashlib.sha256(sn_request(selector,5543)).hexdigest(),digest)
    def test_profile_rejection_prevents_any_sn_write(self):
        self.product.return_value='Mavic 3'
        with self.assertRaises(RuntimeError):SensorSnTransport()
        self.device.cfg[0][0].write.assert_not_called();self.claim.assert_not_called()
    def test_invalid_selector_sequence_and_duplicate_never_write(self):
        t,out=self.ready()
        for selector,seq in ((0,1),(1,1),(True,1),(4,-1),(4,65536),(4,True),(4,'1')):
            with self.assertRaises(ValueError):t.send_sn_query(selector,seq)
        out.write.assert_not_called()
        t.send_sn_query(4,1)
        with self.assertRaises(ValueError):t.send_sn_query(4,2)
        self.assertEqual(out.write.call_count,1);t.close()
        with self.assertRaises(RuntimeError):t.send_sn_query(8,2)
    def test_short_write_is_audited_and_never_retried(self):
        t,out=self.ready();out.write.return_value=7
        with self.assertRaises(IOError):t.send_sn_query(4,1)
        self.assertEqual(t.tx_audit[0]['transferred_bytes'],7)
        self.assertEqual(t.tx_audit[0]['status'],'short_write_delivery_unknown')
        with self.assertRaises(ValueError):t.send_sn_query(4,2)
        out.write.assert_called_once();t.close()
    def test_timeout_is_uncertain_delivery_and_does_not_allow_resend(self):
        t,out=self.ready();out.write.side_effect=IOError('write timeout')
        with self.assertRaises(IOError):t.send_sn_query(4,1)
        self.assertEqual(t.tx_audit[0]['status'],'delivery_unknown')
        self.assertIsNone(t.tx_audit[0]['transferred_bytes'])
        with self.assertRaises(ValueError):t.send_sn_query(4,2)
        self.assertEqual(out.write.call_args.kwargs['timeout'],500);t.close()

class Clock:
    value=0
    def __call__(self):return self.value

class Receiver:
    def __init__(self,clock,on_send=None,baseline=()):
        self.clock=clock;self.pending=list(baseline);self.on_send=on_send
        self.tx_audit=[];self.timeouts=0;self.closed=False
        self.evidence={'interface':4,'bulk_in':'85','synthetic':True}
    def read(self):
        self.clock.value+=.2
        value=self.pending.pop(0) if self.pending else b''
        if isinstance(value,Exception):raise value
        if not value:self.timeouts+=1
        return value
    def send_sn_query(self,selector,sequence):
        request=sn_request(selector,sequence)
        self.tx_audit.append({'selector':selector,'sequence':sequence,'hex':request.hex(' '),
            'requested_bytes':28,'transferred_bytes':None,'status':'delivery_unknown'})
        if self.on_send:self.pending.extend(self.on_send(selector,sequence))
        self.tx_audit[-1].update(transferred_bytes=28,status='transferred')
        return request
    def close(self):self.closed=True

class SensorQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'new.bin';self.clock=Clock();self.progress=[]
    def run_query(self,on_send=None,baseline=(),**kwargs):
        self.receiver=Receiver(self.clock,on_send,baseline)
        return query_sensor_serials(self.path,'01.00.1100',transport_factory=lambda:self.receiver,
            clock=self.clock,sequence_seed=65534,progress=self.progress.append,**kwargs)
    def test_serials_remain_observations_even_when_four_records_are_valid(self):
        r=self.run_query(lambda sel,seq:[response(sel,900)])
        self.assertTrue(r['probe_completed']);self.assertEqual(r['protocol_commands_sent'],4)
        self.assertEqual(r['bulk_out_bytes_confirmed'],112);self.assertEqual(r['received_bytes'],132)
        self.assertEqual(self.path.read_bytes(),b''.join(response(s) for s in SELECTORS))
        self.assertEqual([q['sequence'] for q in r['queries']],[65535,0,1,2])
        for q in r['queries']:
            self.assertEqual(q['serials_observed'],['ABCTAC10071234'])
            self.assertEqual(q['observation_status'],'sn_observado');self.assertFalse(q['current_device_confirmed'])
        self.assertEqual(r['state'],'desconocido');self.assertFalse(r['query_reply_correlation_validated'])
        self.assertFalse(r['normal_mode_firmware_support_validated']);self.assertEqual(r['device_health'],'desconocido')
        self.assertTrue(self.receiver.closed);self.assertEqual(self.progress[-1]['percent'],100)
    def test_same_sequence_is_logged_but_does_not_prove_correlation(self):
        r=self.run_query(lambda sel,seq:[response(sel,seq)])
        self.assertTrue(r['queries'][0]['observations'][0]['request_sequence_equal'])
        self.assertFalse(r['current_device_confirmed'])
    def test_silence_completes_windows_without_declaring_sensor_fault(self):
        r=self.run_query();self.assertTrue(r['probe_completed']);self.assertEqual(r['received_bytes'],0)
        self.assertTrue(all(q['observation_status']=='sin_registro_identificable' for q in r['queries']))
        self.assertEqual(r['device_configuration_writes'],0);self.assertEqual(r['factory_commands_sent'],0)
        self.assertEqual(r['calibration_commands_sent'],0);self.assertEqual(r['driver_changes'],0)
    def test_wrong_selector_is_not_assigned_to_requested_sensor(self):
        r=self.run_query(lambda sel,seq:[response(8 if sel==4 else 4)])
        self.assertEqual(r['other_selector_records'],4)
        self.assertTrue(all(not q['serials_observed'] for q in r['queries']))
    def test_bad_crc_other_header_flags_and_commands_are_ignored(self):
        bad=bytearray(response());bad[-1]^=1
        def replies(sel,seq):
            return [bytes(bad),packet(0x12,0x2a,seq,0x24,0x26,sample(sel),flags=0x80),
                packet(0x03,0x2a,seq,0x24,0x26,sample(sel),flags=0),
                packet(0x12,0x2a,seq,0x24,0x27,sample(sel),flags=0)]
        r=self.run_query(replies);self.assertTrue(all(not q['serials_observed'] for q in r['queries']))
    def test_invalid_record_does_not_create_a_serial(self):
        def replies(sel,seq):
            body=bytearray(sample(sel));body[12]=0
            return [packet(0x12,0x2a,seq,0x24,0x26,body,flags=0)]
        r=self.run_query(replies)
        self.assertTrue(all(q['matching_records']==1 and not q['serials_observed'] for q in r['queries']))
    def test_duplicate_records_are_not_distinct_serials(self):
        r=self.run_query(lambda sel,seq:[response(sel),response(sel)])
        self.assertEqual(r['queries'][0]['matching_records'],2)
        self.assertEqual(r['queries'][0]['observation_status'],'sn_observado')
    def test_conflicting_serials_are_marked_ambiguous(self):
        def replies(sel,seq):
            body=bytearray(sample(sel));body[-4:]=b'5678'
            return [response(sel),packet(0x12,0x2a,seq,0x24,0x26,body,flags=0)]
        r=self.run_query(replies)
        self.assertTrue(all(q['observation_status']=='ambiguo' for q in r['queries']))
    def test_record_present_before_queries_is_explicitly_logged(self):
        r=self.run_query(lambda sel,seq:[response(sel)],baseline=[response(4)])
        self.assertEqual(len(r['baseline_observations']),1)
        self.assertTrue(r['queries'][0]['observations'][0]['seen_before_queries'])
    def test_fragmented_response_is_reassembled(self):
        r=self.run_query(lambda sel,seq:[response(sel)[:6],response(sel)[6:]])
        self.assertTrue(all(len(q['serials_observed'])==1 for q in r['queries']))
    def test_partial_baseline_is_not_attributed_to_the_query(self):
        r=self.run_query(lambda sel,seq:[response(sel)[6:]],baseline=[response(4)[:6]])
        self.assertEqual(r['baseline_pending_bytes_unassigned'],6)
        self.assertTrue(all(not q['serials_observed'] for q in r['queries']))
    def test_failed_send_keeps_uncertain_audit_and_stops_without_retry(self):
        def failed(sel,seq):raise OSError('write disconnected')
        r=self.run_query(failed)
        self.assertEqual(r['state'],'error');self.assertEqual(r['protocol_commands_attempted'],1)
        self.assertEqual(r['protocol_commands_sent'],0);self.assertTrue(r['bulk_out_delivery_unknown'])
        self.assertEqual(len(r['queries']),1);self.assertTrue(self.receiver.closed)
        self.assertLess(self.progress[-1]['percent'],100)
    def test_read_failure_keeps_partial_bytes_and_candidates(self):
        r=self.run_query(lambda sel,seq:[response(sel),OSError('read disconnected')])
        self.assertEqual(r['state'],'error');self.assertEqual(self.path.read_bytes(),response(4))
        self.assertEqual(len(r['queries']),1);self.assertEqual(r['queries'][0]['observation_status'],'ventana_incompleta')
        self.assertEqual(r['queries'][0]['serials_observed'],['ABCTAC10071234']);self.assertTrue(self.receiver.closed)
    def test_cancellation_before_open_never_creates_file_or_transport(self):
        factory=Mock()
        with self.assertRaises(InterruptedError):query_sensor_serials(self.path,'01.00.1100',cancelled=lambda:True,transport_factory=factory)
        factory.assert_not_called();self.assertFalse(self.path.exists())
    def test_cancellation_during_baseline_sends_no_command(self):
        r=self.run_query(cancelled=lambda:self.clock.value>=.2)
        self.assertEqual(r['stop_reason'],'detenida_por_usuario');self.assertEqual(r['protocol_commands_attempted'],0)
        self.assertFalse(r['probe_completed']);self.assertTrue(self.receiver.closed)
    def test_cancellation_after_first_send_never_sends_second(self):
        r=self.run_query(cancelled=lambda:hasattr(self,'receiver') and bool(self.receiver.tx_audit))
        self.assertEqual(r['protocol_commands_sent'],1);self.assertEqual(r['stop_reason'],'detenida_por_usuario')
    def test_validation_and_exclusive_file_creation_before_usb(self):
        factory=Mock();self.path.write_bytes(b'keep')
        for fw,path in [('wrong',self.path),('01.00.1100',self.path.with_suffix('.json'))]:
            with self.assertRaises(ValueError):query_sensor_serials(path,fw,transport_factory=factory)
        with self.assertRaises(FileExistsError):query_sensor_serials(self.path,'01.00.1100',transport_factory=factory)
        factory.assert_not_called();self.assertEqual(self.path.read_bytes(),b'keep')
    def test_opening_error_is_preserved_with_no_tx(self):
        from vision_usb_passive import UsbOpeningError
        diagnostics=[{'backend':'libusb0','stage':'check_parent_product','message':'wrong model'}]
        r=query_sensor_serials(self.path,'01.00.1100',transport_factory=Mock(side_effect=UsbOpeningError(diagnostics)))
        self.assertEqual(r['opening_diagnostics'],diagnostics);self.assertEqual(r['protocol_commands_attempted'],0)
    def test_size_and_read_count_limits_stop_before_more_queries(self):
        with patch('vision_sensor_query.MAX_BYTES',20):
            r=self.run_query(lambda sel,seq:[response(sel)])
        self.assertEqual(r['stop_reason'],'limite_de_bytes');self.assertEqual(r['protocol_commands_sent'],1)
        self.path.unlink();self.clock=Clock()
        with patch('vision_sensor_query.MAX_READS',1):r=self.run_query()
        self.assertEqual(r['stop_reason'],'limite_de_lecturas');self.assertEqual(r['protocol_commands_sent'],0)
    def test_overall_time_limit_stops_after_slow_read(self):
        clock=self.clock
        receiver=Receiver(clock);receiver.read=Mock(side_effect=lambda:(setattr(clock,'value',20) or b''))
        r=query_sensor_serials(self.path,'01.00.1100',transport_factory=lambda:receiver,clock=clock)
        self.assertEqual(r['stop_reason'],'limite_de_tiempo');self.assertEqual(r['protocol_commands_sent'],0)
    def test_close_failure_is_not_reported_as_completed_or_100_percent(self):
        receiver=Receiver(self.clock);receiver.close=Mock(side_effect=OSError('close failed'))
        r=query_sensor_serials(self.path,'01.00.1100',transport_factory=lambda:receiver,clock=self.clock,progress=self.progress.append)
        self.assertEqual(r['state'],'error');self.assertFalse(r['probe_completed'])
        self.assertLess(self.progress[-1]['percent'],100)
    def test_disk_error_stops_queries_and_closes_transport(self):
        receiver=Receiver(self.clock,lambda sel,seq:[response(sel)])
        with patch('pathlib.Path.open') as output:
            output.return_value.__enter__.return_value.write.side_effect=OSError('disk full')
            r=query_sensor_serials(self.path,'01.00.1100',transport_factory=lambda:receiver,clock=self.clock)
        self.assertEqual(r['state'],'error');self.assertIn('disk full',r['error'])
        self.assertTrue(receiver.closed);self.assertEqual(r['protocol_commands_sent'],1)
    def test_oversized_chunk_is_not_saved_or_accepted(self):
        r=self.run_query(lambda sel,seq:[bytes(513)])
        self.assertEqual(r['state'],'error');self.assertEqual(r['received_bytes'],0)
        self.assertEqual(r['protocol_commands_sent'],1)
    def test_flush_failure_after_all_windows_does_not_report_completion(self):
        receiver=Receiver(self.clock)
        with patch('pathlib.Path.open') as output:
            output.return_value.__enter__.return_value.flush.side_effect=OSError('flush failed')
            r=query_sensor_serials(self.path,'01.00.1100',transport_factory=lambda:receiver,clock=self.clock,progress=self.progress.append)
        self.assertEqual(r['state'],'error');self.assertFalse(r['probe_completed'])
        self.assertTrue(receiver.closed);self.assertLess(self.progress[-1]['percent'],100)

if __name__=='__main__':unittest.main()
