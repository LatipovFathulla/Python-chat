import pyaudio
import wave

def record_audio(filename, duration=5, sample_rate=44100, chunk=1024, channels=1):
    # Инициализация PyAudio
    audio = pyaudio.PyAudio()

    # Открытие потока
    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk)

    print("Запись началась...")

    frames = []

    # Запись аудио
    for i in range(0, int(sample_rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    print("Запись завершена.")

    # Остановка и закрытие потока
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Сохранение аудио в файл
    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()

    print(f"Аудио сохранено в файл: {filename}")

if __name__ == "__main__":
    record_audio("voice_message.wav", duration=5)