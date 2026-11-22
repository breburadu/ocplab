import sys
import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('lab',ROOT/'scripts/lab.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.c=json.loads((ROOT/'config/lab.example.json').read_text())
        self.c['work_dir']=self.tmp.name+'/work'
        self.lab=mod.Lab(self.c)
    def tearDown(self): self.tmp.cleanup()
    def test_defaults(self): mod.valid_config(self.c)
    def test_duplicate_ip_rejected(self):
        self.c['nodes'][1]['ip']=self.c['nodes'][0]['ip']
        with self.assertRaises(AssertionError): mod.valid_config(self.c)
    def test_overlap_rejected(self):
        self.c['service_cidr']=self.c['network']['cidr']
        with self.assertRaises(AssertionError): mod.valid_config(self.c)
    def test_isolation_has_no_nat(self):
        self.lab.net['isolate_guests']=True
        x=ET.fromstring(self.lab.network_xml()); self.assertIsNone(x.find('forward'))
        self.assertEqual(len(x.findall('ip/dhcp/host')),4)
    def test_vm_install_to_disk_transition(self):
        n=self.c['nodes'][0]
        initial=ET.fromstring(self.lab.domain_xml(n,True)); final=ET.fromstring(self.lab.domain_xml(n,False))
        self.assertIn('coreos.inst.image_url=http://',initial.findtext('os/cmdline'))
        self.assertIn('coreos.inst.console=ttyS0',initial.findtext('os/cmdline'))
        self.assertEqual(initial.findtext('on_reboot'),'destroy')
        self.assertEqual(final.findtext('on_reboot'),'restart')
        self.assertIsNone(final.find('os/kernel'))
        self.assertEqual(final.find('devices/disk/driver').get('type'),'raw')
    def test_haproxy_no_frontend_server_and_cleanup(self):
        with patch.object(mod,'write') as w, patch.object(mod,'run'):
            self.lab.haproxy(True); text=w.call_args_list[0].args[1]
            section=''
            for line in text.splitlines():
                if line.startswith(('backend','frontend')): section=line
                if line.strip().startswith('server '): self.assertTrue(section.startswith('backend'))
            self.assertEqual(text.count('server '+self.c['bootstrap']['name']),2)
            self.lab.haproxy(False); text=w.call_args_list[-2].args[1]
            self.assertNotIn('server '+self.c['bootstrap']['name'],text)
    def test_atomic_write_and_hash(self):
        p=Path(self.tmp.name)/'file'; mod.write(p,'test')
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertEqual(mod.sha(p),'9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08')
    def test_config_never_includes_pull_secret(self):
        self.assertNotIn('auths',json.dumps(self.c))

if __name__=='__main__': unittest.main()
