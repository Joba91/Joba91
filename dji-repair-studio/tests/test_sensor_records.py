"""Synthetic records only. No customer serials or proprietary DLLs required."""
import unittest
from studio_service import packet
from vision_sensor_records import decode_perception_record
from vision_history import analyze_dji_log
from test_history import log_pair

def sample(selector=4):
    # CBA reverses to ABC; vendor T, year A, month C, day 1, zero fields,
    # low-nibble 7 and suffix 1234. This is deliberately fictional data.
    return bytes([0,160,0,selector,84,0,0,0,0,67,66,65,13,12,1,7,49,50,51,52])

class SensorRecordTests(unittest.TestCase):
    def test_binary_conversion_without_a_serial_label(self):
        r=decode_perception_record(sample())
        self.assertEqual(r['serial_from_payload'],'ABCTAC10071234')
        self.assertEqual(r['state'],'confirmado')
        self.assertFalse(r['current_device_confirmed'])
        self.assertEqual(r['device_health'],'desconocido')

    def test_four_selectors_only(self):
        for selector,role in [(4,'frontleft'),(8,'frontright'),(64,'backleft'),(128,'backright')]:
            self.assertEqual(decode_perception_record(sample(selector))['role_historical'],role)
        for selector in (0,1,2,12,255):
            self.assertNotIn('serial_from_payload',decode_perception_record(sample(selector)))

    def test_vendor_map_and_ascii_passthrough(self):
        for vendor,expected in [(16,'S'),(1,'C'),(32,'F'),(48,'Q'),(78,'N'),(84,'T')]:
            p=bytearray(sample());p[4]=vendor
            self.assertEqual(decode_perception_record(p)['serial_from_payload'][3],expected)

    def test_unknown_layout_not_guessed(self):
        for p in (b'',sample()[:-1],sample()+b'\0',b'\x01'+sample()[1:]):
            self.assertEqual(decode_perception_record(p)['state'],'desconocido')

    def test_invalid_fields_do_not_become_plausible_serials(self):
        for offset,value in [(4,0),(5,1),(6,1),(9,255),(12,12),(12,37),(13,0),(13,13),(14,0),(14,32),(15,10),(16,0),(19,255)]:
            p=bytearray(sample());p[offset]=value
            self.assertNotIn('serial_from_payload',decode_perception_record(p),(offset,value))

    def test_high_nibble_is_opaque_and_low_nibble_decimal(self):
        p=bytearray(sample());p[15]=0xf7
        self.assertEqual(decode_perception_record(p)['serial_from_payload'],'ABCTAC10071234')

    def frames(self,selector=4,request_selector=4):
        query=packet(0x2a,0x12,7,0x24,0x26,b'\x0f'+bytes(11)+b'\xa0\0'+bytes([request_selector]),flags=0x40)
        record=packet(0x12,0x2a,900,0x24,0x26,sample(selector),flags=0)
        return query,record

    def test_label_is_independent_of_binary_conversion(self):
        q,a=self.frames()
        r=analyze_dji_log(log_pair(q,a,'msg:Log: frontleft=ABCTAC10071234\n'))
        c=r['perception_records']['counts']
        self.assertEqual(c,{'records':1,'decoded':1,'selector_agreements':1,'label_matches':1})
        self.assertIn('asociacion_del_registro_sin_correlacion_de_cabeceras',r['historical_traffic']['association_counts'])
        self.assertFalse(r['success_inferred']);self.assertEqual(r['identity']['state'],'desconocido')

    def test_label_disagreement_and_selector_disagreement_are_visible(self):
        q,a=self.frames(request_selector=8)
        r=analyze_dji_log(log_pair(q,a,'msg:Log: frontleft=ABCTAC10070000\n'))
        c=r['perception_records']['counts']
        self.assertEqual(c['label_mismatches'],1);self.assertEqual(c['selector_mismatches'],1)
        self.assertFalse(r['perception_records']['observations_preview'][0]['header_correlation_confirmed'])

    def test_bad_crc_never_decoded(self):
        q,a=self.frames();a=bytearray(a);a[-1]^=1
        r=analyze_dji_log(log_pair(q,a))
        self.assertEqual(r['issue_count'],1);self.assertEqual(r['perception_records']['counts'],{})

    def test_echo_or_unrelated_headers_never_decoded(self):
        q,a=self.frames()
        for other in (q,packet(10,4,7,0x24,0x26,sample(),flags=0),packet(0x12,0x2a,7,0x24,0x26,sample(),flags=128)):
            self.assertEqual(analyze_dji_log(log_pair(q,other))['perception_records']['counts'],{})

    def test_label_after_next_transaction_is_not_attached(self):
        q,a=self.frames()
        text=log_pair(q,a)+log_pair(q,q,'msg:Log: frontleft=ABCTAC10071234\n')
        r=analyze_dji_log(text)['perception_records']
        self.assertNotIn('label_matches',r['counts'])
        self.assertEqual(r['observations_preview'][0]['label_comparison'],'sin_etiqueta_contrastable')

if __name__=='__main__':unittest.main()
