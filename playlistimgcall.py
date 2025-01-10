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
import json

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
            local_image_path = os.path.join("downloads/images", url_or_path.split("/")[-1])
            
            if os.path.exists(local_image_path):
                print(f"Loading image from local: {local_image_path}")
                return QPixmap(local_image_path)
            else:
                print(f"Attempting to download image: {url_or_path}")
                # Treat it as a URL and download the image
                response = requests.get(url_or_path)
                response.raise_for_status()
                image_data = BytesIO(response.content)

                # Save the image to disk for future use
                with open(local_image_path, "wb") as f:
                    f.write(image_data.read())

                print(f"Image downloaded and saved: {local_image_path}")
                return QPixmap(local_image_path)
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

    def save_playlist_data(self, playlist_id, media_list):
        data = {
            "playlist_id": playlist_id,
            "media_list": media_list
        }
        
        # Remove the old playlist data if it exists
        if os.path.exists("playlist_data.json"):
            os.remove("playlist_data.json")

        with open("playlist_data.json", "w") as f:
            json.dump(data, f)
        print(f"Playlist {playlist_id} saved locally.")

    def load_playlist_data(self):
        try:
            with open("playlist_data.json", "r") as f:
                data = json.load(f)
                print(f"Loaded playlist data for ID: {data['playlist_id']}")
                return data["playlist_id"], data["media_list"]
        except Exception as e:
            print(f"Error loading playlist data: {e}")
            return None, None

    def play_media_list(self, media_list, background_channel):
        for media in media_list:
            image_urls = media.get("images", [])
            audio_url = media.get("audio", "")

            # Update images
            self.viewer.signal.update_images.emit(image_urls)

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
                # Load the saved playlist ID and media if available
                self.current_playlist_id, media_list = self.load_playlist_data()

                # If no playlist loaded or network is available, check for a new playlist
                latest_playlist_id = self.fetch_latest_playlist_id()
                print(f"latest_playlist_id : {latest_playlist_id}")
                print(f"current_playlist_id : {self.current_playlist_id}")

                if latest_playlist_id:
                    # If a new playlist ID is fetched, and it differs from the current one, play it
                    if latest_playlist_id != self.current_playlist_id:
                        print(f"New playlist detected: {latest_playlist_id}")
                        self.current_playlist_id = latest_playlist_id

                        # Fetch the media list for the new playlist and play it
                        media_list = self.fetch_media_list(latest_playlist_id)
                        self.save_playlist_data(latest_playlist_id, media_list)
                        self.play_media_list(media_list, background_channel)

                    else:
                        print("No new ID fetched. Falling back to the last playlist.")
                        if self.current_playlist_id:
                            # Fallback to the last known playlist if no new ID is found
                            self.play_media_list(media_list, background_channel)

                else:
                    # No playlist ID fetched, waiting for the network
                    print("No playlist available. Waiting for network connection...")
                    if self.current_playlist_id:
                        # Fallback to the last known playlist if no new ID is found
                        self.play_media_list(media_list, background_channel)

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
