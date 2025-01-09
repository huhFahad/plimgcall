import sys
import os
import time
import requests
import pygame
from threading import Thread
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from io import BytesIO

# Replace with your API URLs
API_GET_LATEST_PLAYLIST = "https://cloudbases.in/demoplatform/Robo/Robo_api/api_get_latest_playlist_id/1"
API_GET_PLAYLIST = "https://cloudbases.in/demoplatform/Robo/Robo_api/api_get_playlist/"

# Ensure the downloads folder exists
os.makedirs("downloads/audio", exist_ok=True)
os.makedirs("downloads/images", exist_ok=True)

# Signal class to handle updates in the GUI
class UpdateSignal(QObject):
    update_images = pyqtSignal(list)

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer")

        self.setWindowFlags(Qt.FramelessWindowHint)  # Removes the window border
        self.showFullScreen()  # Make the window full screen

        # Main widget and layout
        self.widget = QWidget()
        self.layout = QVBoxLayout()
        self.widget.setLayout(self.layout)
        self.widget.setStyleSheet("background-color: black;")
        self.setCentralWidget(self.widget)

        # Signal for updating images
        self.signal = UpdateSignal()
        self.signal.update_images.connect(self.update_image_display)

        # Default image path
        self.default_image_path = "downloads/centelonsolutions_logo.png"

    def fetch_image(self, url_or_path):
        try:
            # Check if the input is a local file path
            if os.path.exists(url_or_path):
                print(f"Loading image from local: {url_or_path}")
                return QPixmap(url_or_path)
            else:
                print(f"Attempting to download image: {url_or_path}")
                # Treat it as a URL and download the image
                response = requests.get(url_or_path)
                response.raise_for_status()
                image_data = BytesIO(response.content)

                # Save the image to disk for future use
                filename = os.path.join("downloads/images", url_or_path.split("/")[-1])
                with open(filename, "wb") as f:
                    f.write(image_data.read())

                print(f"Image downloaded and saved: {filename}")
                return QPixmap(filename)
        except Exception as e:
            print(f"Error fetching image from {url_or_path}: {e}")
            # Return the default image if there's an error
            return QPixmap(self.default_image_path)


    def update_image_display(self, image_urls):
        # Clear existing images
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        if not image_urls:
            image_urls = [self.default_image_path]

        # Add new images
        for url in image_urls:
            print(f"Attempting to load image: {url}")
            pixmap = self.fetch_image(url)
            if pixmap:
                label = QLabel(self)
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignCenter)

                # Ensure the image fills the screen, maintaining aspect ratio
                pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(pixmap)

                # Ensure the image is centered
                label.setAlignment(Qt.AlignCenter)
                label.setScaledContents(True)
                self.layout.addWidget(label)

class PlaylistMonitor(Thread):
    def __init__(self, viewer, interval=10):
        super().__init__()
        self.viewer = viewer
        self.interval = interval
        self.current_playlist_id = None
        self.running = True
        self.background_music = "downloads/Beat.mp3"  # Path to background music

    def fetch_latest_playlist_id(self):
        try:
            response = requests.get(API_GET_LATEST_PLAYLIST)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("id")
        except Exception as e:
            print(f"Error fetching latest playlist ID: {e}")
            return None

    def fetch_media_list(self, playlist_id):
        try:
            response = requests.get(f"{API_GET_PLAYLIST}{playlist_id}")
            response.raise_for_status()
            data = response.json()
            media_list = data.get("data", {}).get("media_list", [])
            return media_list
        except Exception as e:
            print(f"Error fetching media list: {e}")
            return []

    def run(self):
        # Initialize pygame mixer
        pygame.mixer.init()

        # Play background music on loop in a separate channel
        background_channel = pygame.mixer.Channel(0)  # Channel for background music
        if os.path.exists(self.background_music):
            background_sound = pygame.mixer.Sound(self.background_music)
            background_channel.play(background_sound, loops=-1)  # Loop indefinitely
            background_channel.set_volume(1.0)  # Full volume initially

        while self.running:
            try:
                # Check for latest playlist ID
                latest_playlist_id = self.fetch_latest_playlist_id()
                if latest_playlist_id and latest_playlist_id != self.current_playlist_id:
                    print(f"New playlist detected: {latest_playlist_id}")
                    self.current_playlist_id = latest_playlist_id

                    # Fetch the media list and update images and audio
                    media_list = self.fetch_media_list(latest_playlist_id)
                    image_urls_list = []
                    audio_urls_list = []

                    for media in media_list:
                        image_urls_list.append(media.get("images", []))
                        audio_urls_list.append(media.get("audio", ""))

                    # Loop through images and play audio
                    while self.running:
                        for idx, image_urls in enumerate(image_urls_list):
                            audio_url = audio_urls_list[idx]

                            # Update images
                            self.viewer.signal.update_images.emit(image_urls)

                            # Introduce a delay before playing the audio (e.g., 2 seconds)
                            delay_before_audio = 1  # Adjust delay as needed
                            time.sleep(delay_before_audio)

                            # Play audio if available
                            if audio_url:
                                self.download_audio(audio_url)
                                self.play_audio(audio_url, background_channel)  # Pass the background_channel here
                                # Get the duration of the audio
                                audio_filename = os.path.join("downloads/audio", audio_url.split("/")[-1])
                                sound = pygame.mixer.Sound(audio_filename)
                                audio_duration = sound.get_length()  # Duration of the audio

                                # Display image for the duration of the audio
                                time.sleep(audio_duration + 2)  # Display image for the audio duration plus 2 seconds

                        # After looping through the images and audio, restart from the beginning
                        print("Playlist cycle complete, restarting...")
                        time.sleep(self.interval)

                else:
                    image_urls = []
                    self.viewer.signal.update_images.emit(image_urls)

            except Exception as e:
                print(f"Error in monitoring: {e}")

            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def download_audio(self, audio_url):
        try:
            filename = os.path.join("downloads/audio", audio_url.split("/")[-1])

            # Check if the audio is already downloaded
            if os.path.exists(filename):
                return

            print(f"Downloading audio: {audio_url}")

            # Download audio
            response = requests.get(audio_url)
            response.raise_for_status()

            # Save the audio file to disk
            with open(filename, "wb") as f:
                f.write(response.content)

        except Exception as e:
            print(f"Error downloading audio from {audio_url}: {e}")

    def play_audio(self, audio_url, background_channel):
        # Play the downloaded audio using pygame
        filename = os.path.join("downloads/audio", audio_url.split("/")[-1])
        print(f"Playing audio: {filename}")
        try:
            media_channel = pygame.mixer.Channel(1)  # Use a separate channel for media audio
            sound = pygame.mixer.Sound(filename)

            # Lower the background music volume
            background_channel.set_volume(0.2)  # Reduce volume for background music
            media_channel.play(sound)

            # Wait for the media audio to finish
            while media_channel.get_busy():
                time.sleep(0.1)

            # Restore the background music volume
            background_channel.set_volume(1.0)  # Restore full volume

            return True
            
        except Exception as e:
            print(f"Error playing audio: {e}")

def main():
    app = QApplication(sys.argv)

    # Create the image viewer
    viewer = ImageViewer()
    viewer.show()

    # Start the playlist monitor
    monitor = PlaylistMonitor(viewer, interval=10)  # Check every 10 seconds
    monitor.daemon = True  # Make this a daemon thread
    monitor.start()

    # Ensure the monitor thread stops when the app closes
    app.aboutToQuit.connect(monitor.stop)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
