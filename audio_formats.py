"""Offline Azurik voice editing: exact native names and bounded audio payloads.

Retail v4 TOC rows contain cumulative END offsets. Streamed 20-byte WAVE
descriptors point to an SDSR resource by index at +16. Variable-duration
replacement moves whole following resources on page boundaries and rebuilds
the exact footer relocation addresses. Resource IDs and other payloads stay
unchanged. No heuristic scanning, recovery or external service.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
import io
import math
import struct
import sys
import wave

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_WAV_BYTES = 128 * 1024 * 1024
_RATES = {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}
MAX_SECONDS = 600
MAX_FRAMES = max(_RATES) * MAX_SECONDS + 128
_STEP = (7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,
         50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,
         253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,
         1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,
         3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,
         9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,
         24623,27086,29794,32767)
_INDEX = (-1,-1,-1,-1,2,4,6,8)


@dataclass(frozen=True)
class _Section:
    index: int
    tag: str
    offset: int
    size: int
    flags: int


def _archive(data: bytes) -> tuple[list[_Section], dict[int, list[str]]]:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("Les données de l'archive doivent être binaires.")
    if not 64 <= len(data) <= MAX_ARCHIVE_BYTES or data[:4] != b'xobx':
        raise ValueError("Archive XBR invalide ou trop volumineuse.")
    h = struct.unpack_from('<16I', data)
    count, base, footer = h[3], h[4], h[6]
    if h[1] != 4 or not 1 <= count <= 200000 or 64+count*16 > base:
        raise ValueError("Seules les archives Azurik v4 valides sont prises en charge.")
    if (base % 4096 or footer % 4096 or not base <= footer <= len(data)
            or h[6]+h[5]*8 != h[8] or h[8]+h[7]*4 != h[10]
            or h[10]+h[9]*12 != h[12] or h[12]+h[11]*8 != h[13]
            or h[13]+h[14] != len(data) or h[11] > 20000):
        raise ValueError("Le catalogue des ressources XBR est tronqué ou incohérent.")
    sections, previous = [], 0
    for index in range(count):
        size, rawtag, flags, end = struct.unpack_from('<I4sII', data, 64+index*16)
        if any(c < 32 or c > 126 for c in rawtag):
            raise ValueError("Type de ressource XBR illisible.")
        start = base+previous
        if (start+size > footer or end and base+end > footer
                or end < previous+size and not (index == count-1 and end == 0)):
            raise ValueError("Les ressources XBR se chevauchent ou dépassent le fichier.")
        sections.append(_Section(index, rawtag.decode('ascii'), start, size, flags))
        previous = end
    names: dict[int, list[str]] = {}
    seen = set()
    for i in range(h[11]):
        resource, offset = struct.unpack_from('<II', data, h[12]+i*8)
        if resource >= count or offset >= h[14]:
            raise ValueError("Un nom XBR référence une ressource absente.")
        start = h[13]+offset
        end = data.find(b'\0', start, min(len(data), start+256))
        if end < 0:
            raise ValueError("Nom de ressource XBR sans terminaison.")
        try:
            key = data[start:end].decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError("Nom de ressource XBR invalide.") from exc
        if not key or key in seen:
            raise ValueError("Nom de ressource XBR vide ou répété.")
        seen.add(key)
        names.setdefault(resource, []).append(key)
    return sections, names


def _validate_adpcm(payload: bytes, channels: int) -> None:
    align = 36*channels
    if channels not in (1,2) or not payload or len(payload) % align:
        raise ValueError("Le son Xbox ADPCM ne contient pas des blocs complets.")
    if len(payload)//align*64 > MAX_FRAMES:
        raise ValueError("La voix dépasse la durée maximale de dix minutes.")
    for start in range(0,len(payload),align):
        for channel in range(channels):
            step, reserved = struct.unpack_from('<BB',payload,start+channel*4+2)
            if step > 88 or reserved != 0:
                raise ValueError("En-tête de bloc Xbox ADPCM invalide.")


def _metadata(data, section, sections, key):
    if section.size < 16:
        raise ValueError("L'en-tête WAVE est incomplet.")
    rate, counter, channels, bits, streamed, codec, _pad = struct.unpack_from('<II4BI',data,section.offset)
    if rate not in _RATES or channels not in (1,2) or streamed not in (0,1):
        raise ValueError("Format de voix Azurik non pris en charge.")
    if codec not in (0,1) or (codec == 1 and bits != 4) or (codec == 0 and bits not in (8,16)):
        raise ValueError("Codec de voix Azurik non pris en charge.")
    if streamed:
        if section.size != 20:
            raise ValueError("La liaison du flux audio est de format inconnu.")
        linked = struct.unpack_from('<I',data,section.offset+16)[0]
        if linked >= len(sections) or sections[linked].tag != 'sdsr':
            raise ValueError("Le flux audio ne référence pas une ressource SDSR valide.")
        offset, size = sections[linked].offset, sections[linked].size
    else:
        linked = section.index
        offset, size = section.offset+16, section.size-16
    payload = data[offset:offset+size]
    if codec == 1:
        _validate_adpcm(payload,channels)
        frames = size//(36*channels)*64
    else:
        align = channels*(bits//8)
        if not payload or size % align:
            raise ValueError("La voix PCM est incomplète.")
        frames = size//align
    if not 1 <= frames <= min(MAX_FRAMES,rate*MAX_SECONDS+128):
        raise ValueError("La durée de la voix est hors limites.")
    category = ('Oracles' if '/speech/eld_level_intros/' in key else
                "Voix d'Azurik" if '/speech/azurik_speech/' in key else
                'Boîtes de dialogue' if '/popups/' in key else 'Personnages')
    return dict(key=key,resourceIndex=section.index,category=category,rate=rate,
                channels=channels,bits=bits,codec=codec,streamed=bool(streamed),
                dataResourceIndex=linked,dataOffset=offset,dataSize=size,
                frames=frames,duration=frames/rate,originalCounter=counter,
                editable=True,error=None)


def list_voices(data: bytes) -> list[dict]:
    """List only exactly named WAVE resources; malformed audio stays visible."""
    sections, names = _archive(data)
    result=[]
    for section in sections:
        if section.tag != 'wave':
            continue
        for key in names.get(section.index,[]):
            try:
                meta = _metadata(data,section,sections,key)
            except ValueError as exc:
                meta = dict(key=key,resourceIndex=section.index,category='Non pris en charge',
                            editable=False,error=str(exc),duration=0,channels=0,rate=0)
            result.append(meta)
    # Different descriptor resources must not silently share an editable stream.
    users={}
    for meta in result:
        if meta['editable']:
            users.setdefault(meta['dataResourceIndex'],set()).add(meta['resourceIndex'])
    for meta in result:
        if meta['editable'] and len(users[meta['dataResourceIndex']]) > 1:
            meta['editable']=False
            meta['error']='Ce flux est partagé entre plusieurs voix : remplacement indépendant indisponible.'
    return result


def _voice(data,key):
    matches=[m for m in list_voices(data) if m['key']==key]
    if len(matches)!=1:
        raise ValueError("Voix absente du catalogue original.")
    if not matches[0]['editable']:
        raise ValueError(matches[0]['error'])
    return matches[0]


def _expand(code,predictor,index):
    step=_STEP[index]
    delta=(step>>3)+(step>>2 if code&1 else 0)+(step>>1 if code&2 else 0)+(step if code&4 else 0)
    predictor=max(-32768,min(32767,predictor+(-delta if code&8 else delta)))
    index=max(0,min(88,index+_INDEX[code&7]))
    return predictor,index


def decode_xbox_adpcm(payload: bytes, channels: int) -> bytes:
    """Decode 64-frame Xbox IMA blocks to interleaved signed PCM16.

    The predictor is frame zero; the final high nibble is padding. Stereo
    headers precede alternating four-byte channel chunks.
    """
    _validate_adpcm(payload,channels)
    output=array('h')
    align=36*channels
    for start in range(0,len(payload),align):
        decoded=[]
        for channel in range(channels):
            predictor,index=struct.unpack_from('<hB',payload,start+channel*4)
            samples=[predictor]
            for frame in range(63):
                offset=start+channels*4+(frame//8)*4*channels+channel*4+(frame%8)//2
                code=(payload[offset]>>(4*(frame&1)))&15
                predictor,index=_expand(code,predictor,index)
                samples.append(predictor)
            decoded.append(samples)
        output.extend(decoded[channel][frame] for frame in range(64) for channel in range(channels))
    if sys.byteorder!='little': output.byteswap()
    return output.tobytes()


def _quantize(sample,predictor,index):
    difference=sample-predictor
    code=8 if difference<0 else 0
    difference=abs(difference)
    step=_STEP[index]
    for bit,amount in ((4,step),(2,step>>1),(1,step>>2)):
        if difference>=amount:
            code|=bit
            difference-=amount
    return code,*_expand(code,predictor,index)


def encode_xbox_adpcm(pcm: bytes, channels: int) -> bytes:
    """Encode complete PCM16 frames without trimming a partial final block."""
    if channels not in (1,2) or not pcm or len(pcm)%(channels*2):
        raise ValueError("Les échantillons PCM16 sont incomplets.")
    samples=array('h'); samples.frombytes(pcm)
    if sys.byteorder!='little': samples.byteswap()
    frames=len(samples)//channels
    if frames>MAX_FRAMES: raise ValueError("Voix trop longue.")
    if frames%64: samples.extend([0]*((64-frames%64)*channels))
    result=bytearray()
    for first in range(0,len(samples)//channels,64):
        block=bytearray(36*channels)
        for channel in range(channels):
            values=[samples[(first+frame)*channels+channel] for frame in range(64)]
            if all(value==0 for value in values):
                continue
            predictor=values[0]
            average=sum(abs(values[i]-values[i-1]) for i in range(1,9))/8
            index=min(range(89),key=lambda i:abs(_STEP[i]-average*2))
            struct.pack_into('<hBB',block,channel*4,predictor,index,0)
            for frame,sample in enumerate(values[1:]):
                code,predictor,index=_quantize(sample,predictor,index)
                offset=channels*4+(frame//8)*4*channels+channel*4+(frame%8)//2
                block[offset]|=code<<(4*(frame&1))
        result.extend(block)
    return bytes(result)


def voice_pcm(data: bytes, key: str) -> tuple[bytes,dict]:
    meta=_voice(data,key)
    payload=data[meta['dataOffset']:meta['dataOffset']+meta['dataSize']]
    if meta['codec']==1:
        pcm=decode_xbox_adpcm(payload,meta['channels'])
    elif meta['bits']==16:
        pcm=bytes(payload)
    else:
        samples=array('h',((byte-128)*256 for byte in payload))
        if sys.byteorder!='little': samples.byteswap()
        pcm=samples.tobytes()
    return pcm,meta


def pcm_wav(pcm: bytes, rate: int, channels: int) -> bytes:
    output=io.BytesIO()
    with wave.open(output,'wb') as dest:
        dest.setnchannels(channels);dest.setsampwidth(2);dest.setframerate(rate)
        dest.writeframes(pcm)
    return output.getvalue()


def voice_wav(data: bytes, key: str) -> bytes:
    pcm,meta=voice_pcm(data,key)
    return pcm_wav(pcm,meta['rate'],meta['channels'])


def _read_wav(data: bytes):
    if not isinstance(data,(bytes,bytearray)) or not 44<=len(data)<=MAX_WAV_BYTES:
        raise ValueError("Le fichier WAV est invalide ou dépasse 128 Mo.")
    try:
        with wave.open(io.BytesIO(data),'rb') as source:
            channels,rate,width,frames=source.getnchannels(),source.getframerate(),source.getsampwidth(),source.getnframes()
            if source.getcomptype()!='NONE' or channels not in (1,2) or width not in (1,2,3,4) or not 8000<=rate<=192000:
                raise ValueError("Importer un WAV PCM non compressé, mono ou stéréo, de 8 à 32 bits.")
            if not 1<=frames<=rate*600: raise ValueError("Le WAV est vide ou dépasse dix minutes.")
            raw=source.readframes(frames)
            if len(raw)!=frames*channels*width: raise ValueError("Le WAV est tronqué.")
    except (wave.Error,EOFError,struct.error) as exc:
        raise ValueError("Importer un fichier WAV PCM non compressé (les WAV flottants et MP3 ne sont pas pris en charge).") from exc
    if width==2:
        samples=array('h');samples.frombytes(raw)
        if sys.byteorder!='little':samples.byteswap()
    elif width==1:
        samples=array('h',((value-128)*256 for value in raw))
    else:
        shift=(width-2)*8
        samples=array('h',(int.from_bytes(raw[i:i+width],'little',signed=True)>>shift for i in range(0,len(raw),width)))
    return samples,rate,channels,frames


def _resize_footer(data,sections):
    """Verify the exact native language-bank layout before moving resources."""
    h=struct.unpack_from('<16I',data)
    if h[2] or h[9] or h[15] or any(s.tag not in ('wave','surf','sdsr') for s in sections):
        raise ValueError("La durée libre est disponible pour les banques de langue natives Azurik ; cette archive contient des données de format différent.")
    loaders=[struct.unpack_from('<4sI',data,h[6]+i*8) for i in range(h[5])]
    if len(set(tag for tag,flags in loaders))!=len(loaders) or any((tag,flags) not in ((b'wave',4),(b'surf',4),(b'sdsr',0)) for tag,flags in loaders):
        raise ValueError("La table des types de la banque audio est de format inconnu.")
    expected={}
    for section in sections:
        if section.tag=='wave' and section.size>=16 and data[section.offset+10]==1:
            if section.size!=20:
                raise ValueError("Un descripteur de voix en flux a une taille inconnue.")
            linked=struct.unpack_from('<I',data,section.offset+16)[0]
            if linked>=len(sections) or sections[linked].tag!='sdsr':
                raise ValueError("Une liaison de flux audio pointe hors du catalogue SDSR.")
            expected[section.offset+16-h[4]]=(section.index,linked)
    relocations=[]
    for i in range(h[7]):
        relative=struct.unpack_from('<I',data,h[8]+i*4)[0]
        if relative not in expected or relative in relocations:
            raise ValueError("La table de relocalisation des voix contient une adresse inconnue ou répétée.")
        relocations.append(relative)
    if set(relocations)!=set(expected):
        raise ValueError("La table de relocalisation ne contient pas toutes les liaisons des voix.")
    return h,relocations,expected


def _resize_resource(data,resource_index,payload):
    sections,names=_archive(data)
    h,relocations,expected=_resize_footer(data,sections)
    section=sections[resource_index]
    delta=len(payload)-section.size
    shift=((delta+4095)//4096)*4096 if delta>=0 else -((-delta)//4096)*4096
    if not 64<=len(data)+shift<=MAX_ARCHIVE_BYTES:
        raise ValueError("La banque de langue reconstruite dépasserait 512 Mo.")
    padding=shift-delta
    if padding<0:
        raise ValueError("La nouvelle réserve audio n'est pas correctement alignée.")
    result=bytearray(data[:section.offset])+payload+b'\0'*padding+data[section.offset+section.size:]
    struct.pack_into('<I',result,64+resource_index*16,len(payload))
    for index in range(resource_index,len(sections)):
        end=struct.unpack_from('<I',data,64+index*16+12)[0]
        if end:
            new_end=end+shift
            if not 0<=new_end<=0xffffffff:raise ValueError("Limite de relocalisation XBR dépassée.")
            struct.pack_into('<I',result,64+index*16+12,new_end)
    for field in (6,8,10,12,13):
        struct.pack_into('<I',result,field*4,h[field]+shift)
    for index,relative in enumerate(relocations):
        owner,_linked=expected[relative]
        moved=relative+shift if owner>resource_index else relative
        struct.pack_into('<I',result,h[8]+shift+index*4,moved)
    rebuilt,rebuilt_names=_archive(result)
    _resize_footer(result,rebuilt)
    if names!=rebuilt_names or len(rebuilt)!=len(sections):
        raise ValueError("Les noms ou indices des ressources ont changé pendant l'export audio.")
    for before,after in zip(sections,rebuilt):
        if (before.index,before.tag,before.flags)!=(after.index,after.tag,after.flags):
            raise ValueError("Une référence de ressource a changé pendant la reconstruction audio.")
        if before.index!=resource_index and data[before.offset:before.offset+before.size]!=result[after.offset:after.offset+after.size]:
            raise ValueError("Une ressource non sélectionnée a changé pendant la reconstruction audio.")
    return result,shift


def replacement_info(data: bytes,key: str,wav: bytes,*,preserve_allocation=False) -> dict:
    meta=_voice(data,key)
    _samples,rate,channels,frames=_read_wav(wav)
    target_frames=(frames*meta['rate']+rate-1)//rate
    if preserve_allocation and target_frames>meta['frames']:
        raise ValueError(f"Enregistrement trop long ({frames/rate:.2f} s). Durée maximale : {meta['duration']:.2f} s. Le logiciel ne coupe pas votre voix.")
    if not preserve_allocation:
        _resize_footer(data,_archive(data)[0])
    # Inline native SetBufferData derives ADPCM bytes from counter>>6,
    # channels and blockAlign. Stereo inline therefore needs paired blocks.
    alignment=64*(meta['channels'] if not meta['streamed'] else 1) if meta['codec']==1 else 1
    output_frames=meta['frames'] if preserve_allocation else ((target_frames+alignment-1)//alignment)*alignment
    if output_frames>meta['rate']*MAX_SECONDS+alignment:
        raise ValueError("L'enregistrement dépasse la durée maximale de dix minutes.")
    output_size=output_frames//64*36*meta['channels'] if meta['codec']==1 else output_frames*meta['channels']*(meta['bits']//8)
    return dict(meta,importRate=rate,importChannels=channels,importFrames=frames,
                importDuration=frames/rate,targetFrames=target_frames,
                outputFrames=output_frames,originalDuration=meta['duration'],
                duration=output_frames/meta['rate'],resize=output_size!=meta['dataSize'],
                outputDataSize=output_size,preserveAllocation=bool(preserve_allocation),
                silenceSeconds=(output_frames-target_frames)/meta['rate'],
                resampled=rate!=meta['rate'],channelConverted=channels!=meta['channels'])


def _resampled_frame(samples,position,channels,source_frames,ratio):
    """Windowed-sinc rate conversion, including a low-pass before downsampling."""
    if ratio==1:
        index=min(int(position),source_frames-1)
        return [samples[index*channels+c] for c in range(channels)]
    cutoff=min(1.0,ratio)*0.95
    radius=16
    center=int(position)
    values=[0.0]*channels
    weight_sum=0.0
    for index in range(max(0,center-radius+1),min(source_frames,center+radius+1)):
        distance=index-position
        if abs(distance)>=radius:continue
        value=distance*cutoff
        sinc=1.0 if abs(value)<1e-12 else math.sin(math.pi*value)/(math.pi*value)
        weight=cutoff*sinc*(0.5+0.5*math.cos(math.pi*distance/radius))
        weight_sum+=weight
        for channel in range(channels):values[channel]+=samples[index*channels+channel]*weight
    return [max(-32768,min(32767,round(value/weight_sum))) for value in values]


def replace_voice(data: bytes,key: str,wav: bytes,*,preserve_allocation=False) -> tuple[bytes,dict]:
    """Replace an entire recording at its chosen duration, without truncation."""
    meta=replacement_info(data,key,wav,preserve_allocation=preserve_allocation)
    samples,rate,channels,frames=_read_wav(wav)
    target=array('h')
    destination_channels=meta['channels']
    for frame in range(meta['targetFrames']):
        position=frame*rate/meta['rate']
        values=_resampled_frame(samples,position,channels,frames,meta['rate']/rate)
        if destination_channels==1 and channels==2: values=[round((values[0]+values[1])/2)]
        elif destination_channels==2 and channels==1: values=values*2
        target.extend(values)
    target.extend([0]*((meta['outputFrames']-meta['targetFrames'])*destination_channels))
    if sys.byteorder!='little':target.byteswap()
    pcm=target.tobytes()
    if meta['codec']==1: payload=encode_xbox_adpcm(pcm,destination_channels)
    elif meta['bits']==16: payload=pcm
    else:
        if sys.byteorder!='little':target.byteswap()
        payload=bytes(max(0,min(255,(sample>>8)+128)) for sample in target)
    if len(payload)!=meta['outputDataSize']:
        raise ValueError("Le remplacement ne respecte pas la durée choisie du flux.")
    if preserve_allocation:
        start=meta['dataOffset'];end=start+len(payload)
        patched=bytearray(data[:start])+payload+data[end:]
        shift=0
    else:
        old_sections,_=_archive(data)
        allocation=old_sections[meta['dataResourceIndex']]
        resource_payload=payload if meta['streamed'] else data[allocation.offset:allocation.offset+16]+payload
        patched,shift=_resize_resource(data,allocation.index,resource_payload)
        new_sections,_=_archive(patched)
        descriptor=new_sections[meta['resourceIndex']]
        counter=meta['outputFrames']//meta['channels'] if meta['codec']==1 else meta['outputFrames']
        struct.pack_into('<I',patched,descriptor.offset+4,counter)
    patched=bytes(patched)
    # Check the output using the same exact name/descriptor binding.
    rebuilt=_voice(patched,key)
    for field in ('resourceIndex','rate','channels','bits','codec','streamed','dataResourceIndex'):
        if rebuilt[field]!=meta[field]:
            raise ValueError("La validation de l'archive remplacée a échoué.")
    if rebuilt['frames']!=meta['outputFrames'] or rebuilt['dataSize']!=meta['outputDataSize']:
        raise ValueError("Le son reconstruit ne correspond pas à la durée choisie.")
    meta.update(outputCounter=rebuilt['originalCounter'],archiveDelta=shift,
                outputDataOffset=rebuilt['dataOffset'],outputBankBytes=len(patched))
    return patched,meta
