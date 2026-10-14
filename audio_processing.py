"""Explicit offline WAV gain and leading trim; no recording or speech guessing.

Positive gain uses a stereo-linked peak limiter with 8 ms lookahead and
40 ms release. Lookahead inspects future samples without adding delay.
The default -2 dBFS ceiling leaves some room for lossy Xbox ADPCM encoding.
Callers own imported files and must validate peaks after that encoding.
"""
from __future__ import annotations

from array import array
from collections import deque
import math
import sys

from audio_formats import _read_wav, pcm_wav


LOOKAHEAD_SECONDS = 0.008
RELEASE_SECONDS = 0.040


def _number(value,label,minimum,maximum):
    if (isinstance(value,bool) or not isinstance(value,(int,float))
            or not math.isfinite(value) or not minimum<=value<=maximum):
        raise ValueError(f"{label} doit être un nombre compris entre {minimum:g} et {maximum:g}.")
    return float(value)


def _db(value):
    return None if value<=0 else 20*math.log10(value/32768)


def _levels(samples):
    peak=max((abs(value) for value in samples),default=0)
    rms=math.sqrt(sum(value*value for value in samples)/max(1,len(samples)))
    return peak,rms


def prepare_wav(wavbytes: bytes, gain_db=0, trim_start_seconds=0,
                ceiling_db=-2.0) -> tuple[bytes,dict]:
    """Apply only requested gain/trim and return portable PCM16 when processed.

    An unchanged recording (zero gain and trim) is returned byte-identical,
    retaining its original integer PCM width and extra WAV chunks. Silence
    is never detected or removed automatically. All channels use one gain
    envelope, and no file or original recording is read/written here.
    """
    gain_db=_number(gain_db,'Le gain en dB',-12,12)
    trim_start_seconds=_number(trim_start_seconds,'Le début en secondes',0,600)
    ceiling_db=_number(ceiling_db,'Le plafond en dBFS',-24,0)
    samples,rate,channels,input_frames=_read_wav(wavbytes)
    duration=input_frames/rate
    trim_frames=round(trim_start_seconds*rate)
    if trim_start_seconds>=duration or trim_frames>=input_frames:
        raise ValueError("Le début choisi doit laisser au moins un échantillon de l'enregistrement.")
    original_peak,original_rms=_levels(samples)
    selected=samples[trim_frames*channels:]
    before_peak,before_rms=_levels(selected)
    processed=gain_db!=0 or trim_start_seconds!=0
    limited_frames=0
    output_frames=input_frames-trim_frames
    if not processed:
        result=bytes(wavbytes)
        after_peak,after_rms=before_peak,before_rms
    else:
        multiplier=10**(gain_db/20)
        output=array('h')
        if gain_db>0:
            peaks=[max(abs(selected[frame*channels+channel]) for channel in range(channels))
                   for frame in range(output_frames)]
            future_peaks=array('H',[0])*output_frames
            queue=deque()
            lookahead=max(1,round(rate*LOOKAHEAD_SECONDS))
            for frame in range(output_frames-1,-1,-1):
                while queue and queue[0]>frame+lookahead:queue.popleft()
                while queue and peaks[queue[-1]]<=peaks[frame]:queue.pop()
                queue.append(frame)
                future_peaks[frame]=peaks[queue[0]]
            ceiling=min(32767,math.floor(32768*10**(ceiling_db/20)))
            release=1-math.exp(-1/(rate*RELEASE_SECONDS))
            envelope=multiplier
            for frame in range(output_frames):
                safe=min(multiplier,ceiling/max(1,future_peaks[frame]))
                envelope=min(safe,envelope+(multiplier-envelope)*release)
                # Count material limiting rather than the vanishing tail of
                # the exponential release (0.1% gain reduction threshold).
                if envelope<multiplier*0.999:limited_frames+=1
                output.extend(round(selected[frame*channels+channel]*envelope)
                              for channel in range(channels))
        else:
            output.extend(round(value*multiplier) for value in selected)
        after_peak,after_rms=_levels(output)
        if gain_db>0 and after_peak>ceiling:
            raise ValueError("Le limiteur n'a pas respecté son plafond ; aucun enregistrement n'est produit.")
        if sys.byteorder!='little':output.byteswap()
        result=pcm_wav(output.tobytes(),rate,channels)
    metadata=dict(gainDb=gain_db,trimStartSeconds=trim_start_seconds,
                  actualTrimSeconds=trim_frames/rate,trimFrames=trim_frames,
                  inputFrames=input_frames,outputFrames=output_frames,
                  originalDuration=duration,duration=output_frames/rate,
                  rate=rate,channels=channels,ceilingDb=ceiling_db,
                  limiterActive=gain_db>0,limitedFrames=limited_frames,
                  limitedFramePercent=100*limited_frames/output_frames,
                  lookaheadMs=8 if gain_db>0 else 0,releaseMs=40 if gain_db>0 else 0,
                  processingApplied=processed,sourceUnchanged=True,
                  originalPeakDbFS=_db(original_peak),originalRMSDbFS=_db(original_rms),
                  preGainPeakDbFS=_db(before_peak),preGainRMSDbFS=_db(before_rms),
                  peakDbFS=_db(after_peak),rmsDbFS=_db(after_rms),peak=after_peak)
    return result,metadata
