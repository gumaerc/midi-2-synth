import logging
from typing import Any, Dict, List
import mido
import logging

log = logging.getLogger(__name__)
def calculate_time_from_ticks(target_ticks: int, ticks_per_beat: int, tempo_events: List[Dict], initial_tempo: int = 500000) -> float:
    """
    Convert ticks to time in seconds using tempo changes.
    
    Args:
        target_ticks: The tick position to convert to time
        ticks_per_beat: MIDI file's ticks per beat
        tempo_events: List of tempo events sorted by time_ticks
        initial_tempo: Default tempo in microseconds per beat (500000 = 120 BPM)
    
    Returns:
        Time in seconds
    """
    if target_ticks == 0:
        return 0.0
    
    current_time_seconds = 0.0
    current_tempo = initial_tempo
    last_tick_position = 0
    
    # Process each tempo change up to our target tick position
    for tempo_event in tempo_events:
        tempo_change_tick = tempo_event['time_ticks']
        
        # If this tempo change is after our target, calculate remaining time and break
        if tempo_change_tick >= target_ticks:
            remaining_ticks = target_ticks - last_tick_position
            if remaining_ticks > 0:
                current_time_seconds += mido.tick2second(remaining_ticks, ticks_per_beat, current_tempo)
            break
        
        # Calculate time from last position to this tempo change
        if tempo_change_tick > last_tick_position:
            ticks_in_segment = tempo_change_tick - last_tick_position
            current_time_seconds += mido.tick2second(ticks_in_segment, ticks_per_beat, current_tempo)
        
        # Update tempo and position
        current_tempo = tempo_event['tempo']
        last_tick_position = tempo_change_tick
    else:
        # No tempo change after target_ticks, calculate remaining time with current tempo
        remaining_ticks = target_ticks - last_tick_position
        if remaining_ticks > 0:
            current_time_seconds += mido.tick2second(remaining_ticks, ticks_per_beat, current_tempo)
    
    return current_time_seconds

def extract_tempo_changes(midi_file: mido.MidiFile):
    log.debug("Start extract_tempo_changes")
    ticks_per_beat = midi_file.ticks_per_beat
    
    log.info(f"Processing MIDI file: {midi_file}")
    log.info(f"Ticks per beat: {ticks_per_beat}")
    
    # Process all tracks and collect tempo events with absolute timing
    all_tempo_events = []
    try:
        for track_idx, track in enumerate(midi_file.tracks):
            current_time_ticks = 0
            
            for msg in track:
                current_time_ticks += msg.time
                
                if msg.type == 'set_tempo':
                    all_tempo_events.append({
                        'time_ticks': current_time_ticks,
                        'tempo': msg.tempo,
                        'track': track_idx
                    })
    except Exception as e:
        logging.exception(e)
        
    # Sort all tempo events by time
    all_tempo_events.sort(key=lambda x: x['time_ticks'])
    return all_tempo_events

def extract_time_signature_changes(midi_file: mido.MidiFile, tempo_events: List[Dict], initial_tempo: int) -> List[Dict[str, Any]]:
    """Extract all time signature changes from the MIDI file."""
    time_sig_changes = []

    log.info("Extracting Tempo")
    
    for track_num, track in enumerate(midi_file.tracks):
        track_time = 0
        
        for msg in track:
            track_time += msg.time
            
            if msg.type == 'time_signature':
                absolute_time = calculate_time_from_ticks(
                    track_time,
                    midi_file.ticks_per_beat,
                    tempo_events,
                    initial_tempo
                )
                time_sig_changes.append({
                    'numerator': msg.numerator,
                    'denominator': msg.denominator,
                    'time_ticks': track_time,
                    'time_ms': absolute_time * 1000,
                    'clocks_per_click': msg.clocks_per_click,
                    'notated_32nd_notes_per_beat': msg.notated_32nd_notes_per_beat,
                    'track': track_num
                })
    log.debug(time_sig_changes)
    time_sig_changes.sort(key=lambda x: x['time_ms'])
    return time_sig_changes

def extract_tempo_and_time_signature_changes(midi_file: mido.MidiFile, bpm: float):
    """Extract tempo changes with timing in milliseconds from MIDI file"""
    try:
        time_changes = {}
        ticks_per_beat = midi_file.ticks_per_beat
        all_tempo_events = extract_tempo_changes(midi_file)

        # Convert to milliseconds and create final tempo changes list
        current_time_ms = 0.0
        current_tempo = 60000000 / bpm
        last_time_ticks = 0
        
        # Add initial tempo if no tempo change at start
        if not all_tempo_events or all_tempo_events[0]['time_ticks'] > 0:
            bpm = mido.tempo2bpm(current_tempo)
            time_changes[0.0] = {
                'tempo': {
                    'time_ms': 0.0,
                    'bpm': round(bpm, 2),
                    'tempo': current_tempo
                }
            }
        
        for event in all_tempo_events:
            log.debug(f"current_time_ms: {current_time_ms}")
            # Calculate time in ms up to this tempo change
            if event['time_ticks'] > last_time_ticks:
                delta_ticks = event['time_ticks'] - last_time_ticks
                delta_ms = mido.tick2second(delta_ticks, ticks_per_beat, current_tempo) * 1000
                current_time_ms += delta_ms
            
            # Only add if tempo actually changed
            if current_tempo != event['tempo']:
                current_tempo = event['tempo']
                bpm = mido.tempo2bpm(event['tempo'])
                key = round(current_time_ms, 3)
                if key not in time_changes:
                    time_changes[key] = {}
                time_changes[key]['tempo'] = {
                    'time_ms': current_time_ms,
                    'bpm': round(bpm, 2),
                    'tempo': event['tempo']
                }
                log.info(f"Found tempo change: {bpm:.2f} BPM at {current_time_ms:.2f}ms")
            
            last_time_ticks = event['time_ticks']

        time_sig_changes = extract_time_signature_changes(midi_file, all_tempo_events, int(current_tempo))
        for time_sig_change in time_sig_changes:
            key = round(time_sig_change['time_ms'], 3)
            if key not in time_changes:
                time_changes[key] = {}
            time_changes[key]['time_signature'] = {
                'numerator': time_sig_change['numerator'],
                'denominator': time_sig_change['denominator']
            }
        log.debug(time_changes)
        log.info(f"Found {len(time_changes)} unique tempo changes")
        
    except Exception as e:
        logging.exception(e)
        log.error(f"Error parsing MIDI file: {e}")
        return []
    return time_changes