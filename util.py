import os
from pathlib import Path
import logging

log = logging.getLogger(__name__)


def validate_inputs(midi_file, source_synth, output_dir):
    """Validate all input parameters and create necessary directories"""
    errors = []

    # Check MIDI file
    if not os.path.exists(midi_file):
        errors.append(f"MIDI file '{midi_file}' does not exist.")
    elif not midi_file.lower().endswith((".mid", ".midi")):
        errors.append(f"File '{midi_file}' does not appear to be a MIDI file.")

    # Check source synth file
    if not os.path.exists(source_synth):
        errors.append(f"Source beatmap file '{source_synth}' does not exist.")
    elif not source_synth.lower().endswith(".synth"):
        errors.append(
            f"Source file '{source_synth}' does not appear to be a .synth file."
        )

    # Validate output directory path
    output_path = Path(output_dir)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        errors.append(f"Cannot create output directory '{output_dir}': {e}")

    if errors:
        for error in errors:
            log.error(f"Error: {error}")
        return False

    return True


def find_ogg_file_in_synth(temp_dir):
    """Find the ogg file in the extracted .synth directory"""

    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            if any(file.lower().endswith("ogg")):
                return os.path.join(root, file)

    return None


def generate_segment_filename(base_path, index, total_count, segment):
    """Generate output filename for tempo segments"""
    base_path = Path(base_path)
    stem = base_path.stem
    suffix = base_path.suffix

    # Determine number of digits needed for zero-padding
    digits = len(str(total_count))
    sequence_num = str(index + 1).zfill(digits)

    # Format BPM (remove decimal if it's a whole number)
    bpm_str = f"{segment['bpm']:g}"

    # Format start and end times in seconds
    start_sec = segment["start_ms"] / 1000.0
    end_sec = segment["end_ms"] / 1000.0
    duration_sec = segment["duration_ms"] / 1000.0

    start_str = f"{start_sec:.3f}".rstrip("0").rstrip(".")
    end_str = f"{end_sec:.3f}".rstrip("0").rstrip(".")
    duration_str = f"{duration_sec:.3f}".rstrip("0").rstrip(".")

    time_sig_str = ""

    if "time_signature" in segment:
        time_sig_str = f"_TimeSignature{segment['time_signature']['numerator']}-{segment['time_signature']['denominator']}"

    return f"{stem}_{sequence_num}_BPM{bpm_str}{time_sig_str}_{start_str}s-{end_str}s_dur{duration_str}s_Segment{suffix}"


def beats_per_measure_from_time_signature(time_signature):
    """Calculate beats per measure from time signature"""
    numerator = time_signature["numerator"] if "numerator" in time_signature else 4
    denominator = (
        time_signature["denominator"] if "denominator" in time_signature else 4
    )
    ratio = denominator / 4
    beats_per_measure = int(numerator / ratio)
    log.debug(f"numerator: {numerator}")
    log.debug(f"denominator: {denominator}")
    log.debug(f"ratio: {ratio}")
    log.debug(f"beats_per_measure: {beats_per_measure}")
    return beats_per_measure
