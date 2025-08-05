import argparse
from merging import merge_synth_segments_from_folder

import logging


if __name__ == "__main__":

    def main():
        parser = argparse.ArgumentParser(
            description="Create beatmap variants with audio segments matching MIDI tempo changes.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=""" 
Examples:
  %(prog)s /path/to/base_map.synth /path/to/input_dir /path/to/output_file.synth
        """,
        )
        # Positional arguments
        parser.add_argument(
            "base_beatmap", help="Path to base .synth file to use as the template."
        )
        parser.add_argument(
            "input_dir", help="The input directory containing segment files."
        )
        parser.add_argument(
            "output_file",
            help="Directory and filename where the meged beatmap will be saved.",
        )
        args = parser.parse_args()
        base_beatmap = args.base_beatmap
        input = args.input_dir
        output = args.output_file

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)-12s - %(levelname)-8s - %(message)s",
        )

        merge_synth_segments_from_folder(base_beatmap, input, output)

    main()
