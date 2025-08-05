import re
from pathlib import Path
from typing import List, Union, Optional
import dataclasses
from synth_mapping_helper.synth_format import SynthFile
from synth_mapping_helper.utils import second_to_beat
import logging
log = logging.getLogger(__name__)

def parse_segment_filename(filename: str) -> dict:
    """
    Parse segment filename to extract metadata.
    Expected format: TheCrowing_01_BPM170_0s-228.706s_dur228.706s_Segment.synth
    """
    pattern = r"(.+?)_(\d+)_BPM(\d+(?:\.\d+)?)(?:_TimeSignature(\d+)-(\d+))?_(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s_dur(\d+(?:\.\d+)?)s_Segment\.(.+)"
    match = re.match(pattern, filename)

    if not match:
        raise ValueError(f"Filename doesn't match expected pattern: {filename}")

    result = {
        "base_name": match.group(1),
        "segment_number": int(match.group(2)),
        "bpm": float(match.group(3)),
        "time_signature": {
            "numerator": int(match.group(4)),
            "denominator": int(match.group(5)),
        },
        "start_time": float(match.group(6)),
        "end_time": float(match.group(7)),
        "duration": float(match.group(8)),
        "file_extension": match.group(9),
    }
    return result


def merge_synth_segments(
    base_beatmap: Path,
    segments: List[Path],
) -> SynthFile:
    """
    Merge multiple SynthFile segments into a single continuous beatmap.

    Args:
        segments: List of file paths or SynthFile objects to merge
        target_bpm: Target BPM for the merged file (uses first segment's BPM if None)
        artist: Artist name (uses first segment's artist if None)
        mapper: Mapper name (uses first segment's mapper if None)

    Returns:
        SynthFile: Merged beatmap file
    """
    # Load and parse segments
    segment_data = []

    for segment in segments:
        # Parse filename for timing info
        filename_info = parse_segment_filename(segment.name)
        synth_file = SynthFile.from_synth(segment)
        segment_data.append((filename_info, synth_file))

    # Sort segments by start time to ensure correct order
    segment_data.sort(key=lambda x: x[0]["start_time"])

    if not segment_data:
        raise ValueError("No segments provided")

    base_beatmap_synth_file = SynthFile.from_synth(base_beatmap)

    # Create the merged file starting with the first segment
    merged_file = dataclasses.replace(base_beatmap_synth_file)

    # Process each segment
    for i, (info, segment_file) in enumerate(segment_data, 1):
        log.debug(info)
        # Create a copy to avoid modifying the original
        segment_copy = dataclasses.replace(segment_file)
        segment_copy.change_offset(0)

        # Get time signature
        beats_per_measure = (
            info["time_signature"]["numerator"] if "time_signature" in info else 4
        )
        log.debug(f"beats_per_measure: {beats_per_measure}")
        log.debug(f"i: {i}")

        # Calculate time offset in beats for this segment
        # Convert start time (seconds) to beats at target BPM
        start_time = info["start_time"]
        end_time = info["end_time"]
        log.debug(f"start_time: {start_time}")
        log.debug(f"end_time: {end_time}")

        # Offset all objects in this segment by the start time
        segment_copy.offset_everything(delta_s=start_time)
        notes = segment_copy.difficulties["Expert"]
        
        # Collect all note positions from all note types
        all_note_positions = []
        
        # Add positions from right hand notes
        if hasattr(notes, 'right') and notes.right.items():
            all_note_positions.extend(notes.right.keys())
        
        # Add positions from left hand notes
        if hasattr(notes, 'left') and notes.left.items():
            all_note_positions.extend(notes.left.keys())
            
        # Add positions from single notes
        if hasattr(notes, 'single') and notes.single.items():
            all_note_positions.extend(notes.single.keys())
            
        # Add positions from both hand notes
        if hasattr(notes, 'both') and notes.both.items():
            all_note_positions.extend(notes.both.keys())
        
        # Find first and last note positions across all note types
        if all_note_positions:
            first = min(all_note_positions)
            last = max(all_note_positions)
            total_notes = last - first
        else:
            # Handle case where no notes exist
            first = 0
            last = 0
            total_notes = 0
            log.warning(f"No notes found in segment {i}")

        segment_copy.bookmarks[first] = f"{segment_copy.bpm} BPM || Time Signature {beats_per_measure}/{4}"
        log.debug(f"first note after start time offset: {first}")
        log.debug(f"last note after start time offset: {last}")
        log.debug(f"total notes: {total_notes}")

        # Merge the offset segment into the main file
        merged_file.merge(segment_copy, adjust_bpm=True)
        log.info(
            f"Merged segment {i+1}/{len(segment_data)}: {info['start_time']:.3f}s-{info['end_time']:.3f}s"
        )

    return merged_file


def merge_synth_segments_from_folder(
    base_beatmap: Union[str, Path],
    folder_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None
) -> SynthFile:
    """
    Convenience function to merge all segment files from a folder.

    Args:
        folder_path: Path to folder containing segment files
        output_path: Optional path to save the merged file
        target_bpm: Target BPM for merged file (uses first segment if None)

    Returns:
        SynthFile: Merged beatmap file
    """
    folder = Path(folder_path)

    # Find all segment files
    segment_files = list(folder.glob("*_Segment.synth"))

    if not segment_files:
        raise ValueError(f"No segment files found in {folder}")

    log.info(f"Found {len(segment_files)} segment files")

    # Merge segments
    merged_file = merge_synth_segments(base_beatmap, segment_files)

    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        merged_file.save_as(output_path)
        log.info(f"Saved merged file to {output_path}")

    return merged_file