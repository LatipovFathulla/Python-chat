from pywebio import start_server
from pywebio.input import *
from pywebio.output import *
from pywebio.session import run_async, run_js, set_env, eval_js

import asyncio
import base64
import speech_recognition as sr
import tempfile
import os
import pyaudio
import wave

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
    set_env(title="UCChat")

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
            toast("Запись голосового сообщения начнется через 3 секунды...")
            await asyncio.sleep(3)
            toast("Идет запись голосового сообщения...")

            audio_file = record_audio(duration=6)

            recognizer = sr.Recognizer()
            try:
                with sr.AudioFile(audio_file) as source:
                    audio = recognizer.record(source)
                    text = recognizer.recognize_google(audio, language="ru-RU")
                    msg_box.append(put_markdown(f"`{nickname}`: {text} (голосовое сообщение)"))
                    chat_msgs.append((nickname, text))
            except sr.UnknownValueError:
                msg_box.append(put_markdown(f"`{nickname}`: Голосовое сообщение не распознано"))
                chat_msgs.append((nickname, "Голосовое сообщение не распознано"))
            except Exception as e:
                msg_box.append(put_markdown(f"`{nickname}`: Ошибка при обработке голосового сообщения: {str(e)}"))
                chat_msgs.append((nickname, f"Ошибка при обработке голосового сообщения: {str(e)}"))

            with open(audio_file, "rb") as audio:
                audio_data = base64.b64encode(audio.read()).decode('utf-8')

            audio_html = f'<audio controls src="data:audio/wav;base64,{audio_data}"></audio>'
            msg_box.append(put_html(audio_html))
            chat_msgs.append((nickname, audio_html))

            os.unlink(audio_file)
            continue

        if data['msg']:
            msg_box.append(put_markdown(f"`{nickname}`: {data['msg']}"))
            chat_msgs.append((nickname, data['msg']))

        if data['image']:
            img_url = put_image(data['image']['content'])
            msg_box.append(put_markdown(f"`{nickname}`: Изображение"))
            msg_box.append(img_url)
            chat_msgs.append((nickname, img_url))

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
    start_server(main, debug=True, port=8000, cdn=False)