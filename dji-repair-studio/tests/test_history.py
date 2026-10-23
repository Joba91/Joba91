import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_service import packet
from vision_history import analyze_dji_log
from vision_protocol import analyze_capture

def log_pair(command,ack,extra=''):
    return ('<2024-03-09 09:00:00>[INF]func:tpf::FlowItem::Log,msg:Log: cmd Send: '+command.hex(' ')+'\n'
            'Log: CmdAndAck:\nCMD: '+command.hex(' ')+'\nACK: '+ack.hex(' ')+' ########\n'+extra)

class HistoricalLogTests(unittest.TestCase):
    def setUp(self):
        self.command=packet(10,4,7,0,1)
        self.ack=packet(4,10,7,0,1,b'\0',flags=0x80)
    def test_pair_counts_only_authoritative_layer(self):
        result=analyze_dji_log(log_pair(self.command,self.ack))
        self.assertEqual(result['valid_frames'],2)
        self.assertEqual(result['historical_traffic']['distinct_labeled_ack'],1)
        self.assertEqual(result['historical_traffic']['ignored_send_layer_records'],1)
        self.assertEqual(result['historical_traffic']['association_counts'],{'cabeceras_correlacionadas_resultado_desconocido':1})
        self.assertFalse(result['success_inferred'])
    def test_echo_is_not_confirmed_ack(self):
        result=analyze_dji_log(log_pair(self.command,self.command))
        self.assertEqual(result['historical_traffic']['association_counts'],{'echo_no_confirma_respuesta':1})
    def test_sequence_or_sender_mismatch_is_not_correlated(self):
        for ack in (packet(4,10,8,0,1,b'\0',flags=128),packet(10,4,7,0,1,b'\0',flags=128)):
            result=analyze_dji_log(log_pair(self.command,ack))
            self.assertEqual(result['historical_traffic']['association_counts'],{'asociacion_del_registro_sin_correlacion_de_cabeceras':1})
    def test_command_like_flags_do_not_confirm_response(self):
        ack=packet(4,10,7,0,1,b'\0',flags=0)
        result=analyze_dji_log(log_pair(self.command,ack))
        self.assertNotIn('cabeceras_correlacionadas_resultado_desconocido',result['historical_traffic']['association_counts'])
    def test_sensor_labels_are_historical_not_payload_decoding(self):
        extra='msg:Log: frontleft=6KBTEST0000001\nmsg:Log: backright=-\n'
        result=analyze_dji_log(log_pair(self.command,self.ack,extra))
        sensor=result['historical_sensors']
        self.assertEqual(sensor['observations_preview'][0]['serial_reported'],'6KBTEST0000001')
        self.assertEqual(sensor['invalid_or_empty_labels'],1)
        self.assertEqual(result['identity']['state'],'desconocido')
        self.assertEqual(result['usb_operations'],0)
    def test_usb_observations_never_confirm_live_endpoints(self):
        extra='func:tpf::BulkComm::_SearchDevice,msg:Device seen. vid:2ca3, pid:20, mi:4, location:ignored\n'
        result=analyze_dji_log(extra)
        self.assertEqual(result['historical_usb']['observations'][0]['interface'],4)
        self.assertFalse(result['historical_usb']['endpoints_confirmed'])
        self.assertFalse(result['historical_usb']['current_device_confirmed'])
    def test_malformed_and_truncated_records_do_not_merge(self):
        bad=self.ack[:-1]
        result=analyze_dji_log(log_pair(self.command,bad))
        self.assertEqual(result['valid_frames'],1);self.assertEqual(result['issue_count'],1)
        self.assertEqual(result['state'],'error')
    def test_crc_damage_is_reported_per_line(self):
        bad=bytearray(self.ack);bad[-1]^=1
        result=analyze_dji_log(log_pair(self.command,bad))
        self.assertEqual(result['issues_preview'][0]['kind'],'crc_trama')
        self.assertIn('line',result['issues_preview'][0])
    def test_authentication_and_random_hex_are_not_traffic(self):
        noise='cookie: private-cookie-example\naccess_token: secret-example-55ab00\n09:10:55 55 01 04 00\n'
        result=analyze_dji_log(log_pair(self.command,self.ack,noise))
        serialized=json.dumps(result)
        self.assertNotIn('private-cookie',serialized);self.assertNotIn('secret-example',serialized)
        self.assertEqual(result['issue_count'],0);self.assertEqual(result['valid_frames'],2)
    def test_orphan_records_not_promoted_to_pairs(self):
        result=analyze_dji_log('ACK: '+self.ack.hex(' ')+'\nCMD: '+self.command.hex(' '))
        self.assertEqual(result['historical_traffic']['association_counts'],{'acks_without_adjacent_request':1,'requests_without_adjacent_ack':1})
    def test_send_only_fallback_is_disclosed(self):
        result=analyze_dji_log('func:tpf::FlowItem::Log,msg:Log: cmd Send: '+self.command.hex(' '))
        self.assertEqual(result['valid_frames'],1);self.assertEqual(result['historical_traffic']['record_layer'],'SEND')
        self.assertEqual(result['historical_traffic']['distinct_labeled_ack'],0)
    def test_gb18030_and_utf16_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'capture.log'
            for encoding in ('gb18030','utf-16'):
                path.write_bytes(('测试记录\n'+log_pair(self.command,self.ack)).encode(encoding))
                result=analyze_capture(path)
                self.assertEqual(result['encoding'],encoding)
                self.assertEqual(result['format'],'djilog');self.assertEqual(result['valid_frames'],2)
    def test_project_and_flow_names_are_not_model_identification(self):
        result=analyze_dji_log('"project":"WM162"\nitem name: main:GetPerceptionSN:SN:unknown')
        self.assertEqual(result['historical_context']['project_names'],['WM162'])
        self.assertFalse(result['historical_context']['marketing_model_confirmed'])
        self.assertEqual(result['state'],'desconocido')
    def test_cancellation_and_record_limits(self):
        text=log_pair(self.command,self.ack)
        with self.assertRaises(InterruptedError):analyze_dji_log(text,lambda:True)
        with patch('vision_history.LIMIT',1),self.assertRaises(ValueError):analyze_dji_log(text)
