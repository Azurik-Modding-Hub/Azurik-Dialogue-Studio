import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import iso_export
from xbox_iso import XboxISO, MAGIC, SECTOR


def sha(data):return hashlib.sha256(data).hexdigest()


def xbr(marker=b'language-original'):
    data=bytearray(64)+marker
    struct.pack_into('<4sIIII',data,0,b'xobx',4,0,0,64)
    return bytes(data)


def table(rows):
    # Independent unbalanced directory fixture; the production writer uses
    # a balanced tree. Child links are four-byte offsets, not byte offsets.
    rows=sorted(rows,key=lambda row:row[0].lower())
    output=bytearray(b'\xff'*SECTOR)
    for i,(name,sector,size,flags) in enumerate(rows):
        at=i*64;raw=name.encode('ascii')
        struct.pack_into('<HHIIBB',output,at,0,(i+1)*16 if i+1<len(rows) else 0,sector,size,flags,len(raw))
        output[at+14:at+14+len(raw)]=raw
    return output


def fixture(path):
    exe=bytearray(512);exe[:4]=b'XBEH'
    struct.pack_into('<I',exe,0x104,0x10000)
    struct.pack_into('<I',exe,0x118,0x10178)
    struct.pack_into('<I',exe,0x180,0x4D530007)
    title='Azurik - Rise of Perathia'.encode('utf-16-le')
    exe[0x184:0x184+len(title)]=title
    files={'default.xbe':bytes(exe),'gamedata/town.xbr':xbr(b'town-original'),
           'gamedata/French.xbr':xbr(),'movie.bik':b'unchanged synthetic movie'}
    disc=bytearray(41*SECTOR)
    desc=bytearray(SECTOR);desc[:20]=desc[-20:]=MAGIC
    struct.pack_into('<II',desc,20,34,SECTOR)
    disc[32*SECTOR:33*SECTOR]=desc
    disc[34*SECTOR:35*SECTOR]=table([('default.xbe',36,len(files['default.xbe']),0x21),
        ('GameData',35,SECTOR,0x10),('movie.bik',39,len(files['movie.bik']),0x22)])
    disc[35*SECTOR:36*SECTOR]=table([('town.xbr',37,len(files['gamedata/town.xbr']),0x20),
        ('French.xbr',38,len(files['gamedata/French.xbr']),0x21)])
    sectors={'default.xbe':36,'gamedata/town.xbr':37,'gamedata/French.xbr':38,'movie.bik':39}
    for key,data in files.items():
        offset=sectors[key]*SECTOR
        disc[offset:offset+len(data)]=data
    path.write_bytes(disc)
    return files,bytes(disc)


def stage(root,path,original,modified,**extra):
    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(modified)
    result={'format':'azurik-level-iso','version':1,'gameFiles':[
        dict(path=path,sha256=sha(modified),sourceSha256=sha(original) if original is not None else None)]}
    result.update(extra)
    (root/'iso-plan.json').write_text(json.dumps(result),encoding='utf-8')
    return result


def contents(path):
    image=XboxISO(path)
    result={}
    with path.open('rb') as stream:
        for entry in image.entries:
            if entry['directory']:continue
            stream.seek(image._extent(entry['sector'],entry['size']))
            result[entry['path'].casefold()]=stream.read(entry['size'])
    return result


class ISOExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.source=self.root/'original.iso'
        self.files,self.original=fixture(self.source)
        self.export=self.root/'export'
        self.changed=xbr(b'French-dialogue-and-voice-edited')
        stage(self.export,'gamedata/French.xbr',self.files['gamedata/French.xbr'],self.changed)

    def tearDown(self):self.tmp.cleanup()

    def test_language_bank_replacement_reloads_and_preserves_original_game(self):
        destination=self.root/'modified.iso';progress=[]
        report=iso_export.build_iso(self.source,self.export,destination,lambda value,stage:progress.append(value))
        actual=contents(destination)
        self.assertEqual(actual['gamedata/french.xbr'],self.changed)
        self.assertEqual(actual['default.xbe'],self.files['default.xbe'])
        self.assertEqual(actual['gamedata/town.xbr'],self.files['gamedata/town.xbr'])
        self.assertEqual(actual['movie.bik'],self.files['movie.bik'])
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertTrue(report['sourceUnchanged'])
        self.assertTrue(report['executableUnchanged'])
        self.assertFalse(report['imageTestedInGame'])
        self.assertEqual(report['isoSha256'],sha(destination.read_bytes()))
        self.assertEqual(progress[-1],100)
        self.assertEqual(report['editor'],'Azurik Dialogue Studio')

    def test_original_iso_cannot_be_the_destination(self):
        with self.assertRaises(ValueError):iso_export.build_iso(self.source,self.export,self.source)
        self.assertEqual(self.source.read_bytes(),self.original)

    def test_existing_destination_is_preserved(self):
        destination=self.root/'existing.iso';destination.write_bytes(b'keep this file')
        with self.assertRaises(ValueError):iso_export.build_iso(self.source,self.export,destination)
        self.assertEqual(destination.read_bytes(),b'keep this file')

    def test_source_bank_hash_must_match_actual_selected_iso(self):
        stage(self.export,'gamedata/French.xbr',b'wrong original bank',self.changed)
        destination=self.root/'modified.iso'
        with self.assertRaisesRegex(ValueError,'source diffère'):iso_export.build_iso(self.source,self.export,destination)
        self.assertFalse(destination.exists())

    def test_staged_payload_hash_checked_before_output(self):
        (self.export/'gamedata/French.xbr').write_bytes(xbr(b'tampered staged bank'))
        destination=self.root/'modified.iso'
        with self.assertRaises(ValueError):iso_export.build_iso(self.source,self.export,destination)
        self.assertFalse(destination.exists())

    def test_other_asset_or_executable_edits_are_rejected(self):
        for path in ('gamedata/town.xbr','default.xbe'):
            stage(self.export,path,b'original',xbr(b'edited'))
            with self.assertRaises(ValueError):iso_export.inspect_export(self.export)

    def test_language_additions_and_level_operations_are_rejected(self):
        stage(self.export,'gamedata/German.xbr',None,xbr())
        with self.assertRaises(ValueError):iso_export.inspect_export(self.export)
        stage(self.export,'gamedata/French.xbr',self.files['gamedata/French.xbr'],self.changed,
              levelOperations={'created':[{'id':'custom','template':'town'}],'deleted':[]})
        with self.assertRaises(ValueError):iso_export.inspect_export(self.export)

    def test_path_traversal_and_duplicate_plan_rows_rejected(self):
        plan=json.loads((self.export/'iso-plan.json').read_text())
        plan['gameFiles'][0]['path']='gamedata/../French.xbr'
        (self.export/'iso-plan.json').write_text(json.dumps(plan))
        with self.assertRaises(ValueError):iso_export.inspect_export(self.export)
        plan=stage(self.export,'gamedata/French.xbr',self.files['gamedata/French.xbr'],self.changed)
        plan['gameFiles'].append(plan['gameFiles'][0])
        (self.export/'iso-plan.json').write_text(json.dumps(plan))
        with self.assertRaises(ValueError):iso_export.inspect_export(self.export)


if __name__=='__main__':unittest.main()
