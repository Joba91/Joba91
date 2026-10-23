import unittest
from studio_service import Session, packet, analyze, validate, Cancelled
from studio_protocol import Decoder

class Clock:
    def __init__(self):self.value=0
    def __call__(self):self.value+=0.02;return self.value

def reply(request, payload=b'\0'):
    return packet(request[5],request[4],int.from_bytes(request[6:8],'little'),request[9],request[10],payload,flags=0x80)
def status(payload):return packet(4,10,123,4,0x30,payload,flags=0x80)
class Transport:
    def __init__(self,handler):self.handler=handler;self.data=[];self.sent=[]
    def write(self,data):self.sent.append(data);self.data.extend(self.handler(data));return len(data)
    def read(self,size):return self.data.pop(0) if self.data else b''

class ServiceTests(unittest.TestCase):
    def test_coarse_packet_matches_original(self):
        self.assertEqual(packet(10,4,0,4,8,b'\1').hex(' '), '55 0e 04 66 0a 04 00 00 40 04 08 01 be b2')
    def test_hall_packet_matches_original(self):
        self.assertEqual(packet(10,4,0,4,8,b'\2').hex(' '), '55 0e 04 66 0a 04 00 00 40 04 08 02 25 80')
    def test_factory_packet_matches_original(self):
        self.assertEqual(packet(42,0x8f,0,0,0x44,b'\x80\x0astart_factory\0').hex(' '),
                         '55 1d 04 df 2a 8f 00 00 40 00 44 80 0a 73 74 61 72 74 5f 66 61 63 74 6f 72 79 00 fc 25')
    def test_exit_packet_matches_original(self):
        self.assertEqual(packet(42,0x68,0,0,0x44,b'\x80\x0astop_factory\0').hex(' '),
                         '55 1c 04 1b 2a 68 00 00 40 00 44 80 0a 73 74 6f 70 5f 66 61 63 74 6f 72 79 00 f6 e6')
    def test_user_echo_response_is_crc_valid_but_not_success(self):
        info=analyze('55 0e 04 66 04 0a 8e ad 80 04 08 01 fb 95')
        self.assertTrue(info['valido']);self.assertEqual(info['payload'],'01')
        t=Transport(lambda req:[reply(req,b'\x01')])
        with self.assertRaises(TimeoutError):
            Session(t,clock=Clock()).calibrate('JointCoarse')
        self.assertEqual(len(t.sent),1)
    def test_echo_requires_matching_progress_before_success(self):
        t=Transport(lambda req:[reply(req,b'\x01')+status(b'\x52\1')+status(b'\x64\0')])
        self.assertEqual(Session(t,clock=Clock()).calibrate('JointCoarse')['estado'],'equipo_informa_fin')
    def test_coarse_progress_and_success_in_same_usb_read(self):
        t=Transport(lambda req:[reply(req,b'\1\x11')+status(b'\x52\1')+status(b'\x64\0')])
        r=Session(t,clock=Clock()).calibrate('JointCoarse')
        self.assertEqual(r['estado'],'equipo_informa_fin');self.assertFalse(r['imu_escrita'])
        self.assertTrue(r['salida_fabrica_pendiente'])
    def test_hall_progress_and_success(self):
        t=Transport(lambda req:[reply(req)+status(b'\x11\1')+status(b'\x64\0')])
        self.assertEqual(Session(t,clock=Clock()).calibrate('LinearHall')['estado'],'equipo_informa_fin')
    def test_terminal_without_new_progress_is_not_success(self):
        t=Transport(lambda req:[reply(req,b'\1\x11')+status(b'\x64\0')])
        with self.assertRaisesRegex(RuntimeError,'sin etapas'):Session(t,clock=Clock()).calibrate('JointCoarse')
    def test_wrong_progress_family_does_not_confirm_coarse(self):
        t=Transport(lambda req:[reply(req,b'\1\x11')+status(b'\x11\1')+status(b'\x64\0')])
        with self.assertRaisesRegex(RuntimeError,'sin etapas'):Session(t,clock=Clock()).calibrate('JointCoarse')
    def test_reported_failure(self):
        t=Transport(lambda req:[reply(req,b'\1\x11')+status(b'\x64\3')])
        with self.assertRaisesRegex(RuntimeError,'FALLIDA'):Session(t,clock=Clock()).calibrate('JointCoarse')
    def test_no_ack_is_timeout_no_retry(self):
        t=Transport(lambda req:[])
        with self.assertRaises(TimeoutError):Session(t,clock=Clock(),timeout=.1).calibrate('JointCoarse')
        self.assertEqual(len(t.sent),1)
    def test_wrong_sequence_does_not_confirm_request(self):
        t=Transport(lambda req:[packet(4,10,0,4,8,b'\1\x11',flags=0x80)])
        s=Session(t,clock=Clock(),timeout=.1);s.sequence=999
        with self.assertRaises(TimeoutError):s.calibrate('JointCoarse')
    def test_crc_failure_ignored(self):
        def handle(req):
            bad=bytearray(reply(req));bad[-1]^=1;return [bytes(bad)]
        with self.assertRaises(TimeoutError):Session(Transport(handle),clock=Clock(),timeout=.1).request(10,4,4,8,b'\2')
    def test_factory_requires_both_confirmations(self):
        t=Transport(lambda req:[reply(req,b'\0' if req[5]==0x8f else b'\xfb')])
        with self.assertRaisesRegex(RuntimeError,'incompleta'):Session(t,clock=Clock()).factory(True)
        self.assertEqual(len(t.sent),2)
    def test_factory_success_is_restart_pending(self):
        t=Transport(lambda req:[reply(req)])
        self.assertEqual(Session(t,clock=Clock()).factory(True)['estado'],'orden_confirmada_reinicio_pendiente')
    def test_exit_attempts_second_even_when_first_rejected(self):
        t=Transport(lambda req:[reply(req,b'\xfb' if req[5]==0x8f else b'\0')])
        with self.assertRaises(RuntimeError):Session(t,clock=Clock()).factory(False)
        self.assertEqual(len(t.sent),2)
    def test_cancel_does_not_send_stop_or_other_commands(self):
        t=Transport(lambda req:[])
        with self.assertRaises(Cancelled):Session(t,cancelled=lambda:True).calibrate('JointCoarse')
        self.assertEqual(t.sent,[])
    def test_model_firmware_and_preparation_guards(self):
        with self.assertRaises(ValueError):validate('Mavic 4 Pro','01.00.0200','JointCoarse',True)
        with self.assertRaises(ValueError):validate('Mavic 3 Classic','01.00.0600','JointCoarse',True)
        with self.assertRaises(ValueError):validate('Mavic 3','01.00.0200','JointCoarse',True)
        with self.assertRaises(ValueError):validate('Mavic 3','01.00.0500','JointCoarse',False)
        validate('Mavic 3','01.00.0500','JointCoarse',True)
        validate('Mavic 3','','Salir modo fabrica')
    def test_passive_capture_does_not_send(self):
        t=Transport(lambda req:[])
        r=Session(t,clock=Clock()).monitor(.1)
        self.assertEqual(r['estado'],'escucha_completada');self.assertEqual(t.sent,[])
    def test_analyzer_reports_bad_checksum(self):
        raw=bytearray(status(b'\x52\1'));raw[-1]^=1
        self.assertFalse(analyze(raw.hex())['valido'])
    def test_unknown_status_is_not_terminal(self):
        t=Transport(lambda req:[]);t.data=[status(b'\x64\1')]
        with self.assertRaises(TimeoutError):Session(t,clock=Clock()).monitor(.1,require_progress=True)
    def test_short_or_bad_hex_rejected(self):
        for text in ('', '5', 'zz', '55 0e'):
            with self.subTest(text=text),self.assertRaises(ValueError):analyze(text)

if __name__=='__main__':unittest.main()
