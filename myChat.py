from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import run_async, run_js, set_env, eval_js
from pydub import AudioSegment
import io

import asyncio
import base64
import speech_recognition as sr
import tempfile
import os
import pyaudio
import wave

AudioSegment.converter = "/usr/local/bin/ffmpeg"
AudioSegment.ffmpeg = "/usr/local/bin/ffmpeg"
AudioSegment.ffprobe = "/usr/local/bin/ffprobe"

chat_msgs = []
online_users = set()

MAX_MESSAGES_COUNT = 400


def record_audio(duration=5, sample_rate=44100, chunk=1024, channels=1):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk)

    frames = []
    for i in range(0, int(sample_rate / chunk * (duration + 0.5))):
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
        wf = wave.open(temp_audio.name, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        return temp_audio.name


async def main():
    global chat_msgs
    put_html("""
    <style>
     body {
            background-color: #2f302f;
            color: white;
        }
        
        #input-container {
            background-color: #2f302f;
        }
        .card-header {
            color:#fff !important;
        }
        #pywebio-scope-ROOT {
        border: 2px solid #fff; /* Голубая рамка */
        border-radius: 10px; /* Скругленные углы */
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1), /* Основная тень */
                    0 6px 20px rgba(0, 0, 0, 0.1);
        padding: 15px;
         }
        .webio-scrollable.scrollable-border {
        border: 1px solid #fff;
        border-radius: 10px;
        }            
        .card {
            background-color:#2f302f;
            border: 2px solid #fff;
            border-radius: 10px;
        }
        
        .btn-primary {
            background-color: #4caf50;
            border-color: #4caf50;
            transition: background-color 0.3s ease, box-shadow 0.3s ease; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }
        
        .btn-primary:hover {
            background-color: #45a049; /* Цвет кнопки при наведении */
            border-color: #4caf50;
            box-shadow: 0 6px 8px rgba(0, 0, 0, 0.4); /* Тень при наведении */
        }
    
        .btn-primary:active {
            background-color: #3e8e41; /* Цвет кнопки при клике */
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2); /* Тень при клике */
            transform: translateY(2px); /* Небольшой сдвиг вниз при клике */
        }
        .footer {
            display:none
        }   
    </style>     
    <script>
    let mediaRecorder;
    let audioChunks = [];
    
    async function startRecording() {
        console.log("Начало записи");
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log("Доступ к микрофону получен");
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();
    
            mediaRecorder.addEventListener("dataavailable", event => {
                console.log("Получен фрагмент аудио");
                audioChunks.push(event.data);
            });
    
            mediaRecorder.addEventListener("stop", () => {
                console.log("Запись остановлена");
                const audioBlob = new Blob(audioChunks);
                sendAudioToServer(audioBlob);
                audioChunks = [];
            });
        } catch (err) {
            console.error("Ошибка при запуске записи:", err);
        }
    }
    
    function stopRecording() {
        console.log("Остановка записи");
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }
    
    function sendAudioToServer(audioBlob) {
        console.log("Отправка аудио на сервер");
        const reader = new FileReader();
        reader.onloadend = function() {
            const base64data = reader.result.split(',')[1];
            console.log("Аудио преобразовано в base64");
            
            // Use the correct PyWebIO function to send data
            py_send_data({'type': 'audio', 'data': base64data});
        };
        reader.readAsDataURL(audioBlob);
    }
    
    // Make functions globally accessible
    window.startRecording = startRecording;
    window.stopRecording = stopRecording;

    // Define a function to receive confirmation from the server
    window.audio_received = function() {
        console.log("Сервер подтвердил получение аудио");
    };
</script>
    """)
    set_env(title="LFchat")

    put_markdown('## Добро пожаловать в наш чат!!!')
    put_text(
        "Добро пожаловать в чат для общения! Здесь вы можете общаться с людьми из разных уголков мира и делиться своими мыслями и идеями в режиме реального времени. Будьте вежливы и уважайте других участников чата, и вы обязательно найдете новых интересных собеседников!")
    msg_box = output()
    put_scrollable(msg_box, height=300, keep_bottom=True)

    nickname = await input('Войти в чат', required=True, placeholder='Ваше имя',
                           validate=lambda n: "Такой ник уже используется" if n in online_users or n == '*' else None)
    online_users.add(nickname)

    chat_msgs.append(('Пользователь', f"`{nickname}` присоединился к чату!"))
    msg_box.append(put_markdown(f"`{nickname}` присоединился к чату!"))

    refresh_task = run_async(refresh_msg(nickname, msg_box))

    while True:
        data = await input_group("Новое сообщение!", [
            input(placeholder="Текст сообщения", name="msg"),
            file_upload(label="Загрузить изображение", name="image", accept="image/*"),
            actions(name="cmd",
                    buttons=["Отправить", 'Записать голосовое сообщение', {'label': "Выйти из чата", 'type': 'cancel'}])
        ], validate=lambda m: ('msg', 'Введите текст сообщения!') if m["cmd"] == 'Отправить' and not m["msg"] else None)

        if data is None:
            break

        if data['cmd'] == 'Записать голосовое сообщение':
            print("Начало записи голосового сообщения")
            toast("Запись голосового сообщения начнется через 3 секунды...")
            await asyncio.sleep(3)
            toast("Идет запись голосового сообщения...")

            run_js('startRecording()')
            await asyncio.sleep(6)  # Записываем 6 секунд
            run_js('stopRecording()')

            print("Ожидание аудиоданных от клиента")
            audio_data = await eval_js('new Promise(resolve => py_send_data = resolve)')

            print(f"Получены аудиоданные: {audio_data is not None}")

            if audio_data and audio_data.get('type') == 'audio':
                print("Обработка аудиоданных")
                audio_base64 = audio_data['data']
                audio_bytes = base64.b64decode(audio_base64)

                # Сохраняем аудио во временный файл
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
                    temp_audio.write(audio_bytes)
                    temp_audio_path = temp_audio.name

                print(f"Временный файл создан: {temp_audio_path}")

                try:
                    # Попытка преобразовать аудио в WAV
                    audio = AudioSegment.from_file(temp_audio_path)
                    wav_path = temp_audio_path + ".wav"
                    audio.export(wav_path, format="wav")

                    recognizer = sr.Recognizer()
                    with sr.AudioFile(wav_path) as source:
                        audio = recognizer.record(source)
                        text = recognizer.recognize_google(audio, language="ru-RU")
                        print(f"Распознанный текст: {text}")
                        msg_box.append(put_markdown(f"`{nickname}`: {text} (голосовое сообщение)"))
                        chat_msgs.append((nickname, text))

                    # Отображаем аудио-плеер
                    with open(temp_audio_path, "rb") as audio_file:
                        audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
                    audio_html = f'<audio controls src="data:audio/webm;base64,{audio_base64}"></audio>'
                    msg_box.append(put_html(audio_html))
                    chat_msgs.append((nickname, audio_html))

                except sr.UnknownValueError:
                    print("Голосовое сообщение не распознано")
                    msg_box.append(put_markdown(f"`{nickname}`: Голосовое сообщение не распознано"))
                    chat_msgs.append((nickname, "Голосовое сообщение не распознано"))
                except Exception as e:
                    print(f"Ошибка при обработке голосового сообщения: {str(e)}")
                    msg_box.append(put_markdown(f"`{nickname}`: Ошибка при обработке голосового сообщения: {str(e)}"))
                    chat_msgs.append((nickname, f"Ошибка при обработке голосового сообщения: {str(e)}"))
                finally:
                    # Удаляем временные файлы
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
                    if os.path.exists(wav_path):
                        os.remove(wav_path)

                run_js('audio_received()')
            else:
                print("Аудиоданные не получены или имеют неправильный формат")
            continue

        if data['msg']:
            message = f"`{nickname}`: {data['msg']}"
            chat_msgs.append((nickname, data['msg']))
            msg_box.append(put_markdown(message))

        if data['image']:
            img_data = base64.b64encode(data['image']['content']).decode('utf-8')
            img_html = f'<img src="data:image/png;base64,{img_data}" style="max-width:100%;height:auto;">'
            message = f"`{nickname}`: Изображение"
            chat_msgs.append((nickname, img_html))
            msg_box.append(put_markdown(message))
            msg_box.append(put_html(img_html))

    refresh_task.close()

    online_users.remove(nickname)
    toast("Вы вышли из чата!")
    msg_box.append(put_markdown(f"Пользователь `{nickname}` покинул чат!"))
    chat_msgs.append(('Этот', f"Пользователь `{nickname}` покинул чат!"))

    put_buttons(["Перезайти"], onclick=lambda btn: run_js('window.location.reload()'))




async def refresh_msg(nickname, msg_box):
    global chat_msgs
    last_idx = len(chat_msgs)

    while True:
        await asyncio.sleep(1)

        for m in chat_msgs[last_idx:]:
            if m[0] != nickname:
                msg_box.append(put_markdown(f"`{m[0]}`: {m[1]}"))

        if len(chat_msgs) > MAX_MESSAGES_COUNT:
            chat_msgs = chat_msgs[len(chat_msgs) // 2:]

        last_idx = len(chat_msgs)


if __name__ == "__main__":
    start_server(main, debug=True, port=7340, cdn=False)