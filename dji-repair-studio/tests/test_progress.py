import unittest
from studio_service import Session
from studio_app import ProgressState
from test_service import Clock, Transport, reply, status

class ProgressTests(unittest.TestCase):
    def run_session(self, frames, action='JointCoarse'):
        events=[]
        t=Transport(lambda req:[reply(req,b'\x01' if action=='JointCoarse' else b'\0')+b''.join(status(x) for x in frames)])
        result=Session(t,clock=Clock(),progress=events.append).calibrate(action)
        return result,events

    def test_progress_counts_distinct_matching_stages_and_terminal(self):
        _,events=self.run_session([b'\x52\1',b'\x52\1',b'\x53\1',b'\x11\1',b'\x64\0'])
        self.assertEqual([e['percent'] for e in events],[20,20,40,100])
        self.assertEqual(events[-1]['label'],'Fin informado por el equipo')

    def test_hall_uses_its_own_milestones(self):
        _,events=self.run_session([b'\x11\1',b'\x12\1',b'\x14\1',b'\x16\1',b'\x17\1',b'\x64\0'],'LinearHall')
        self.assertEqual([e['percent'] for e in events],[16,33,50,66,83,100])

    def test_ack_or_failed_calibration_never_fakes_100(self):
        for frames,error in (([],TimeoutError),([b'\x52\1',b'\x64\3'],RuntimeError)):
            events=[]
            t=Transport(lambda req:[reply(req,b'\1')+b''.join(status(x) for x in frames)])
            with self.assertRaises(error):Session(t,clock=Clock(),progress=events.append).calibrate('JointCoarse')
            self.assertNotIn(100,[e['percent'] for e in events])

    def test_partial_factory_exit_never_shows_full_confirmation(self):
        events=[]
        t=Transport(lambda req:[reply(req,b'\xfb' if req[5]==0x8f else b'\0')])
        with self.assertRaises(RuntimeError):Session(t,clock=Clock(),progress=events.append).factory(False)
        self.assertEqual([e['percent'] for e in events],[50])

    def test_factory_success_requires_both_confirmations(self):
        events=[]
        Session(Transport(lambda req:[reply(req)]),clock=Clock(),progress=events.append).factory(True)
        self.assertEqual([e['percent'] for e in events],[50,100])

    def test_worker_finish_never_implies_full_calibration(self):
        state=ProgressState()
        state.update({'mode':'determinate','percent':40})
        state.update({'mode':'determinate','percent':20})
        state.finish(False,'Timeout')
        state.update({'mode':'determinate','percent':100})
        self.assertEqual(state.value,40)
        state.reset();state.finish(True,'No quantitative data')
        self.assertFalse(state.measured)
        self.assertEqual(state.value,0)
