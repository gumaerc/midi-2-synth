import copy
import math
import numpy as np
from synth_mapping_helper.pattern_generation import add_spiral
from synth_mapping_helper.synth_format import SynthFile, DataContainer
from synth_mapping_helper.utils import second_to_beat
import logging

from util import beats_per_measure_from_time_signature

log = logging.getLogger(__name__)
from audio import segment_beatmap_audio


def load_beatmap_from_synth(synth_file_path):
    """Load beatmap data from .synth file using SMH or fallback to manual extraction"""
    try:
        return SynthFile.from_synth(synth_file=synth_file_path)
    except Exception as e:
        log.error(f"Error loading beatmap with SMH: {e}")
        return False


def create_tempo_segment_with_audio(beatmap: SynthFile, segment, output_path):
    """Create a beatmap variant with specific BPM and audio segment matching the tempo duration"""
    log.debug(f"segment: {segment}")
    try:
        # Create a deep copy of the beatmap data
        beatmap_segment = copy.deepcopy(beatmap)

        # Update BPM and set Offset
        bpm = float(segment["bpm"])
        start_time = segment["start_ms"]
        end_time = segment["end_ms"]
        beatmap_segment.change_bpm(bpm)
        seconds_per_beat = 60 / bpm
        # Get time signature
        beats_per_measure = beats_per_measure_from_time_signature(
            {
                "numerator": segment["time_signature"]["numerator"],
                "denominator": segment["time_signature"]["denominator"],
            }
        )
        note_value = (
            segment["time_signature"]["denominator"] / 4
            if segment["time_signature"]
            else 1
        )
        seconds_per_measure = seconds_per_beat * beats_per_measure
        # The beatmap editor requires at least 2 seconds of silence
        silence_duration_seconds = 2
        remainder = silence_duration_seconds % seconds_per_measure
        if remainder == 0:
            time_to_next_1 = 0
        else:
            time_to_next_1 = seconds_per_measure - remainder
        total_offset = (
            0 if start_time == 0 else (silence_duration_seconds + time_to_next_1) * 1000
        )
        beatmap_segment.change_offset(total_offset)

        log.info(
            f"Creating segment: BPM={segment['bpm']}, Offset={total_offset}ms, {start_time:.2f}ms-{end_time:.2f}ms -> {output_path}"
        )

        # Extract the audio segment for this tempo section
        success = segment_beatmap_audio(beatmap, start_time, end_time, beatmap_segment)

        segment_length = end_time - start_time

        # Convert minimum delay to beats
        min_delay_beats = second_to_beat(2, beatmap_segment.bpm)
        log.debug(f"min_delay_beats: {min_delay_beats}")

        # Find the first measure boundary after min_delay_beats
        first_measure_after_delay = int(min_delay_beats // beats_per_measure) + 1
        log.debug(f"first_measure_after_delay: {first_measure_after_delay}")
        # The amount of beats until the first "1"
        start_beat = first_measure_after_delay * beats_per_measure
        log.debug(f"start_beat: {start_beat}")

        # Length of the segment in beats
        total_beats = (
            math.ceil(
                math.floor(second_to_beat(segment_length / 1000, beatmap_segment.bpm))
                / beats_per_measure
            )
            * beats_per_measure
        )
        if total_beats < beats_per_measure:
            total_beats = beats_per_measure
        log.debug(f"total_beats: {total_beats}")
        # Make sure the last beat falls on the last beat of a measure before the end of the segment
        end_beat = (total_beats // beats_per_measure) * beats_per_measure
        if start_time != 0:
            end_beat += start_beat
        log.debug(f"end_beat: {end_beat}")

        add_timing_notes(
            beatmap_segment,
            beats_per_measure=beats_per_measure,
            note_value=note_value,
            start_beat=start_beat,
            end_beat=end_beat,
        )

        if not success:
            raise RuntimeError(
                f"Failed to extract audio segment from {start_time}ms to {end_time}ms"
            )
        beatmap_segment.save_as(output_file=output_path)
        return True

    except Exception as e:
        log.error(f"Error creating tempo segment with audio: {e}")
        return False


def add_timing_notes(
    synth_file: SynthFile,
    difficulty: str = "Expert",
    start_beat: float = 0.0,
    end_beat: float = None,
    center_x: float = 0.0,
    center_y: float = 0.0,
    spiral_radius: float = 4.0,  # radius of spiral
    rotations_per_measure: float = 0.5,  # rotations per measure
    beats_per_measure: int = 4,
    note_value: float = 1.0,  # denominator of time signature
):
    """
    Add right-handed notes every quarter note to a SynthFile using spiral generation.

    Args:
        synth_file: The SynthFile to modify
        difficulty: Which difficulty to add notes to (default: "Expert")
        start_beat: Beat to start adding notes (default: 0.0)
        end_beat: Beat to stop adding notes (default: end of audio)
        center_x: X position center in grid coordinates (default: 0.0)
        center_y: Y position center in grid coordinates (default: 0.0)
        spiral_radius: Maximum radius of spiral (default: 3.0)
        rotations_per_measure: How many rotations per measure (default: 0.5)
        beats_per_measure: Beats per measure for hand switching (default: 4)
        note_value: Denominator of time signature (default: 1.0)
    """

    # Get or create the difficulty
    if difficulty not in synth_file.difficulties:
        synth_file.difficulties[difficulty] = DataContainer(bpm=synth_file.bpm)

    data_container = synth_file.difficulties[difficulty]

    # Calculate end beat if not provided (use audio duration)
    if end_beat is None:
        end_beat = second_to_beat(synth_file.audio.duration, synth_file.bpm)
        if start_beat > 0:
            end_beat += start_beat

    # Calculate total duration and beats per hand switch (2 measures)
    hand_switch_interval = beats_per_measure * 2  # 2 measures

    # Generate quarter note beats
    beat_times = np.arange(start_beat, end_beat + note_value, note_value)
    # Ensure we don't exceed end_beat
    beat_times = beat_times[beat_times <= end_beat]

    if len(beat_times) == 0:
        log.error(f"No beats to add between {start_beat} and {end_beat}")
        return

    log.info(
        f"Adding {len(beat_times)} beats from Start Beat: {start_beat} || End Beat: {end_beat} @ {synth_file.bpm}"
    )

    # Create base nodes with center coordinates and beat times
    # Shape: (n_beats, 3) where columns are [x, y, time]
    base_nodes = np.zeros((len(beat_times), 3))
    base_nodes[:, 0] = center_x  # x coordinates
    base_nodes[:, 1] = center_y  # y coordinates
    base_nodes[:, 2] = beat_times  # time coordinates

    # Calculate fidelity based on rotations per measure (your fix)
    total_measures = len(beat_times) / beats_per_measure
    spiral_times = total_measures * rotations_per_measure
    fidelity = (
        len(beat_times) / spiral_times if rotations_per_measure > 0 else len(beat_times)
    )

    # Generate spiral coordinates using the provided functions
    spiral_coords = add_spiral(
        nodes=base_nodes,
        fidelity=fidelity,
        radius=spiral_radius,
        start_angle=0.0,
        direction=1,
    )

    # Calculate beats per full rotation for direction reversal
    beats_per_rotation = beats_per_measure / rotations_per_measure

    # Add notes to appropriate hands
    for i, beat_time in enumerate(beat_times):
        # Determine direction based on completed rotations
        # Every full rotation (360°), reverse direction
        rotation_number = int((beat_time - start_beat) // beats_per_rotation)
        direction = (
            1 if rotation_number % 2 == 0 else -1
        )  # Alternate direction every rotation

        # If direction is reversed, flip the coordinates
        if direction == -1:
            # Reverse the spiral by flipping around center
            x_pos = center_x - (spiral_coords[i, 0] - center_x)
            y_pos = spiral_coords[i, 1]  # Keep y the same for horizontal flip
        else:
            x_pos = spiral_coords[i, 0]
            y_pos = spiral_coords[i, 1]

        # Determine which hand based on 2-measure intervals
        measure_number = int((beat_time - start_beat) // hand_switch_interval)
        is_right_hand = measure_number % 2 == 0  # Even measures = right, odd = left

        # Create note coordinates (1x3 array)
        note_coords = np.array([[x_pos, y_pos, beat_time]])

        # Add to appropriate hand dictionary
        if is_right_hand:
            data_container.right[beat_time] = note_coords
        else:
            data_container.left[beat_time] = note_coords
