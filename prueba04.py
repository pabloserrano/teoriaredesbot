#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import random
import telepot 
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardHide, ForceReply
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.namedtuple import InlineQueryResultArticle, InlineQueryResultPhoto, InputTextMessageContent
import logging
import ConfigParser
from pushover import Client


message_with_inline_keyboard = None
start_done = {}
news_update = {}
poll_answer = {}
poll_trigger = 0
poll_ongoing = 0
poll_init_time = time.time()
unique_users = set()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='activity.log',
                    filemode='a')


def on_chat_message(msg):
	global news_update
	global poll_trigger

	content_type, chat_type, chat_id = telepot.glance(msg)
	print('Chat:', content_type, chat_type, chat_id)

	if content_type != 'text':
		return

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
		f = open('commands.txt')
		for line in f:
			bot.sendMessage(chat_id, '%s' %line)
		f.close()

	elif command == '/settings':
		logging.info('Comando /settings de %s', chat_id)
		bot.sendMessage(chat_id, 'Configuracion actual: News %i' % news_update[key])

	elif command == '/newson':
		logging.info('Comando /newson de %s', chat_id)
		bot.sendMessage(chat_id, 'Noticias activadas')
		news_update[key] = 1

	elif command == '/newsoff':
		logging.info('Comando /newsoff de %s', chat_id)
		bot.sendMessage(chat_id, 'Noticias desactivadas')
		news_update[key] = 0

	elif command == '/stats':
		logging.info('Comando /stats de %s', chat_id)
		bot.sendMessage(chat_id, 'Desde que arranqué he visto %i IDs' % len(unique_users))

	elif command == '/survey':
		logging.info('Comando /survey de %s', chat_id)
		if chat_id != ADMIN_ID:
			bot.sendMessage(chat_id, 'No puedes hacer eso')
		else:
			if poll_ongoing == 1:
				bot.sendMessage(chat_id, 'Ya hay una encuesta corriendo')
			elif len(unique_users) < 2:
				logging.info('Admin pide encuesta pero no hay usuarios')
				bot.sendMessage(chat_id, 'No hay usuarios o sólo está el ADMIN')
			else:
				bot.sendMessage(chat_id, 'Lanzando una encuesta')
				poll_trigger = 1

	else: 
		logging.info('Comando no reconocido de %i', chat_id)
		bot.sendMessage(chat_id, 'Comando no reconocido, usuario %i' % chat_id)
		


def on_callback_query(msg):
	global poll_answer
	query_id, from_id, data = telepot.glance(msg, flavor='callback_query')
	print('Callback query:', query_id, from_id, data)

	key = str(from_id)
	if poll_ongoing == 0:
		bot.answerCallbackQuery(query_id, text='Ya no se puede votar en esta encuesta')
	elif key in poll_answer:
		bot.answerCallbackQuery(query_id, text='Ya has votado en esta encuesta')
	else:
		if data == 'voto_si':
			bot.answerCallbackQuery(query_id, text='Has votado SÍ')
			poll_answer[key] = 1
		elif data == 'voto_no':
			bot.answerCallbackQuery(query_id, text='Has votado NO')
			poll_answer[key] = 0
		else:
			bot.answerCallbackQuery(query_id, text='Algo ha ido mal')



config = ConfigParser.ConfigParser()
config.readfp(open(r'config.txt'))

TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
PUSHOVER_API = config.get('Tokens', 'pushover_api')
PUSHOVER_CLIENT = config.get('Tokens', 'pushover_client')
ADMIN_ID = int(config.get('Admin', 'admin_id'))

client = Client(PUSHOVER_CLIENT, api_token=PUSHOVER_API)

bot = telepot.Bot(TELEGRAM_TOKEN)
bot.message_loop({'chat': on_chat_message,
                  'callback_query': on_callback_query})

print('Listening ...')
logging.info('Arranco el bot')

#client.send_message("Bot de teoría de redes arrancado", title="Telegram bot")

while 1:
	if poll_trigger == 1:
		poll_trigger = 0
		poll_ongoing = 1
		poll_init_time = time.time()

		logging.info('Lanzando encuesta a %d usuarios', len(unique_users))
		markup = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text='Sí', callback_data='voto_si')],
			[InlineKeyboardButton(text='No', callback_data='voto_no')],
			])
		for x in unique_users:
			time.sleep(1)
			if int(x) != ADMIN_ID:
				message_with_inline_keyboard = bot.sendMessage(x, 'Responde', reply_markup=markup)

	time.sleep(5)

	for x in news_update:
		if news_update[x] == 1: 
			bot.sendMessage(x, 'Aquí vendrían las noticias')

	if poll_ongoing == 1:
		if time.time() - poll_init_time > 20:
			logging.info('Fin de la encuesta, hay %d respuestas', len(poll_answer))
			bot.sendMessage(ADMIN_ID, 'Encuesta terminada')
			poll_ongoing = 0
			poll_answer = {}

