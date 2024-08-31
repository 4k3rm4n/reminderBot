import json
import telebot
from telebot import types
import requests
import re
from datetime import datetime, timedelta
import sqlite3
import schedule
import time
import threading

pattern_date = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$'
pattern_timer = r'^(?:(\d+)[Dd] )?(?:(\d+)[Hh] )?(?:(\d+)[Mm])?$'
pattern_offset = r'([+-]\d{1,2}|0)'
bot = telebot.TeleBot('****')
API = '****'
date = ''
text = ''


#⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️ testing
@bot.message_handler(commands=['spam'])
def spam(message):
    if super_user_validation(message):
        bot.send_message(message.chat.id, 'write user name')
        bot.register_next_step_handler(message, spam_set_username)
    else:
        bot.send_message(message.chat.id, 'sorry, you dont have permission')


#⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️ select error exeption
def spam_set_username(message):
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    cur.execute("SELECT chat_id FROM users_offset WHERE user_name = '%s'" % message.text.strip())

    table = cur.fetchall()
    chat_id = int(table[0][0])
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, 'write the message you want to spam someone')
    bot.register_next_step_handler(message, spam_finishing, chat_id)


def spam_finishing(message, chat_id):
    for i in range(10):
        bot.send_message(chat_id, f'{message.text}')
    bot.send_message(message.chat.id, 'all done')
#⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️ testing


@bot.message_handler(commands=['update_utc_offset'])
def update_utc_offset(message):
    bot.send_message(message.chat.id, 'write the UTC offset in format "+3" or "0"')
    if is_valid_offset(message.text.strip()):
        try:
            conn = sqlite3.connect('users.sql')
            cur = conn.cursor()

            cur.execute("UPDATE users_offset SET utc_offset = '%i' WHERE chat_id = '%i'" % (int(message.text.strip()), message.chat.id))

            conn.commit()
            cur.close()
            conn.close()
            bot.send_message(message.chat.id, 'offset updated successfully')
            markup_message_reminder(message)
            markup_message_reminder(message)
        except sqlite3.OperationalError:
            bot.send_message(message.chat.id, 'looks like you havent set your UTC offset yet')
    else:
        bot.send_message(message.chat.id, 'something went wrong')
        bot.register_next_step_handler(message, update_utc_offset)


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add(types.InlineKeyboardButton('/reminder'))
    markup.add(types.InlineKeyboardButton('/weather'))
    bot.send_message(message.chat.id, 'this bot can give you info about weather in your city')
    bot.send_message(message.chat.id, 'also work as reminder', reply_markup=markup)


@bot.message_handler(commands=['reminder'])
def main_reminder(message):
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    cur.execute('CREATE TABLE IF NOT EXISTS users_offset (chat_id int, utc_offset, user_name varchar(50))')
    cur.execute("SELECT count(*) FROM users_offset WHERE chat_id = '%i'" % message.chat.id)
    table = cur.fetchall()
    count_of_records = int(table[0][0])

    conn.commit()
    cur.close()
    conn.close()

    if count_of_records == 0:
        bot.send_message(message.chat.id, 'plz set your UTC offset')
        bot.send_message(message.chat.id, 'write the UTC offset in format "+3" or "0"')
        bot.register_next_step_handler(message, save_offset)
    else:
        markup_message_reminder(message)


def save_offset(message):
    if is_valid_offset(message.text.strip()):
        conn = sqlite3.connect('users.sql')
        cur = conn.cursor()

        cur.execute("INSERT INTO users_offset (chat_id, utc_offset, user_name) VALUES ('%i', '%i', '%s')" % (message.chat.id, int(message.text.strip()), f'@{message.from_user.username}'))

        conn.commit()
        cur.close()
        conn.close()

        bot.send_message(message.chat.id, 'offset saved successfully, thx')
        markup_message_reminder(message)
    else:
        bot.send_message(message.chat.id, 'something went wrong')
        bot.send_message(message.chat.id, 'write the UTC offset in format "+3" or "0"')
        bot.register_next_step_handler(message, save_offset)


def save_date_lite(message):
    global date
    if is_valid_datetime(message.text.strip()):
        dt = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        delta = timedelta(hours=get_user_utc_offset(message))
        temp_date = dt - delta
        date = temp_date.strftime('%Y-%m-%d %H:%M')
        bot.send_message(message.chat.id, 'date saved successfully')
        bot.send_message(message.chat.id, 'now write a reminder text')
        bot.register_next_step_handler(message, save_text_lite)
    else:
        bot.send_message(message.chat.id, 'Invalid date, try again')
        bot.send_message(message.chat.id, 'plz write the date in format "2020-07-22 15:32"')
        bot.send_message(message.chat.id, 'also make sure it is a date from the future')
        bot.register_next_step_handler(message, save_date_lite)


def save_text_lite(message):
    global text
    text = message.text
    bot.send_message(message.chat.id, 'text saved successfully')
    #bot.send_message(message.chat.id, f'date: {date}, text: {text}')
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    cur.execute('CREATE TABLE IF NOT EXISTS users (chat_id int, date varchar(20), text varchar(1000), count_record int)')
    cur.execute("SELECT count(*) FROM users WHERE chat_id = '%i'" % message.chat.id)

    table = cur.fetchall()
    count_of_records = int(table[0][0])

    cur.execute("INSERT INTO users (chat_id, date, text, count_record) VALUES ('%i', '%s', '%s', '%i')" % (message.chat.id, date, text, count_of_records + 1))

    conn.commit()
    cur.close()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('your reminders', callback_data='reminders'))
    markup.add(types.InlineKeyboardButton('go to menu', callback_data='menu'))
    bot.send_message(message.chat.id, 'remind registered successfully', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def select(call):
    if call.data == 'reminders':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('go to menu', callback_data='menu'))
        try:
            conn = sqlite3.connect('users.sql')
            cur = conn.cursor()

            cur.execute("SELECT count_record, date, text FROM users WHERE chat_id = '%i' ORDER BY count_record ASC" % call.message.chat.id)

            user_offset = get_user_utc_offset(call.message)
            table = cur.fetchall()
            info = ''
            for el in table:
                delta = timedelta(hours=user_offset)
                dt = datetime.strptime(el[1], "%Y-%m-%d %H:%M")
                temp_date = dt + delta
                res_date = temp_date.strftime('%Y-%m-%d %H:%M')
                info += f'({el[0]})  date: {res_date}, text: {el[2]}\n'
            cur.close()
            conn.close()
            if len(info) == 0:
                bot.send_message(call.message.chat.id, 'u have no reminders', reply_markup=markup)
            else:
                markup.add(types.InlineKeyboardButton('delete record', callback_data='delete'))
                bot.send_message(call.message.chat.id, info, reply_markup=markup)
        except sqlite3.OperationalError:
            bot.send_message(call.message.chat.id, 'something went wrong')
    if call.data == 'menu':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
        start(call.message)
    if call.data == 'set':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
        bot.send_message(call.message.chat.id, 'plz write the date in format "2020-07-22 15:32"')
        bot.register_next_step_handler(call.message, save_date_lite)
    if call.data == 'setTimer':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
        bot.send_message(call.message.chat.id, 'plz write time in format "01D 13H 22M"')
        bot.register_next_step_handler(call.message, save_date_timer)
    if call.data == 'delete':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                      reply_markup=None)
        bot.send_message(call.message.chat.id, 'plz enter the remind number, you want to delete')
        bot.register_next_step_handler(call.message, delete_record)


def save_date_timer(message):
    global date
    if is_valid_timer(message.text.strip()):
        match = re.match(pattern_timer, message.text.strip())
        res_in_m = int(match.group(3)) if match.group(3) else 0
        res_in_h = int(match.group(2)) if match.group(2) else 0
        res_in_d = int(match.group(1)) if match.group(1) else 0
        delta = timedelta(days=res_in_d, hours=res_in_h, minutes=res_in_m)
        timer_time = delta + datetime.now()
        date = timer_time.strftime('%Y-%m-%d %H:%M')
        bot.send_message(message.chat.id, 'time saved successfully')
        bot.send_message(message.chat.id, 'now write a reminder text')
        bot.register_next_step_handler(message, save_text_lite)
    else:
        bot.send_message(message.chat.id, 'Invalid time, try again')
        bot.send_message(message.chat.id, 'plz write time in format "01D 13H 22M"')
        bot.register_next_step_handler(message, save_date_timer)


def is_valid_datetime(datetime_string):
    if re.match(pattern_date, datetime_string):
        try:
            dt = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M")
            if dt > datetime.now():
                return True
        except ValueError:
            return False
    return False


def is_valid_timer(datetime_string):
    if re.match(pattern_timer, datetime_string):
        if len(datetime_string) != 0:
            return True
    return False


def is_valid_offset(string_offset):
    if re.match(pattern_offset, string_offset):
        if len(string_offset) != 0:
            return True
    return False


def delete_record(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('your reminders', callback_data='reminders'))
    markup.add(types.InlineKeyboardButton('go to menu', callback_data='menu'))
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM users WHERE chat_id = '%i' and count_record = '%i'" % (message.chat.id, int(message.text.strip())))
    table = cur.fetchall()
    count_of_records = int(table[0][0])
    if count_of_records == 1:
        cur.execute("DELETE FROM users WHERE chat_id = '%i' and count_record = '%i'" % (message.chat.id, int(message.text.strip())))
        bot.send_message(message.chat.id, 'remind deleted successfully', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'something went wrong, try again')
        bot.send_message(message.chat.id, 'plz enter the remind number, you want to delete')
        bot.register_next_step_handler(message, delete_record)
    conn.commit()
    cur.close()
    conn.close()


@bot.message_handler(commands=['clear_tables'])
def clear_db(message):
    if super_user_validation(message):
        conn = sqlite3.connect('users.sql')
        cur = conn.cursor()

        cur.execute('DROP TABLE IF EXISTS users')
        cur.execute('DROP TABLE IF EXISTS users_offset')
        conn.commit()
        cur.close()
        conn.close()

        bot.send_message(message.chat.id, 'tables users and users_offset was deleted')
    else:
        bot.send_message(message.chat.id, 'sorry, you dont have permission')


@bot.message_handler(commands=['check_tables'])
def check_db(message):
    if super_user_validation(message):
        try:
            conn = sqlite3.connect('users.sql')
            cur = conn.cursor()

            cur.execute('SELECT * FROM users')

            table = cur.fetchall()
            info = 'users table:\n'
            for el in table:
                info += f'({el[0]}) ({el[3]})  date: {el[1]}, text: {el[2]}\n'

            info += 'users_offset table:\n'

            cur.execute('SELECT * FROM users_offset')

            table = cur.fetchall()
            for el in table:
                info += f'id: {el[0]}  offset: {el[1]}  user name: {el[2]}\n'

            cur.close()
            conn.close()
            bot.send_message(message.chat.id, info)
        except sqlite3.OperationalError:
            bot.send_message(message.chat.id, 'something went wrong')
    else:
        bot.send_message(message.chat.id, 'sorry, you dont have permission')


def check_remind():
    #bot.send_message(message.chat.id, f"TEST:   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    try:
        conn = sqlite3.connect('users.sql')
        cur = conn.cursor()

        cur.execute("SELECT * FROM users")

        table = cur.fetchall()
        info = ''
        for el in table:
            dt = datetime.strptime(el[1], "%Y-%m-%d %H:%M")
            if dt <= datetime.now():
                info = f'❗️❗️❗️PLZ DONT FORGET->: {el[2]}\n'
                bot.send_message(el[0], info)
                cur.execute("DELETE FROM users WHERE chat_id = '%i' and date = '%s' and text = '%s'" % (el[0], el[1], el[2]))
        conn.commit()
        cur.close()
        conn.close()
    except sqlite3.OperationalError:
        return


def get_user_utc_offset(message) -> int:
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    cur.execute("SELECT utc_offset FROM users_offset WHERE chat_id = '%i'" % message.chat.id)

    table = cur.fetchall()
    utc_offset_user = table[0][0]
    cur.close()
    conn.close()
    return int(utc_offset_user)


def markup_message_reminder(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('your reminders', callback_data='reminders'))
    markup.add(types.InlineKeyboardButton('set new remind', callback_data='set'))
    markup.add(types.InlineKeyboardButton('set timer mode', callback_data='setTimer'))
    bot.send_message(message.chat.id, 'check your reminders or set new one', reply_markup=markup)


def super_user_validation(message) -> bool:
    if message.from_user.username == 'akk3rm4n':
        return True
    return False


@bot.message_handler(commands=['weather'])
def weather(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add(types.InlineKeyboardButton('Kyiv'))
    markup.add(types.InlineKeyboardButton('Borova'))
    markup.add(types.InlineKeyboardButton('Odesa'))
    markup.add(types.InlineKeyboardButton('Lviv'))
    bot.send_message(message.chat.id, 'enter city, or choose one from below', reply_markup=markup)
    bot.register_next_step_handler(message, main_weather)


def main_weather(message):
    city = message.text.strip().lower()
    res = requests.get(f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API}&units=metric')
    if res.status_code == 200:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('go to menu', callback_data='menu'))
        data = json.loads(res.text)
        bot.reply_to(message, f'country: {data["sys"]["country"]}, city: {data["name"]}')
        bot.send_message(message.chat.id, f'temp: {data["main"]["temp"]}, feels like: {data["main"]["feels_like"]}  , humidity: {data["main"]["humidity"]}')
        bot.send_message(message.chat.id, 'use "/weather" to get weather again', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'invalid city, try again')
        bot.register_next_step_handler(message, main_weather)


def schedule_checker():
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    schedule.every(1).minutes.do(check_remind)
    schedule_thread = threading.Thread(target=schedule_checker)
    schedule_thread.start()


bot.polling(none_stop=True)
