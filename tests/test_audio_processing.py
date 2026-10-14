from array import array
import io
import math
import struct
import unittest
import wave

import audio_processing as processing
from audio_formats import _read_wav,pcm_wav


def wav_values(values,rate=48000,channels=1,width=2):
    if width==2:
        return pcm_wav(struct.pack('<'+'h'*len(values),*values),rate,channels)
    raw=bytearray()
    for value in values:
        if width==1:raw.append(max(0,min(255,(value>>8)+128)))
        else:raw.extend((value<<(8*(width-2))).to_bytes(width,'little',signed=True))
    out=io.BytesIO()
    with wave.open(out,'wb') as dest:
        dest.setframerate(rate);dest.setnchannels(channels);dest.setsampwidth(width)
        dest.writeframes(raw)
    return out.getvalue()


class AudioProcessingTests(unittest.TestCase):
    def test_default_is_byte_identical_for_every_integer_pcm_width(self):
        for width in (1,2,3,4):
            with self.subTest(width=width):
                original=wav_values([0,1000,-1000,2000],width=width)
                result,meta=processing.prepare_wav(original)
                self.assertEqual(result,original)
                self.assertFalse(meta['processingApplied'])
                self.assertFalse(meta['limiterActive'])
                self.assertEqual(meta['trimFrames'],0)

    def test_explicit_trim_keeps_exact_remaining_frames_and_sample_rate(self):
        original=wav_values([value for f in range(1000) for value in (f,-f)],rate=48000,channels=2)
        result,meta=processing.prepare_wav(original,trim_start_seconds=100/48000)
        samples,rate,channels,frames=_read_wav(result)
        self.assertEqual((rate,channels,frames),(48000,2,900))
        self.assertEqual(samples[0],100);self.assertEqual(samples[1],-100)
        self.assertEqual(list(samples[-2:]),[999,-999])
        self.assertEqual(meta['trimFrames'],100)

    def test_quiet_sound_receives_requested_gain_without_delay(self):
        original=wav_values([1000]*1000,rate=22050)
        result,meta=processing.prepare_wav(original,gain_db=6)
        samples,rate,channels,frames=_read_wav(result)
        self.assertEqual(frames,1000)
        self.assertTrue(all(abs(sample-1995)<=1 for sample in samples))
        self.assertEqual(meta['limitedFrames'],0)
        self.assertEqual(meta['lookaheadMs'],8)

    def test_peak_limiter_preserves_stereo_ratio_and_ceiling(self):
        values=[]
        for frame in range(2400):
            value=30000 if frame%200==0 else 12000
            values.extend((value,value//2))
        result,meta=processing.prepare_wav(wav_values(values,channels=2),gain_db=12)
        samples,rate,channels,frames=_read_wav(result)
        ceiling=math.floor(32768*10**(-2/20))
        self.assertLessEqual(max(map(abs,samples)),ceiling)
        self.assertGreater(meta['limitedFrames'],0)
        self.assertEqual(frames,2400)
        for left,right in zip(samples[::2],samples[1::2]):self.assertLessEqual(abs(left-2*right),1)

    def test_negative_gain_reduces_volume_without_limiter(self):
        result,meta=processing.prepare_wav(wav_values([32767,-32768]*100),gain_db=-6)
        samples,*_= _read_wav(result)
        self.assertLess(max(map(abs,samples)),16430)
        self.assertFalse(meta['limiterActive'])
        self.assertEqual(meta['limitedFrames'],0)

    def test_pcm_extreme_negative_sample_and_zero_ceiling_never_overflow(self):
        for ceiling in (-2,0):
            with self.subTest(ceiling=ceiling):
                result,meta=processing.prepare_wav(wav_values([-32768,32767]*100),gain_db=12,ceiling_db=ceiling)
                samples,*_=_read_wav(result)
                self.assertLessEqual(max(map(abs,samples)),32767)

    def test_processing_converts_supported_integer_widths_to_pcm16(self):
        for width in (1,2,3,4):
            with self.subTest(width=width):
                result,meta=processing.prepare_wav(wav_values([0,1000,-1000,2000],width=width),gain_db=-1)
                with wave.open(io.BytesIO(result),'rb') as source:self.assertEqual(source.getsampwidth(),2)
                self.assertEqual(meta['outputFrames'],4)

    def test_does_not_detect_or_remove_silence_without_explicit_trim(self):
        original=wav_values([0]*1000+[5000]*1000)
        result,meta=processing.prepare_wav(original,gain_db=6)
        samples,*_=_read_wav(result)
        self.assertEqual(list(samples[:1000]),[0]*1000)
        self.assertEqual(meta['outputFrames'],2000)
        self.assertEqual(meta['trimFrames'],0)

    def test_bad_parameters_and_empty_result_are_rejected(self):
        original=wav_values([1000]*1000,rate=10000)
        for kwargs in ({'gain_db':13},{'gain_db':-13},{'gain_db':True},{'gain_db':float('nan')},
                       {'gain_db':float('inf')},{'trim_start_seconds':-0.1},
                       {'trim_start_seconds':0.1},{'trim_start_seconds':1},
                       {'ceiling_db':1},{'ceiling_db':-25},{'ceiling_db':'-2'}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):processing.prepare_wav(original,**kwargs)
        with self.assertRaises(ValueError):processing.prepare_wav(b'not WAV')

    def test_trim_rounding_cannot_silently_create_empty_recording(self):
        with self.assertRaises(ValueError):
            processing.prepare_wav(wav_values([1000],rate=48000),trim_start_seconds=0.9/48000)


if __name__=='__main__':unittest.main()
