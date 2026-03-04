import telebot

# СЮДА ВСТАВЬ ТОКЕН ОТ @BotFather
API_TOKEN = '8590026400:AAG_C5JKs-Apkrb-eoYPyBepkbWRsfGC0FY'
bot = telebot.TeleBot(API_TOKEN)

users = {} 
search_queue = []

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🎭 Добро пожаловать в Maska! Нажми /search")

@bot.message_handler(commands=['search'])
def search(message):
    uid = message.chat.id
    if uid in users:
        bot.send_message(uid, "Вы уже в чате! /stop")
        return
    if uid not in search_queue:
        search_queue.append(uid)
        bot.send_message(uid, "🔍 Ищу собеседника...")
    if len(search_queue) >= 2:
        u1 = search_queue.pop(0)
        u2 = search_queue.pop(0)
        users[u1], users[u2] = u2, u1
        bot.send_message(u1, "🎭 Собеседник найден! Пиши привет.")
        bot.send_message(u2, "🎭 Собеседник найден! Пиши привет.")

@bot.message_handler(commands=['stop'])
def stop(message):
    uid = message.chat.id
    if uid in users:
        p = users.pop(uid)
        users.pop(p, None)
        bot.send_message(uid, "Чат окончен. 🛑")
        bot.send_message(p, "Собеседник покинул чат. 🛑")
    elif uid in search_queue:
        search_queue.remove(uid)
        bot.send_message(uid, "Поиск остановлен.")

@bot.message_handler(content_types=['text'])
def echo(message):
    uid = message.chat.id
    if uid in users:
        bot.send_message(users[uid], message.text)

bot.polling(none_stop=True)
