import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from studio_protocol import checksum
from studio_service import packet
from vision_packages import inspect_package, parse_manifest
from vision_protocol import CaptureDecoder, decode_bytes, analyze_capture
from vision_interfaces import UnavailableIdentification, LocalCalibrationProvider
from vision_services import service_target, probe_server, _connect_tls, AuthorizedServiceProvider

# Real byte sequence supplied in this conversation for a different drone/gimbal.
# This is NOT evidence of Mini 4 Pro endpoints, command effects or 150 ACKs.
USER_FRAME=bytes.fromhex('55 0e 04 66 04 0a 8e ad 80 04 08 01 fb 95')

class PackageTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def package(self):
        (self.root/'sensor.bin').write_bytes(b'unit-specific-example')
        digest=hashlib.md5(b'unit-specific-example',usedforsecurity=False).hexdigest()
        (self.root/'MD5SUMS').write_text(digest+'  sensor.bin\n')
        return digest
    def test_directory_md5_and_sha_do_not_enable_compatibility(self):
        self.package();report=inspect_package(self.root)
        self.assertEqual(report['integrity']['state'],'confirmado')
        self.assertFalse(report['integrity']['md5_authenticates'])
        self.assertEqual(LocalCalibrationProvider().compatibility(report,None).state,'desconocido')
        self.assertEqual(report['device_writes'],0)
        self.assertEqual(len(LocalCalibrationProvider().candidates(report)),1)
    def test_zip_inventory_does_not_extract_or_execute(self):
        self.package();archive=self.root/'package.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name in ('sensor.bin','MD5SUMS'):z.write(self.root/name,name)
            z.writestr('DJI Test.exe',b'not executable test data')
        before=set(self.root.iterdir());report=inspect_package(archive)
        self.assertEqual(set(self.root.iterdir()),before)
        self.assertEqual(report['executed_files'],0)
        self.assertEqual(report['extracted_files'],0)
        self.assertEqual(report['integrity']['state'],'desconocido') # EXE not covered
    def test_mismatch_missing_and_malformed_manifest_are_errors(self):
        self.package();(self.root/'sensor.bin').write_bytes(b'changed')
        self.assertEqual(inspect_package(self.root)['integrity']['state'],'error')
        (self.root/'sensor.bin').unlink()
        self.assertEqual(inspect_package(self.root)['integrity']['checks'][0]['state'],'falta')
        (self.root/'MD5SUMS').write_text('please run DJI Test.exe')
        self.assertEqual(inspect_package(self.root)['integrity']['state'],'error')
    def test_no_manifest_is_unknown(self):
        (self.root/'data.bin').write_bytes(b'data')
        self.assertEqual(inspect_package(self.root)['integrity']['state'],'desconocido')
    def test_gnu_bsd_relative_paths_and_bad_paths(self):
        digest='a'*32
        entries,errors=parse_manifest(f'{digest} *sensor.bin\nMD5 (camera.bin) = {digest}\n{digest} ../escape.bin','sub/MD5SUMS')
        self.assertEqual([e['path'] for e in entries],['sub/sensor.bin','sub/camera.bin'])
        self.assertEqual(len(errors),1)
    def test_archive_traversal_absolute_and_windows_drive_rejected(self):
        for name in ('../escape.bin','/absolute.bin','C:\\escape.bin','sub\\..\\escape.bin'):
            with self.subTest(name=name):
                archive=self.root/'bad.zip'
                with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'test')
                with self.assertRaises(ValueError):inspect_package(archive)
    def test_duplicate_windows_names_rejected(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('sensor.bin',b'a');z.writestr('SENSOR.BIN',b'b')
        with self.assertRaises(ValueError):inspect_package(archive)
    def test_symlink_archive_rejected(self):
        archive=self.root/'bad.zip';entry=zipfile.ZipInfo('linked.bin');entry.create_system=3
        entry.external_attr=(stat.S_IFLNK|0o777)<<16
        with zipfile.ZipFile(archive,'w') as z:z.writestr(entry,'outside.bin')
        with self.assertRaises(ValueError):inspect_package(archive)
    @unittest.skipIf(os.name=='nt','Local symlink creation may require Windows privileges')
    def test_directory_symlinks_are_not_followed(self):
        self.package();(self.root/'link').symlink_to(self.root/'sensor.bin')
        report=inspect_package(self.root)
        self.assertEqual(report['integrity']['state'],'error')
        self.assertNotIn('link',[f['path'] for f in report['files']])
    def test_size_limit_and_cancellation(self):
        self.package()
        with patch('vision_packages.MAX_FILE',2),self.assertRaises(ValueError):inspect_package(self.root)
        with self.assertRaises(InterruptedError):inspect_package(self.root,cancelled=lambda:True)
    def test_cancellation_during_last_file_is_not_swallowed(self):
        (self.root/'data.bin').write_bytes(b'data');calls=0
        def cancel():
            nonlocal calls
            calls+=1
            return calls>=3
        with self.assertRaises(InterruptedError):inspect_package(self.root,cancelled=cancel)

class FramingTests(unittest.TestCase):
    def test_real_user_sample_verifies_framing_only(self):
        result=decode_bytes(USER_FRAME)
        self.assertEqual(result['valid_frames'],1);self.assertEqual(result['issue_count'],0)
        self.assertEqual(result['frames_preview'][0]['payload_raw'],'01')
        self.assertEqual(result['frames_preview'][0]['command_meaning'],'desconocido')
        self.assertEqual(result['identity']['state'],'desconocido')
    def test_concatenated_duplicate_and_incremental_frames(self):
        other=packet(10,4,17,0,1,b'')
        result=decode_bytes(USER_FRAME+USER_FRAME+other)
        self.assertEqual(result['valid_frames'],3);self.assertEqual(result['distinct_frames'],2)
        decoder=CaptureDecoder()
        for byte in USER_FRAME:decoder.feed(bytes([byte]))
        decoder.feed(b'',final=True)
        self.assertEqual(decoder.result()['valid_frames'],1)
    def test_truncation_at_every_boundary(self):
        for size in range(1,len(USER_FRAME)):
            result=decode_bytes(USER_FRAME[:size])
            self.assertEqual(result['valid_frames'],0);self.assertEqual(result['state'],'error')
    def test_bad_header_and_frame_crc_recover_next_frame(self):
        for index in (3,-1):
            bad=bytearray(USER_FRAME);bad[index]^=1
            result=decode_bytes(bytes(bad)+USER_FRAME)
            self.assertEqual(result['valid_frames'],1);self.assertGreater(result['issue_count'],0)
    def test_incorrect_length_with_valid_header_crc_recovers_next_frame(self):
        bad=bytearray(USER_FRAME);bad[1:3]=(900|1024).to_bytes(2,'little');bad[3]=checksum(bad[:3],0x77,0x8c)
        result=decode_bytes(bytes(bad)+USER_FRAME)
        self.assertEqual(result['valid_frames'],1)
        self.assertIn('truncada',[x['kind'] for x in result['issues_preview']])
    def test_noise_empty_and_too_short_length(self):
        self.assertEqual(decode_bytes(b'')['state'],'desconocido')
        self.assertEqual(decode_bytes(b'noise'+USER_FRAME)['valid_frames'],1)
        self.assertEqual(decode_bytes(b'\x55\x01\x04\0')['state'],'error')
    def test_text_logs_utf16_hex_dump_and_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);log=root/'capture.log'
            for seconds in ('11','55'):
                log.write_text('2026-10-23 09:10:'+seconds+' RX: '+USER_FRAME.hex(' ')+'\nUnrecognized text\n',encoding='utf-8')
                result=analyze_capture(log)
                self.assertEqual(result['valid_frames'],1);self.assertEqual(result['ignored_text_lines'],1)
            self.assertIn('Sin verificar',result['initial_150_ack_claim'])
            log.write_text('0000: '+USER_FRAME[:7].hex(' ')+' | ASCII\n0007: '+USER_FRAME[7:].hex(' ')+' | ASCII',encoding='utf-16')
            self.assertEqual(analyze_capture(log,'hexlog')['valid_frames'],1)
            with_payload_55=packet(4,10,1,0,1,b'\x11\x55\x33\x44\x66\x77')
            log.write_text('0000: '+with_payload_55[:11].hex(' ')+'\n000b: '+with_payload_55[11:].hex(' '))
            self.assertEqual(analyze_capture(log,'hexlog')['valid_frames'],1)
            binary=root/'capture.bin';binary.write_bytes(USER_FRAME)
            self.assertEqual(analyze_capture(binary)['valid_frames'],1)
    def test_unknown_log_format_is_not_a_healthy_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'log.txt';file.write_text('No packets; run unknown software')
            report=analyze_capture(file)
            self.assertEqual(report['state'],'desconocido');self.assertEqual(report['valid_frames'],0)

class ServiceTests(unittest.TestCase):
    def test_identity_and_download_remain_unavailable(self):
        self.assertEqual(UnavailableIdentification().identify().state,'desconocido')
        with self.assertRaises(NotImplementedError):AuthorizedServiceProvider('https://authorized.example:8443').download()
    def test_urls_with_credentials_queries_insecure_scheme_and_bad_ports_rejected(self):
        for url in ('http://example.com','https://user:password@example.com','https://example.com/?token=secret','https://example.com/#secret','https://example.com:0','https://example.com:99999'):
            with self.subTest(url=url),self.assertRaises(ValueError):service_target(url)
        self.assertEqual(service_target('https://example.com:8443/path'),('example.com',8443))
    def test_probe_deadline_covers_dns_and_preserves_no_download_state(self):
        with patch('vision_services.subprocess.run',side_effect=subprocess.TimeoutExpired('probe',.5)) as run:
            report=probe_server('https://authorized.example',.5)
        self.assertEqual(report['state'],'error');self.assertFalse(report['download_enabled'])
        self.assertEqual(run.call_args.kwargs['timeout'],.5)
        self.assertEqual(run.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'0')
    def test_windowed_worker_uses_files_and_no_gui(self):
        def child(command,**options):
            data=json.loads(Path(command[-2]).read_text())
            self.assertEqual(data['host'],'authorized.example')
            Path(command[-1]).write_text(json.dumps({'state':'confirmado','detail':'TLS only'}))
            return SimpleNamespace(returncode=0)
        with patch('vision_services.subprocess.run',side_effect=child):
            report=probe_server('https://authorized.example',3)
        self.assertEqual(report['state'],'confirmado')
    def test_tcp_tls_success_does_not_mean_authentication_or_calibration(self):
        with patch('vision_services.ssl.create_default_context') as context,patch('vision_services.socket.create_connection'):
            report=_connect_tls('authorized.example',8443,.5)
        context.assert_called_once_with()
        self.assertEqual(report['state'],'confirmado');self.assertEqual(report['authentication'],'desconocido')
        self.assertFalse(report['download_enabled'])
    def test_certificate_failure_is_error_and_verification_not_disabled(self):
        import ssl
        with patch('vision_services.ssl.create_default_context') as context,patch('vision_services.socket.create_connection'):
            context.return_value.wrap_socket.side_effect=ssl.SSLCertVerificationError('bad certificate')
            report=_connect_tls('authorized.example',8443,.5)
        self.assertEqual(report['state'],'error')
    def test_out_of_range_timeout_rejected_before_subprocess(self):
        with patch('vision_services.subprocess.run') as run:
            for value in (0,11,float('nan')):
                with self.assertRaises(ValueError):probe_server('https://example.com',value)
        run.assert_not_called()

if __name__=='__main__':unittest.main()
