import subprocess
import os
import imageio_ffmpeg as ffmpeg
import logging
import warnings

# Configure logging to a suitable level for monitoring and debugging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Suppress warnings
warnings.filterwarnings("ignore")


class AudioExtractor:
    """
    A class to handle the extraction of audio from a video file using FFmpeg.

    Attributes:
    -----------
    input_video : str
        Path to the input video file.
    output_audio : str
        Path to the output audio file (with '.wav' extension).
    ffmpeg_path : str
        Path to the FFmpeg executable.

    Methods:
    --------
    get_audio_duration() -> float:
        Returns the duration of the extracted audio in seconds.
    extract_audio() -> float:
        Extracts the audio from the input video and returns its duration.
    """

    def __init__(self, input_video: str, output_audio: str):
        """
        Initializes an instance of AudioExtractor with the provided input video
        and output audio paths. Validates and ensures that the output audio file
        has the correct '.wav' extension.

        Parameters:
        -----------
        input_video : str
            Path to the input video file.
        output_audio : str
            Path to the output audio file.
        """
        self.input_video = input_video
        self.output_audio = self._validate_audio_extension(output_audio)
        self.ffmpeg_path = ffmpeg.get_ffmpeg_exe()

    def _validate_audio_extension(self, output_audio: str) -> str:
        """
        Ensures that the output audio file has a '.wav' extension. If not, appends '.wav'.

        Parameters:
        -----------
        output_audio : str
            Path to the output audio file.

        Returns:
        --------
        str
            Validated output audio file path with '.wav' extension.
        """
        if not output_audio.endswith(".wav"):
            output_audio += ".wav"
            logging.warning(
                f"Output file extension missing or incorrect. Updated to: {output_audio}"
            )
        return output_audio

    def _create_output_directory(self):
        """
        Creates the output directory if it doesn't exist.
        """
        output_dir = os.path.dirname(self.output_audio)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")

    def extract_audio(self) -> float:
        """
        Extracts the audio from the input video file using FFmpeg and returns its duration.

        Returns:
        --------
        float
            Duration of the extracted audio in seconds.

        Raises:
        -------
        RuntimeError
            If an error occurs during audio extraction.
        """
        self._create_output_directory()
        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            self.input_video,
            "-ac",
            "2",
            "-ar",
            "44100",
            "-vn",
            self.output_audio,
        ]
        try:
            logging.info(f"Extracting audio from video: {self.input_video}")
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logging.info(f"Audio extracted successfully to {self.output_audio}")
            return self.output_audio
        except subprocess.CalledProcessError as e:
            logging.error(f"Error during audio extraction: {e}")
            raise RuntimeError("Audio extraction failed") from e


# if __name__ == "__main__":
#     # Example usage with paths for input video and output audio
#     input_video = r"D:\project\test.mp4"
#     output_audio = r'outputs\output_audio.wav'
#     extractor = AudioExtractor(input_video, output_audio)
#     duration = extractor.extract_audio()