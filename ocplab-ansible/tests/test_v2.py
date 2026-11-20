import io, json, os, subprocess, sys, tarfile, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import lab
import storage
ROOT=Path(__file__).resolve().parents[1]

class V2(unittest.TestCase):
    def test_tar_symlink_and_hardlink_are_readable(self):
        for kind in [tarfile.SYMTYPE,tarfile.LNKTYPE]:
            stream=io.BytesIO()
            with tarfile.open(fileobj=stream,mode='w') as t:
                m=tarfile.TarInfo('oc'); data=b'binary';m.size=len(data);t.addfile(m,io.BytesIO(data))
                m=tarfile.TarInfo('kubectl');m.type=kind;m.linkname='oc';t.addfile(m)
            stream.seek(0)
            with tarfile.open(fileobj=stream) as t:
                members=[m for m in t.getmembers() if Path(m.name).name=='kubectl' and (m.isfile() or m.islnk() or m.issym())]
                self.assertEqual(t.extractfile(members[0]).read(),b'binary')
    def test_resume_vm_preserves_uuid(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/lab.example.json').read_text())
            c['work_dir']=d+'/work';c['disk_dir']=d+'/disks'
            l=lab.Lab(c);n=c['bootstrap'];l.nodes=[n]
            for marker in ['ignition','owned-'+n['name']]:l.mark(marker)
            for kind in ['kernel','initramfs']:lab.write(l.w/'http/rhcos'/kind,b'boot')
            def vir(*args,**kwargs):
                if args[0]=='domstate':return 'shut off'
                if args[0]=='domuuid':return '1cefc924-9d3d-4da6-8be0-98ad45aab3f1'
                return ''
            from types import SimpleNamespace
            with patch.object(l,'preflight'),patch.object(l,'crash_guard'),patch.object(l,'inspect_installed_disk'),patch.object(l,'vir',side_effect=vir),patch.object(l,'ssh',return_value=SimpleNamespace(returncode=0)):
                l.vms()
            root=lab.ET.fromstring((l.w/(n['name']+'-disk.xml')).read_text())
            self.assertEqual(root.findtext('uuid'),'1cefc924-9d3d-4da6-8be0-98ad45aab3f1')
            self.assertIsNone(root.find('os/kernel'))
    def test_attachment_parser(self):
        xml='<domain><devices>'+storage.disk_xml('/tmp/node-data.raw')+'</devices></domain>'
        self.assertEqual(storage.attachments(xml),{'vdb':'/tmp/node-data.raw'})
    def test_guest_script_syntax(self):
        p=subprocess.run(['bash','-n'],input=storage.guest_script(80*1024**3,False),text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('allow_format=0',storage.guest_script(1,False))
        self.assertNotIn('mkfs.xfs -f',storage.guest_script(1,True))
    def test_os_disk_rejected(self):
        class L: c={'storage':{'target':'vda'}}
        with self.assertRaises(AssertionError): storage.settings(L())
    def test_catalog_patch_uses_nonroot_and_distinct_tag(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/lab.example.json').read_text());c['work_dir']=d+'/work'
            l=lab.Lab(c)
            cat={'spec':{'image':'mirror:5000/redhat/index:v4.22'}}
            with patch.object(l,'logrun') as log,patch.object(lab,'run',return_value='sha256:abcdef'):
                result=l.fix_catalog(cat)
            self.assertEqual(result['spec']['image'],'mirror:5000/redhat/index:v4.22-permissions-fixed')
            content=(l.w/'catalog-permissions-fix/Containerfile').read_text()
            self.assertIn('chmod -R a+rX /configs',content);self.assertTrue(content.endswith('USER 1001\n'))
            self.assertEqual(log.call_count,3)
    def test_logrun_streams_and_redacts_password(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/lab.example.json').read_text());c['work_dir']=d+'/work';l=lab.Lab(c)
            with patch('sys.stdout',new_callable=io.StringIO) as out:
                l.logrun([sys.executable,'-c','print("progress");print("password: secret123")'],'fake',10)
            content=next((l.w/'logs').glob('fake-*')).read_text()
            self.assertIn('progress',content);self.assertNotIn('secret123',content);self.assertNotIn('secret123',out.getvalue())
    def test_upgrade_preserves_identity_and_adopts(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/lab.example.json').read_text());c['work_dir']=d+'/work'; c.pop('storage');c['virtualization'].pop('fix_catalog_permissions')
            work=Path(c['work_dir']);(work/'state').mkdir(parents=True)
            lock=work/'state/config.sha256';lock.write_text(lab.hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest())
            config=Path(d)/'lab.json';config.write_text(json.dumps(c))
            p=subprocess.run([sys.executable,str(ROOT/'scripts/upgrade_config.py'),str(config),'--adopt-storage'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            new=json.loads(config.read_text());self.assertTrue(new['storage']['adopt_existing_disks'])
            for k in c:
                if k!='virtualization': self.assertEqual(new[k],c[k])
            self.assertEqual(lock.read_text().strip(),lab.hashlib.sha256(json.dumps(new,sort_keys=True).encode()).hexdigest())
    def test_upgrade_refuses_wrong_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            c=json.loads((ROOT/'config/lab.example.json').read_text());c['work_dir']=d+'/work'
            work=Path(c['work_dir']);(work/'state').mkdir(parents=True);(work/'state/config.sha256').write_text('invalid')
            config=Path(d)/'lab.json';config.write_text(json.dumps(c));original=config.read_bytes()
            p=subprocess.run([sys.executable,str(ROOT/'scripts/upgrade_config.py'),str(config)],capture_output=True)
            self.assertNotEqual(p.returncode,0);self.assertEqual(config.read_bytes(),original)
    def test_screen_launcher_two_windows(self):
        with tempfile.TemporaryDirectory() as d:
            stub=Path(d)/'screen';record=Path(d)/'calls'
            stub.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$SCREEN_TEST_LOG"\nif [ "$1" = -ls ]; then exit 1; fi\n')
            stub.chmod(0o755)
            c=Path(d)/'lab.json';c.write_text('{}')
            env={**os.environ,'PATH':d+':'+os.environ['PATH'],'SCREEN_TEST_LOG':str(record),'OCP_SCREEN_SESSION':'test-launch'}
            p=subprocess.run(['bash',str(ROOT/'start-screen.sh'),str(c),'storage','validate'],env=env,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            calls=record.read_text();self.assertIn('-t installer',calls);self.assertIn('-t logs',calls);self.assertIn('storage validate',calls)

if __name__=='__main__':unittest.main()
