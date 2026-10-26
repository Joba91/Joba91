import unittest
from studio_service import packet
from vision_hms import HmsTracker
from vision_hms_extended import parse_hms_extended_frame,code_reference
from vision_protocol import decode_bytes
from test_hms import hms,record,Receiver,Clock
from vision_hms_query import probe_hms
from pathlib import Path
import tempfile

def ext_record(code=0x1A510380,tail=None,tag=0):
    body=code.to_bytes(4,'little')+(bytes(16) if tail is None else tail)
    return bytes([tag,len(body)])+body

def ext(cycle=0,index=0,end=True,records=(),sender=0x1d,receiver=0x0a,version=0,flags=0):
    payload=bytes([version,cycle,index|(128 if end else 0),len(records)])+b''.join(records)
    return packet(sender,receiver,100,0x21,8,payload,flags=flags)

class ExtendedHmsTests(unittest.TestCase):
    def test_envelope_exposes_code_and_preserves_uninterpreted_body(self):
        tail=bytes.fromhex('03 00 00 04 12 00 00 00 00 00 00 04 00 00 00 00')
        p=parse_hms_extended_frame(ext(records=[ext_record(tail=tail)]))
        self.assertEqual(p['declared_record_count'],1);self.assertEqual(p['command_id_raw'],'08')
        r=p['records'][0];self.assertEqual(r['alarm_code_raw'],'0x1A510380')
        self.assertEqual(r['body_bytes_4_to_19_raw'],tail.hex(' '))
        self.assertIsNone(r['sensor_index_raw']);self.assertIsNone(r['report_level_raw'])
        self.assertEqual(r['alarm_activity'],'desconocido');self.assertFalse(r['vision_association_confirmed'])
    def test_reference_labels_never_confirm_current_model_or_active_fault(self):
        for code in ('0x1A510380','0x1A510382','0x1A510384','0x1A510385','0x1C000404','0x1C000408'):
            r=code_reference(code)
            self.assertTrue(r['reference_description_available']);self.assertIn('Referencia SDK:',r['description'])
            self.assertFalse(r['reference_applies_to_current_model_confirmed']);self.assertEqual(r['alarm_activity'],'desconocido')
        self.assertFalse(code_reference('0x11111111')['reference_description_available'])
    def test_empty_packet_does_not_mean_healthy(self):
        t=HmsTracker();t.observe(ext());r=t.result()
        self.assertEqual(r['complete_cycles'],1);self.assertEqual(r['records_preview'],[])
        self.assertEqual(r['device_health'],'desconocido')
    def test_fragmented_extended_cycles_require_all_parts(self):
        t=HmsTracker();t.observe(ext(index=2,records=[ext_record()]))
        t.observe(ext(index=0,end=False));self.assertEqual(t.result()['complete_cycles'],0)
        t.observe(ext(index=1,end=False));self.assertEqual(t.result()['complete_cycles'],1)
        self.assertTrue(t.result()['records_preview'][0]['seen_in_complete_cycle'])
    def test_cycle_sources_include_command_family_to_avoid_cross_filling(self):
        t=HmsTracker();t.observe(hms(index=0,end=False));t.observe(ext(index=1))
        self.assertEqual(t.result()['complete_cycles'],0);self.assertEqual(t.result()['incomplete_cycles'],2)
    def test_mixed_families_remain_separate_even_for_same_code(self):
        t=HmsTracker();t.observe(hms(records=[record(code=0x1A510380)]));t.observe(ext(records=[ext_record()]))
        r=t.result();self.assertEqual(r['family_counts'],{'21/06':1,'21/08':1})
        self.assertEqual(r['distinct_records_shown'],2)
        self.assertEqual({row['command_id_raw'] for row in r['records_preview']},{'06','08'})
    def test_distinct_opaque_metadata_is_not_collapsed_as_same_state(self):
        t=HmsTracker();t.observe(ext(cycle=0,records=[ext_record()]))
        tail=bytearray(16);tail[3]=4
        t.observe(ext(cycle=1,records=[ext_record(tail=tail)]))
        self.assertEqual(t.result()['distinct_records_shown'],2)
        self.assertTrue(all(r['alarm_activity']=='desconocido' for r in t.result()['records_preview']))
    def test_duplicate_tlv_packet_does_not_inflate_record_count(self):
        t=HmsTracker();f=ext(records=[ext_record()]);t.observe(f);t.observe(f)
        self.assertEqual(t.result()['record_observations'],1);self.assertEqual(t.result()['duplicate_packets'],1)
    def test_contradiction_revokes_extended_cycle(self):
        t=HmsTracker();t.observe(ext(records=[ext_record()]));t.observe(ext(records=[ext_record(code=1)]))
        self.assertEqual(t.result()['complete_cycles'],0)
        self.assertFalse(t.result()['records_preview'][0]['seen_in_complete_cycle'])
    def test_unknown_tag_or_length_stays_opaque_without_exposing_a_code(self):
        opaque=bytes([1,13])+b'ABCDEFGHIJKLM'
        p=parse_hms_extended_frame(ext(records=[opaque,ext_record()]))
        self.assertEqual(len(p['records']),1);self.assertEqual(p['opaque_records'][0]['body_hex'],b'ABCDEFGHIJKLM'.hex(' '))
        t=HmsTracker();t.observe(ext(records=[opaque,ext_record()]));r=t.result()
        self.assertEqual(r['opaque_record_observations'],1);self.assertEqual(r['cycles_preview'][0]['record_count'],2)
    def test_unknown_size_tag_zero_is_not_decoded_as_twenty_byte_record(self):
        p=parse_hms_extended_frame(ext(records=[bytes([0,4])+b'ABCD']))
        self.assertEqual(p['records'],[]);self.assertEqual(len(p['opaque_records']),1)
    def test_bad_header_version_flags_count_length_or_crc_is_rejected(self):
        bad=bytearray(ext());bad[-1]^=1
        payloads=[b'\0\0\x80',b'\0\0\x80\x01',b'\0\0\x80\x01\x00',
            b'\0\0\x80\x01\x00\x14abc',b'\0\0\x80\x00abc']
        frames=[bytes(bad),ext(version=1),ext(flags=0x80),hms()]
        frames.extend(packet(0x1d,0x0a,10,0x21,8,p,flags=0) for p in payloads)
        for frame in frames:
            with self.subTest(frame=frame.hex()),self.assertRaises(ValueError):parse_hms_extended_frame(frame)
    def test_offline_stream_analysis_keeps_reference_and_activity_separate(self):
        r=decode_bytes(ext(records=[ext_record()]))
        self.assertEqual(r['valid_frames'],1);self.assertEqual(r['hms']['family_counts']['21/08'],1)
        self.assertEqual(r['hms']['records_preview'][0]['alarm_activity'],'desconocido')
        self.assertFalse(r['hms']['alarm_code_mapping_validated'])
    def test_live_hms_probe_also_observes_extended_frames_without_new_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock();f=ext(records=[ext_record()]);receiver=Receiver(clock,[f])
            r=probe_hms(Path(directory)/'new.bin','01.00.1100',transport_factory=lambda:receiver,clock=clock,sequence_seed=10)
        self.assertEqual(r['protocol_commands_sent'],1);self.assertEqual(r['bulk_out_bytes_confirmed'],14)
        self.assertEqual(r['hms']['family_counts']['21/08'],1);self.assertEqual(r['device_health'],'desconocido')
    def test_extended_data_for_another_recipient_are_not_current_probe_results(self):
        with tempfile.TemporaryDirectory() as directory:
            clock=Clock();receiver=Receiver(clock,[ext(receiver=0x2a)])
            r=probe_hms(Path(directory)/'new.bin','01.00.1100',transport_factory=lambda:receiver,clock=clock,sequence_seed=10)
        self.assertEqual(r['foreign_recipient_hms_packets'],1);self.assertEqual(r['hms']['packets_seen'],0)

if __name__=='__main__':unittest.main()
