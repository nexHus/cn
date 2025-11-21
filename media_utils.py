import cv2
import pyaudio
import threading
import numpy as np

# Audio Config
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Reduced from 44100 to save bandwidth
CHUNK = 1024


class AudioRecorder:
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
        if self.recording and self.stream:
            try:
                return self.stream.read(CHUNK, exception_on_overflow=False)
            except:
                return None
        return None

    def stop(self):
        self.recording = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass


class AudioPlayer:
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
        if self.stream:
            try:
                self.stream.write(data)
            except:
                pass

    def cleanup(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass


class VideoCamera:
    def __init__(self):
        self.cap = None
        try:
            # Try index 0 first
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                # Try index 1 (common for external cams or virtual cams)
                self.cap = cv2.VideoCapture(1)
                if not self.cap.isOpened():
                    print("[WARNING] No camera found. Using placeholder.")
                    self.cap = None
        except Exception as e:
            print(f"[ERROR] Failed to initialize camera: {e}")
            self.cap = None

    def get_frame_bytes(self):
        frame = None
        if self.cap is not None and self.cap.isOpened():
            try:
                ret, read_frame = self.cap.read()
                if ret:
                    frame = read_frame
            except:
                pass

        if frame is None:
            # Generate a placeholder frame (black image with text)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Add some noise or movement so it looks like a stream?
            # Just static text is fine for now.
            cv2.putText(
                frame,
                "NO CAMERA",
                (200, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )

        # Downscale more for network performance (smaller resolution = less data)
        frame = cv2.resize(frame, (240, 180))
        # Compress to JPEG with lower quality for speed
        success, buffer = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30]
        )
        if success:
            return buffer.tobytes()
        return None

    def cleanup(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except:
                pass
