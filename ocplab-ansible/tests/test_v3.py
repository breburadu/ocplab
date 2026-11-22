import json, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import hardware, modules, exposure, lab
ROOT=Path(__file__).resolve().parents[1]
class V3(unittest.TestCase):
    def config(self):
        return json.loads((ROOT/'config/lab.example.json').read_text())
    def test_distro_detection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'os-release'
            for ident,family in [('debian','debian'),('ubuntu','debian'),('rhel','redhat'),('fedora','redhat'),('other',None)]:
                p.write_text('ID='+ident+'\nVERSION_ID="12"\n')
                self.assertEqual(hardware.distro(p)['family'],family)
    def test_hardware_does_not_shrink_masters(self):
        r=hardware.recommend(32000,4,200)
        self.assertFalse(r['recommended_for_this_automation'])
        self.assertEqual(r['per_node']['memory_mib'],16384)
        self.assertEqual(hardware.recommend(100000,16,1000)['minimum_peak_ram_mib'],69632)
    def test_modules_core_only(self):
        c=self.config(); c['modules']['selected']=['core']; modules.normalize(c)
        self.assertFalse(c['virtualization']['enabled']); self.assertFalse(c['storage']['enabled'])
    def test_modules_dependency_rejected(self):
        c=self.config(); c['modules']['selected']=['core','storage']
        with self.assertRaises(AssertionError): modules.normalize(c)
    def test_unknown_module_rejected(self):
        c=self.config(); c['modules']['selected']=['core','anything']
        with self.assertRaises(AssertionError): modules.normalize(c)
    def test_nat_default_and_explicit_dns_forwarders(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.config(); c['work_dir']=d+'/work'; obj=lab.Lab(c)
            xml=lab.ET.fromstring(obj.network_xml())
            self.assertEqual(xml.find('forward').get('mode'),'nat')
            self.assertEqual(len(xml.findall('dns/forwarder')),2)
    def test_exposure_requires_acl_and_rejects_reserved_port(self):
        c=self.config(); c['exposure']['lan_ips']=['10.20.30.40']
        with self.assertRaises(AssertionError): exposure.settings(c)
        c['exposure']['allowed_cidrs']=['10.20.30.0/24']
        exposure.settings(c)
        c['exposure']['tcp_forwards']=[{'name':'ssh','host':'192.168.123.11','port':22,'listen_port':22623}]
        with self.assertRaises(AssertionError): exposure.settings(c)
    def test_haproxy_keeps_machine_config_internal(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.config(); c['work_dir']=d+'/work'
            c['exposure'].update(lan_ips=['10.20.30.40'],allowed_cidrs=['10.20.30.0/24'])
            obj=lab.Lab(c)
            with patch.object(lab,'write') as w,patch.object(lab,'run'):
                obj.haproxy(False); text=w.call_args_list[0].args[1]
            self.assertIn('bind 10.20.30.40:6443',text)
            self.assertNotIn('bind 10.20.30.40:22623',text)
    def test_wait_recovers_transient_api_error(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.config(); c['work_dir']=d+'/work'; obj=lab.Lab(c)
            with patch.object(obj,'progress'),patch('lab.time.sleep'),patch('lab.time.monotonic',side_effect=range(100)),patch('sys.stdout'):
                check=unittest.mock.Mock(side_effect=[RuntimeError('EOF'),True])
                obj.wait_for('test',check,60)
                self.assertEqual(check.call_count,2)
    def test_published_service_uses_nodes_not_pod_ips(self):
        with tempfile.TemporaryDirectory() as d:
            c=self.config(); c['work_dir']=d+'/work'; item={'name':'web','namespace':'demo','service':'web','port':8080,'listen_port':18080}
            c['exposure']['services']=[item]; obj=lab.Lab(c)
            (obj.w/'published-services.json').write_text(json.dumps([{'config':item,'node_port':31080}]))
            text=exposure.proxy_text(obj)
            for node in c['nodes']: self.assertIn(node['ip']+':31080',text)
            self.assertNotIn('10.128.',text)
if __name__=='__main__': unittest.main()
