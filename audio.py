from copy import deepcopy
from io import BytesIO
from pydub import AudioSegment
from synth_mapping_helper.audio_format import AudioData
from synth_mapping_helper.synth_format import SynthFile
import traceback
import logging
log = logging.getLogger(__name__)

def get_ogg_duration(audio_path):
    """Get audio duration in milliseconds"""
    try:
        audio = AudioSegment.from_ogg(audio_path)
        return len(audio)  # Duration in milliseconds
    except Exception as e:
        log.error(f"Error getting audio duration: {e}")
        return None

def segment_beatmap_audio(original_beatmap: SynthFile, start_time_ms, end_time_ms, beatmap_segment: SynthFile):
    """Extract a specific segment of audio between start and end times"""
    try:
        log.info(f"Extracting audio segment from {start_time_ms:.2f}ms to {end_time_ms:.2f}ms...")
        original_audio_buffer = BytesIO(original_beatmap.audio.raw_data)
        audio = AudioSegment.from_file(original_audio_buffer, format="ogg")
        
        # Extract segment from start_time_ms to end_time_ms
        audio_segment = audio[start_time_ms:end_time_ms]
        segment_buffer = BytesIO()
        audio_segment.export(segment_buffer, format="ogg")
        
        beatmap_segment.audio = AudioData.from_raw(segment_buffer.read())
        log.info(f"Segmented beatmap audio: {start_time_ms} - {end_time_ms} (duration: {audio_segment.duration_seconds})")
        return True
        
    except Exception as e:
        traceback.print_exc()
        log.error(f"Error extracting audio segment: {e}")
        return False

def create_tempo_segments(tempo_and_time_changes, audio_duration_ms, initial_bpm):
    """Create tempo segments with start and end times for each BPM section"""
    segments = []
    
    keys = sorted(tempo_and_time_changes.keys())
    log.debug(f"keys: {keys}")
    log.debug(f"tempo_and_time_changes: {tempo_and_time_changes}")
    last_bpm = initial_bpm
    last_tempo = None
    last_time_signature = None
    log.debug(f"audio_duration_ms: {audio_duration_ms}")
    for i, start_time in enumerate(keys):
        events = tempo_and_time_changes[start_time]
        # Determine end time (next tempo change or end of audio)
        if i + 1 < len(keys):
            log.debug(keys[i + 1])
            end_time = keys[i + 1]
        else:
            end_time = audio_duration_ms
        log.debug(f"start_time: {start_time}")
        log.debug(f"end_time: {end_time}")
        
        duration = end_time - start_time
        segment = {}
        segment.update({
            'start_ms': start_time,
            'end_ms': end_time,
            'duration_ms': duration,
        })
        if "tempo" in events:
            last_bpm = deepcopy(events['tempo']['bpm'])
            last_tempo = deepcopy(events['tempo']['tempo'])
            segment.update({
                'bpm': deepcopy(events['tempo']['bpm']),
                'tempo': deepcopy(events['tempo']['tempo'])
            })
        else:
            segment.update({
                'bpm': last_bpm,
                'tempo': last_tempo
            })
        if "time_signature" in events:
            last_time_signature = deepcopy(events['time_signature'])
            segment.update({
                'time_signature': {
                    'numerator': deepcopy(events['time_signature']['numerator']),
                    'denominator': deepcopy(events['time_signature']['denominator'])
                }
            })
        else:
            segment.update({'time_signature': deepcopy(last_time_signature)})
        log.debug(f"events: {events}")
        log.debug(f"last_tempo: {last_tempo}")
        log.debug(f"last_bpm: {last_bpm}")
        log.debug(f"last_time_signature: {last_time_signature}")
        log.debug(f"segment: {segment}")
        log.info(f"Segment {i+1}: {segment['bpm']:.2f} BPM Time Signature {segment['time_signature']['numerator']}/{segment['time_signature']['denominator']} from {start_time:.2f}ms to {end_time:.2f}ms (duration: {duration:.2f}ms)")
        segments.append(segment)
    
    return segments
