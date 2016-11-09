#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import random
import telepot 
import logging
import ConfigParser
from pushover import Client

start_done = {}
news_update = {}
unique_users = set()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='activity.log',
                    filemode='a')


def handle(msg):
	global news_update
	chat_id = msg['chat']['id']
	command = msg['text']
	key = str(chat_id)

	print 'Comando %s from %i' %(command,chat_id)

	if command == '/start':
		logging.info('Comando /start de %s', chat_id)
		if key in start_done:
			bot.sendMessage(chat_id, 'Ya tenías hecho el start')
		else:
			bot.sendMessage(chat_id, 'Bot inicializado, noticias OFF por defecto')
			start_done[key] = 1
			news_update[key] = 0
			unique_users.add(chat_id)
			#client.send_message("Nueva conexión al bot", title="Telegram bot")
	elif command == '/help':
		logging.info('Comando /help de %s', chat_id)
		bot.sendMessage(chat_id, 'Aqui vendría la ayuda')
	elif command == '/settings':
		logging.info('Comando /settings de %s', chat_id)
		bot.sendMessage(chat_id, 'Configuracion actual: News %i' %news_update[key])
	elif command == '/newsOn':
		logging.info('Comando /newsOn de %s', chat_id)
		bot.sendMessage(chat_id, 'Noticias activadas')
		news_update[key] = 1
	elif command == '/newsOff':
		logging.info('Comando /newsOff de %s', chat_id)
		bot.sendMessage(chat_id, 'Noticias desactivadas')
		news_update[key] = 0
	elif command == '/stats':
		logging.info('Comando /stats de %s', chat_id)
		bot.sendMessage(chat_id, 'En total he visto %i IDs' % len(unique_users))
		


config = ConfigParser.ConfigParser()
config.readfp(open(r'config.txt'))

TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
PUSHOVER_API = config.get('Tokens', 'pushover_api')
PUSHOVER_CLIENT = config.get('Tokens', 'pushover_client')

client = Client(PUSHOVER_CLIENT, api_token=PUSHOVER_API)

bot = telepot.Bot(TELEGRAM_TOKEN)

bot.message_loop(handle)
print('Listening ...')
logging.info('Arranco el bot')


#client.send_message("Bot de teoría de redes arrancado", title="Telegram bot")

while 1: 
	time.sleep(10)
	for x in news_update:
		if news_update[x] == 1: 
			bot.sendMessage(x, 'Noticias de las')
			bot.sendMessage(x, str(datetime.datetime.now()))




