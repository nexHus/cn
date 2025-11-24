import cv2
import pyaudio
import threading
import numpy as np

# Audio configuration constants
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024


class AudioRecorder:
    # Handles audio recording from the microphone.

    def __init__(self):
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = None
            self.recording = False
        except Exception as e:
            print(f"[ERROR] Failed to initialize audio recorder: {e}")
            self.audio = None
            self.stream = None
            self.recording = False

    def start(self):
        # Starts the audio recording stream
        if self.audio is None:
            return
        try:
            self.recording = True
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
        except Exception as e:
            print(f"[ERROR] Failed to start audio recording: {e}")
            self.recording = False
            self.stream = None

    def get_chunk(self):
        # Reads a chunk of audio data from the stream.
        if self.recording and self.stream:
            try:
                return self.stream.read(CHUNK, exception_on_overflow=False)
            except:
                return None
        return None

    def stop(self):
        # Stops the audio recording and closes the stream
        self.recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass


class AudioPlayer:
    
    # Handles audio playback.
    

    def __init__(self):
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK,
            )
        except Exception as e:
            print(f"[ERROR] Failed to initialize audio player: {e}")
            self.audio = None
            self.stream = None

    def play(self, data):
        # Plays a chunk of audio data
        if self.stream:
            try:
                self.stream.write(data)
            except:
                pass

    def cleanup(self):
        # Stops the audio stream and releases resources.
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass


class VideoCamera:
    
    # Handles video capture from the webcam.
    

    def __init__(self):
        self.cap = None
        try:
            # Try opening default camera (0), then fallback to (1)
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(1)
                if not self.cap.isOpened():
                    print("[WARNING] No camera found. Using placeholder.")
                    self.cap = None
        except Exception as e:
            print(f"[ERROR] Failed to initialize camera: {e}")
            self.cap = None

    def get_frame_bytes(self):
        # Captures a frame, resizes it, and encodes it as JPEG bytes.
        frame = None
        if self.cap is not None and self.cap.isOpened():
            try:
                ret, read_frame = self.cap.read()
                if ret:
                    frame = read_frame
            except:
                pass

        # If no frame captured, create a placeholder black frame
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                frame,
                "NO CAMERA",
                (200, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )

        # Resize and encode frame
        frame = cv2.resize(frame, (240, 180))
        success, buffer = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30]
        )
        if success:
            return buffer.tobytes()
        return None

    def cleanup(self):
        # Releases the camera resource.
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
