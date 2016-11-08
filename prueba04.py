#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import random
import telepot 
import ConfigParser
from pushover import Client


def handle(msg):
	global chat_id, news_update
	chat_id = msg['chat']['id']
	command = msg['text']

	print 'Got command: %s from %i' %(command,chat_id)

	if command == '/start':
		if chat_id == -1:
			bot.sendMessage(chat_id, 'Bot arrancado, te tengo')
			client.send_message("Nueva conexión al bot", title="Telegram bot")
		else: 
			bot.sendMessage(chat_id, 'Para qué le das a start otra vez')
	elif command == '/help':
		bot.sendMessage(chat_id, 'Aqui vendría la ayuda')
	elif command == '/settings':
		bot.sendMessage(chat_id, 'Configuracion actual')
	elif command == '/newsOn':
		bot.sendMessage(chat_id, 'Noticias activadas')
		news_update = 1
	elif command == '/newsOff':
		bot.sendMessage(chat_id, 'Noticias desactivadas')
		news_update = 0


chat_id = -1
news_update = 0

config = ConfigParser.ConfigParser()
config.readfp(open(r'config.txt'))

TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
PUSHOVER_API = config.get('Tokens', 'pushover_api')
PUSHOVER_CLIENT = config.get('Tokens', 'pushover_client')

client = Client(PUSHOVER_CLIENT, api_token=PUSHOVER_API)
bot = telepot.Bot(TELEGRAM_TOKEN)

bot.message_loop(handle)
print('Listening ...')

client.send_message("Bot de teoría de redes arrancado", title="Telegram bot")

while 1: 
	time.sleep(10)
	if news_update == 1: 
		if chat_id == -1:
			print('Aquí hubo un error, no tengo chat id')
		else:
			bot.sendMessage(chat_id, 'Noticias de las')
			bot.sendMessage(chat_id, str(datetime.datetime.now()))




