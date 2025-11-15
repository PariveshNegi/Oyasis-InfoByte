import speech_recognition as sr
import playsound
import datetime
import wikipedia
from gtts import gTTS
import pyglet
import os
import time

def speak(text):
    print(f"Assistant: {text}")
    tts = gTTS(text=text, lang='en')
    filename = "voice.mp3"
    tts.save(filename)

    music = pyglet.media.load(filename, streaming=False)
    music.play()

    time.sleep(music.duration)
    os.remove(filename)

def listen():
    """Capture voice input and convert it to text."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        recognizer.pause_threshold = 1
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        except sr.WaitTimeoutError:
            print("⏳ Timeout — no speech detected.")
            return ""
    try:
        print("🧠 Recognizing...")
        query = recognizer.recognize_google(audio, language='en-in')
        print(f"You said: {query}")
    except sr.UnknownValueError:
        speak("Sorry, I didn’t catch that. Please say it again.")
        return ""
    except sr.RequestError:
        speak("There’s a problem connecting to the internet.")
        return ""
    return query.lower()

def process_command(command):
    """Respond to specific voice commands."""
    if "hello" in command or "hi" in command:
        speak("Hello there! How can I assist you today?")
    
    elif "time" in command:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The current time is {current_time}")
    
    elif "date" in command:
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        speak(f"Today's date is {current_date}")
    
    elif "search" in command:
        speak("What would you like me to search for?")
        query = listen()
        if query:
            try:
                result = wikipedia.summary(query, sentences=2)
                speak("According to Wikipedia...")
                speak(result)
            except wikipedia.exceptions.DisambiguationError:
                speak("That topic is too broad. Please be more specific.")
            except wikipedia.exceptions.PageError:
                speak("I couldn't find anything on that.")
    
    elif "exit" in command or "stop" in command or "quit" in command:
        speak("Goodbye! Have a great day.")
        exit()
    
    else:
        speak("Sorry, I didn’t understand that command.")

def main():
    speak("Voice assistant activated. To search something, you can say search, and wait for responces.")
    while True:
        command = listen()
        if command:
            process_command(command)

if __name__ == "__main__":
    main()
