import argparse
from pathlib import Path

from mido import MidiFile
import progressbar

from audio import create_tempo_segments
from beatmap import create_tempo_segment_with_audio, load_beatmap_from_synth
from midi import extract_tempo_and_time_signature_changes
from util import generate_segment_filename, validate_inputs
import logging


def main():
    parser = argparse.ArgumentParser(
        description="Create beatmap variants with audio segments matching MIDI tempo changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s song.mid output_dir --source base_map.synth
        """,
    )

    # Positional arguments
    parser.add_argument("midi", help="The MIDI input file containing tempo changes.")
    parser.add_argument(
        "output_dir", help="Directory where variant beatmaps will be saved."
    )

    # Required argument for base beatmap
    parser.add_argument(
        "--source", required=True, help="Path to base .synth file to use as template."
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s",
    )
    log = logging.getLogger(__name__)

    # Validate inputs
    if not validate_inputs(args.midi, args.source, args.output_dir):
        return 1

    output_dir = Path(args.output_dir)

    # Load base beatmap and get audio duration
    beatmap = load_beatmap_from_synth(args.source)
    if beatmap is None:
        return 1

    # Extract tempo changes from MIDI
    log.info("Extracting tempo changes from MIDI file...")
    midi_file = MidiFile(args.midi)
    tempo_and_time_changes = extract_tempo_and_time_signature_changes(
        midi_file, beatmap.bpm
    )

    if not tempo_and_time_changes:
        log.error("No tempo changes found in MIDI file.")
        return 1

    # Get audio duration from the source file
    log.info("Analyzing source audio duration...")
    audio_duration_ms = beatmap.audio.duration * 1000
    if audio_duration_ms is None:
        log.error("Error: Could not determine audio duration")
        return 1

    log.info(f"Source audio duration: {audio_duration_ms/1000.0:.2f} seconds")

    # Create tempo segments
    log.info("\nCreating tempo segments...")
    tempo_segments = create_tempo_segments(
        tempo_and_time_changes, audio_duration_ms, beatmap.bpm
    )

    if not tempo_segments:
        log.error("No tempo segments could be created.")
        return 1

    original_bpm = beatmap.bpm
    log.info(
        f"Base beatmap loaded: '{beatmap.meta.name}' by {beatmap.meta.artist}, mapped by {beatmap.meta.mapper}"
    )
    log.info(f"Original BPM: {original_bpm}, Offset: {beatmap.offset_ms}")

    # Generate variants with audio segments
    successful_variants = 0
    failed_variants = 0
    source_filename = Path(args.source).name

    log.info(
        f"\nGenerating {len(tempo_segments)} beatmap variants with tempo-matched audio segments..."
    )

    bar = progressbar.ProgressBar(max_value=len(tempo_segments))
    for i, segment in enumerate(tempo_segments):
        target_segment = segment

        output_filename = generate_segment_filename(
            source_filename,
            i,
            len(tempo_segments),
            segment,
        )
        output_path = output_dir / output_filename

        duration_sec = segment["duration_ms"] / 1000.0
        log.info(
            f"Creating segment {i+1}/{len(tempo_segments)}: {output_filename} (duration: {duration_sec:.2f}s)"
        )

        success = create_tempo_segment_with_audio(
            beatmap,
            target_segment,
            output_path,
        )

        if success:
            successful_variants += 1
        else:
            failed_variants += 1
            log.error(f"Failed to create segment {i+1}: {output_filename}")

        bar.update(i)
    bar.finish()

    # Summary
    log.info(f"\n{'='*60}")
    log.info(f"SUMMARY")
    log.info(f"{'='*60}")
    log.info(f"Total tempo changes found: {len(tempo_and_time_changes)}")
    log.info(f"Tempo segments created: {len(tempo_segments)}")
    log.info(f"Segments after filtering: {len(tempo_segments)}")
    log.info(f"Successful variants created: {successful_variants}")
    log.info(f"Failed variants: {failed_variants}")
    log.info(f"Output directory: {output_dir}")

    if successful_variants > 0:
        log.info(f"\n📁 Each variant contains:")
        log.info(f"   • Beatmap metadata with Offset = 0.0")
        log.info(f"   • Audio segment matching the tempo duration")
        log.info(f"   • Only audio that corresponds to the specific tempo section")

    if failed_variants > 0:
        log.error(
            f"\n⚠️  {failed_variants} variants failed to create. Check the error messages above."
        )
        return 1
    else:
        log.info(f"\n✅ All variants created successfully!")
        return 0


if __name__ == "__main__":
    main()
