import io
import math
import struct
import unittest
import wave
from array import array

import audio_formats as audio


def archive(*,streamed=True,shared=False,channels=2,bits=4,codec=1,frames=128):
    count=3 if shared else 2
    base=4096
    pcm=struct.pack('<'+'h'*(frames*channels),*([0]*(frames*channels)))
    payload=audio.encode_xbox_adpcm(pcm,channels) if codec==1 else pcm
    if not streamed:
        descriptor=struct.pack('<II4BI',22050,frames//channels if codec==1 else frames,channels,bits,0,codec,0)+payload
        items=[(b'wave',descriptor,8)]
        names=[(0,b'loc/french/speech/eld_level_intros/test')]
    else:
        descriptor=struct.pack('<II4BII',22050,frames//channels if codec==1 else frames,channels,bits,1,codec,0,0)
        items=[(b'sdsr',payload,16),(b'wave',descriptor,8)]
        names=[(1,b'loc/french/speech/eld_level_intros/test')]
        if shared:
            items.append((b'wave',descriptor,8))
            names.append((2,b'loc/french/speech/eld_level_intros/other'))
    count=len(items)
    footer=((base+sum((len(data)+3)&~3 for tag,data,flags in items)+4095)//4096)*4096
    result=bytearray(footer)
    relocation_count=sum(tag==b'wave' and data[10]==1 for tag,data,flags in items)
    loaders=b''.join(struct.pack('<4sI',tag,flag) for tag,flag in [(b'wave',4),(b'surf',4),(b'sdsr',0)])
    relocation_offset=footer+len(loaders)
    names_offset=relocation_offset+relocation_count*4
    struct.pack_into('<4sIIIIIII',result,0,b'xobx',4,0,count,base,3,footer,relocation_count)
    struct.pack_into('<III',result,32,relocation_offset,0,names_offset)
    pool=bytearray();nametable=bytearray()
    for index,key in names:
        nametable+=struct.pack('<II',index,len(pool));pool+=key+b'\0'
    struct.pack_into('<IIII',result,44,len(names),names_offset,names_offset+len(nametable),len(pool))
    position=0
    relocations=bytearray()
    for index,(tag,data,flags) in enumerate(items):
        result[base+position:base+position+len(data)]=data
        end=(position+len(data)+3)&~3
        struct.pack_into('<I4sII',result,64+index*16,len(data),tag,flags,end)
        if tag==b'wave' and data[10]==1:relocations+=struct.pack('<I',position+16)
        position=end
    result+=loaders+relocations+nametable+pool
    return bytes(result)


def wav(frames,rate=22050,channels=1,width=2):
    out=io.BytesIO()
    raw=(b'\x80' if width==1 else b'\0'*width)*frames*channels
    with wave.open(out,'wb') as dest:
        dest.setnchannels(channels);dest.setsampwidth(width);dest.setframerate(rate);dest.writeframes(raw)
    return out.getvalue()


class AudioFormatsTests(unittest.TestCase):
    key='loc/french/speech/eld_level_intros/test'

    def test_exact_native_name_and_stream_reference(self):
        meta=audio.list_voices(archive())[0]
        self.assertEqual(meta['key'],self.key)
        self.assertEqual(meta['resourceIndex'],1)
        self.assertEqual(meta['dataResourceIndex'],0)
        self.assertEqual(meta['dataOffset'],4096)
        self.assertEqual(meta['frames'],128)
        self.assertTrue(meta['streamed'])

    def test_unedited_source_bytes_are_untouched(self):
        original=archive()
        voices=audio.list_voices(original)
        self.assertEqual(original,archive())
        self.assertTrue(voices[0]['editable'])

    def test_replacement_preserves_descriptor_toc_names_and_size(self):
        original=archive()
        pcm=struct.pack('<'+'h'*64,*[round(10000*math.sin(i/5)) for i in range(64)])
        imported=audio.pcm_wav(pcm,22050,1)
        patched,info=audio.replace_voice(original,self.key,imported,preserve_allocation=True)
        self.assertEqual(len(original),len(patched))
        start,end=info['dataOffset'],info['dataOffset']+info['dataSize']
        self.assertEqual(original[:start],patched[:start])
        self.assertEqual(original[end:],patched[end:])
        self.assertNotEqual(original[start:end],patched[start:end])
        decoded,meta=audio.voice_pcm(patched,self.key)
        samples=struct.unpack('<'+'h'*(len(decoded)//2),decoded)
        self.assertEqual(samples[128:],tuple([0]*128))
        self.assertEqual(samples[::2],samples[1::2])
        self.assertEqual(meta['originalCounter'],64)

    def test_long_recording_rejected_without_truncation(self):
        with self.assertRaisesRegex(ValueError,'trop long'):
            audio.replace_voice(archive(),self.key,wav(129),preserve_allocation=True)

    def test_resample_and_channels(self):
        patched,info=audio.replace_voice(archive(),self.key,wav(128,44100,1))
        self.assertTrue(info['resampled'])
        self.assertTrue(info['channelConverted'])
        self.assertEqual(info['targetFrames'],64)
        self.assertEqual(len(patched),len(archive()))

    def test_partial_encoder_block_is_padded_not_discarded(self):
        encoded=audio.encode_xbox_adpcm(struct.pack('<h',1234),1)
        decoded=audio.decode_xbox_adpcm(encoded,1)
        self.assertEqual(len(encoded),36)
        self.assertEqual(len(decoded),128)
        self.assertEqual(struct.unpack_from('<h',decoded)[0],1234)

    def test_codec_sine_quality_and_stereo_independence(self):
        samples=[round(12000*math.sin(2*math.pi*300*f/22050)) for f in range(640)]
        raw=struct.pack('<'+'h'*1280,*[v for value in samples for v in (value,-value)])
        decoded=audio.decode_xbox_adpcm(audio.encode_xbox_adpcm(raw,2),2)
        values=struct.unpack('<'+'h'*1280,decoded)
        mse=sum((a-b)**2 for a,b in zip(samples,values[::2]))/len(samples)
        self.assertLess(math.sqrt(mse),300)
        self.assertEqual(values[0],0)
        self.assertGreater(max(values[::2]),10000)
        self.assertLess(min(values[1::2]),-10000)

    def test_invalid_adpcm_headers_and_partial_blocks(self):
        with self.assertRaises(ValueError): audio.decode_xbox_adpcm(b'\0'*35,1)
        corrupt=bytearray(36);corrupt[2]=89
        with self.assertRaises(ValueError): audio.decode_xbox_adpcm(corrupt,1)
        corrupt[2]=0;corrupt[3]=1
        with self.assertRaises(ValueError): audio.decode_xbox_adpcm(corrupt,1)

    def test_stream_ref_requires_sdsr_type_and_bounds(self):
        original=bytearray(archive())
        descriptor=4096+144
        struct.pack_into('<I',original,descriptor+16,500)
        item=audio.list_voices(original)[0]
        self.assertFalse(item['editable'])
        with self.assertRaises(ValueError): audio.voice_wav(original,self.key)

    def test_shared_stream_rejected(self):
        self.assertTrue(all(not item['editable'] for item in audio.list_voices(archive(shared=True))))

    def test_inline_adpcm_uses_payload_after_header(self):
        meta=audio.list_voices(archive(streamed=False))[0]
        self.assertFalse(meta['streamed'])
        self.assertEqual(meta['dataOffset'],4112)
        self.assertEqual(meta['frames'],128)

    def test_pcm_audio_preserves_native_codec(self):
        original=archive(streamed=False,bits=16,codec=0)
        patched,meta=audio.replace_voice(original,self.key,wav(64,width=3))
        self.assertEqual(meta['codec'],0)
        self.assertEqual(len(original),len(patched))

    def test_all_supported_integer_wav_widths_import(self):
        for width in (1,2,3,4):
            with self.subTest(width=width):
                patched,meta=audio.replace_voice(archive(),self.key,wav(64,width=width),preserve_allocation=True)
                pcm,_=audio.voice_pcm(patched,self.key)
                self.assertEqual(pcm,b'\0'*(128*2*2))

    def test_bad_wav_not_accepted(self):
        with self.assertRaises(ValueError): audio.replace_voice(archive(),self.key,b'not a wav')
        with self.assertRaises(ValueError): audio.replace_voice(archive(),self.key,wav(10)[:-2])

    def test_truncated_name_catalog_rejected(self):
        with self.assertRaises(ValueError):audio.list_voices(archive()[:-2])
        bad=bytearray(archive());struct.pack_into('<I',bad,struct.unpack_from('<I',bad,48)[0]+4,999999)
        with self.assertRaises(ValueError):audio.list_voices(bad)

    def test_free_duration_grows_resource_and_updates_native_relocations(self):
        original=archive()
        patched,info=audio.replace_voice(original,self.key,wav(400))
        self.assertEqual(info['targetFrames'],400)
        self.assertEqual(info['outputFrames'],448)
        self.assertTrue(info['resize'])
        self.assertEqual(info['archiveDelta'],4096)
        self.assertLess(info['silenceSeconds'],64/22050)
        before_sections,before_names=audio._archive(original)
        after_sections,after_names=audio._archive(patched)
        self.assertEqual(before_names,after_names)
        self.assertEqual(after_sections[0].size,448//64*72)
        self.assertEqual(after_sections[1].offset,before_sections[1].offset+4096)
        h_before=struct.unpack_from('<16I',original);h_after=struct.unpack_from('<16I',patched)
        for field in (6,8,10,12,13):self.assertEqual(h_after[field],h_before[field]+4096)
        relative=struct.unpack_from('<I',patched,h_after[8])[0]
        self.assertEqual(h_after[4]+relative,after_sections[1].offset+16)
        self.assertEqual(struct.unpack_from('<I',patched,h_after[4]+relative)[0],0)
        self.assertEqual(audio.list_voices(patched)[0]['originalCounter'],224)
        self.assertEqual(len(audio.voice_pcm(patched,self.key)[0]),448*2*2)

    def test_free_duration_shortens_and_removes_old_silence_allocation(self):
        original=archive(frames=8192)
        patched,info=audio.replace_voice(original,self.key,wav(15))
        self.assertEqual(info['outputFrames'],64)
        self.assertEqual(info['targetFrames'],15)
        self.assertLess(info['silenceSeconds'],64/22050)
        self.assertLess(len(patched),len(original))
        self.assertEqual(info['archiveDelta']%4096,0)
        self.assertEqual(audio.list_voices(patched)[0]['frames'],64)
        self.assertEqual(audio.list_voices(patched)[0]['originalCounter'],32)

    def test_inline_stereo_growth_matches_native_bytecount_formula(self):
        patched,info=audio.replace_voice(archive(streamed=False),self.key,wav(257))
        meta=audio.list_voices(patched)[0]
        self.assertEqual(meta['frames'],384)
        self.assertEqual((meta['originalCounter']>>6)*meta['channels']*(36*meta['channels']),meta['dataSize'])

    def test_missing_or_unknown_relocations_block_resource_resize(self):
        original=bytearray(archive())
        relocation_offset=struct.unpack_from('<I',original,32)[0]
        struct.pack_into('<I',original,relocation_offset,0)
        with self.assertRaisesRegex(ValueError,'relocalisation'):
            audio.replace_voice(original,self.key,wav(400))

    def test_multiple_duration_replacements_retain_named_stream_binding(self):
        first,_=audio.replace_voice(archive(),self.key,wav(2048))
        second,info=audio.replace_voice(first,self.key,wav(300))
        self.assertEqual(audio.list_voices(second)[0]['frames'],320)
        self.assertEqual(info['resourceIndex'],1)
        self.assertEqual(info['dataResourceIndex'],0)
        self.assertEqual(audio._archive(first)[1],audio._archive(second)[1])

    def test_downsampling_lowpass_limits_aliasing(self):
        samples=array('h',[round(12000*math.sin(2*math.pi*15000*f/44100)) for f in range(400)])
        result=[audio._resampled_frame(samples,frame*2,1,len(samples),0.5)[0] for frame in range(20,180)]
        self.assertLess(math.sqrt(sum(value*value for value in result)/len(result)),500)

    def test_wav_export_is_portable_pcm16(self):
        data=audio.voice_wav(archive(),self.key)
        with wave.open(io.BytesIO(data),'rb') as source:
            self.assertEqual(source.getnchannels(),2)
            self.assertEqual(source.getframerate(),22050)
            self.assertEqual(source.getsampwidth(),2)
            self.assertEqual(source.getnframes(),128)


if __name__=='__main__':unittest.main()
