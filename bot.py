#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time
import os
import csv
import sys
import time
import datetime 
import random
from collections import defaultdict
import logging
import ConfigParser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, Job



def load_config_users( file, users ):
	with open(file, 'r') as csv_file:
		csv_reader = csv.DictReader(csv_file)
		for row in csv_reader:
			users[str(row['chatid'])].append(row['admin'])
			users[str(row['chatid'])].append(row['polls'])
			users[str(row['chatid'])].append(row['news'])
		return len(users)

def save_config_users( file, users ):
	with open(file, 'w') as csv_file:
		writer = csv.writer(csv_file)
		writer.writerow(['chatid','admin','polls','news'])
		for key, value in users.items():
			writer.writerow([key, value[0], value[1], value[2] ])


def load_calendar( file, calendar ):
	with open(file, 'r') as myfile:
		for myline in myfile:
			(date, text) = myline.split("\t")
			calendar[date] = text
		return len(calendar)


def admin(bot, update):
	if int(users[str(update.message.chat_id)][0]):
		update.message.reply_text('Parte de admin del bot')
	else:
		update.message.reply_text('Comando no reconocido')

def alert(bot, update, args):
	global users
	logging.info('Usuario %i comando /alert ' % update.message.chat_id)
	if int(users[str(update.message.chat_id)][0]):
		chat_id = update.message.chat_id
		if len(args) == 0:
			update.message.reply_text('Uso: /alert <texto de aviso>')
		else:
			for key in users:
				if int(key) != chat_id:
					bot.sendMessage(chat_id=int(key), text=str(update.message.text))
			update.message.reply_text('Alerta enviada')
			logging.info('Alerta enviada: %s' % str(update.message.text))
	else:
		update.message.reply_text('Comando no reconocido')


def start(bot, update):
	global users
	global FILE_USERS
	if str(update.message.chat_id) not in users:
		update.message.reply_text('Hola! Por defecto, noticias y encuestas activadas (comando /settings para cambiar configuracion)')
		users[str(update.message.chat_id)].append(0)
		users[str(update.message.chat_id)].append(1)
		users[str(update.message.chat_id)].append(1)
		logging.info('/start nuevo usuario: %i ' % update.message.chat_id)
		save_config_users(FILE_USERS, users)
	else:
		update.message.reply_text('Hola de nuevo')
		logging.info('/start vuelve usuario %i ' % update.message.chat_id)
	


def help(bot, update):
	logging.info('Usuario %i comando /help ' % update.message.chat_id)
	if int(users[str(update.message.chat_id)][0]):
		update.message.reply_text('/alert para enviar una alerta, /settings para configurar los parámetros, /freetext para enviar texto libre, /randomfact para una curiosidad al azar, /stats para estadisticas')
	else:
		update.message.reply_text('/settings para configurar los parámetros, /freetext para enviar texto libre, /randomfact para una curiosidad al azar')


def randomfact(bot, update):
	global users
	global FILE_RANDOM
	logging.info('Usuario %i comando /randomfact ' % update.message.chat_id)

	lines = open(FILE_RANDOM).read().splitlines()
	myline = random.choice(lines)
	identifier, text = myline.split("\t")
	update.message.reply_text(text)
	
	keyboard = [[InlineKeyboardButton("Si", callback_data='r.'+identifier+'.si'),
		InlineKeyboardButton("No", callback_data='r.'+identifier+'.no')]]
	reply_markup = InlineKeyboardMarkup(keyboard)
	if int(users[str(update.message.chat_id)][1]):
		update.message.reply_text('Te ha parecido interesante?', reply_markup=reply_markup)


def settings(bot, update):
	global users
	global FILE_USERS
	logging.info('Usuario %i comando /settings ' % update.message.chat_id)

	keyboard = [[InlineKeyboardButton("Activar", callback_data='s.news.si'),
		InlineKeyboardButton("Desactivar", callback_data='s.news.no')]]
	reply_markup = InlineKeyboardMarkup(keyboard)
	update.message.reply_text('Recibir noticias', reply_markup=reply_markup)

	keyboard = [[InlineKeyboardButton("Activar", callback_data='s.polls.si'),
		InlineKeyboardButton("Desactivar", callback_data='s.polls.no')]]
	reply_markup = InlineKeyboardMarkup(keyboard)
	update.message.reply_text('Participar en encuestas', reply_markup=reply_markup)

def activity_count(datestamp, fname):
	keyword = datestamp.strftime("%Y-%m-%d")
	with open(fname, 'r') as fin:
		return sum([1 for line in fin if keyword in line])

def stats(bot, update):
	global users
	global FILE_USERS
	global FILE_LOG
	logging.info('Usuario %i comando /stats ' % update.message.chat_id)
	if int(users[str(update.message.chat_id)][0]):
		num_users = sum(1 for line in open(FILE_USERS)) - 1
		update.message.reply_text('Hay %i usuarios' % num_users)
		today = datetime.date.today()
		update.message.reply_text('Dia: %s actividad: %i' % (today.strftime("%Y-%m-%d"), activity_count(today,FILE_LOG)))
		for d in xrange(1,3):
			today = today - datetime.timedelta(days=1)
			update.message.reply_text('Dia: %s actividad: %i' % (today.strftime("%Y-%m-%d"), activity_count(today,FILE_LOG)))
	else:
		update.message.reply_text('Comando no reconocido')


def freetext(bot, update, args):
	#TODO HAY QUE FORMATEAR LA ENTRADA QUE NO SEAN TILDES O COSAS RARAS
    global FILE_TEXT
    logging.info('Usuario %i comando /freetext ' % update.message.chat_id)
    chat_id = update.message.chat_id
    if len(args) == 0:
    	update.message.reply_text('Uso: /freetext <texto>')
    else:
    	with open(FILE_TEXT, "a") as myfile:
    		myfile.write("%s \t %s \t %s\n" % (str(datetime.datetime.now()), str(chat_id), str(update.message.text)))
    	update.message.reply_text('Texto guardado')



def button(bot, update):
    global users
    global FILE_USERS
    global FILE_RANDOM_RESULTS
    global FILE_NEWS_RESULTS
	
    query = update.callback_query
    chat_id=query.message.chat_id
    message_id=query.message.message_id

    #s para los settings
    if query.data[0] == 's':
    	dummy, parameter, reply = query.data.split(".")
    	if parameter == 'news':
    		if reply == 'si':
    			text="Noticias activadas"
    			users[str(chat_id)][2] = '1'
    		else:
    			text="Noticias desactivadas"
    			users[str(chat_id)][2] = '0'
    	elif parameter == 'polls':
    		if reply == 'si':
    			text="Encuestas activadas"
    			users[str(chat_id)][1] = '1'
    		else:
    			text="Encuestas desactivadas"
    			users[str(chat_id)][1] = '0'
    	else:
    		text="Parametro de settings no reconocido"
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	save_config_users( FILE_USERS, users )
    	logging.info('Usuario %i pone configuracion polls: %s news: %s' % (chat_id, users[str(chat_id)][1], users[str(chat_id)][2]))

    #r para los random facts
    elif query.data[0] == 'r':
    	dummy, identifier, reply = query.data.split(".")
    	if reply == 'si':
    		text="Vale!"
    	else:
    		text="Vaya..."
    	with open(FILE_RANDOM_RESULTS, "a") as myfile:
    		myfile.write("%s \t %s \t %s \t %s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	logging.info('Usuario %i responde random %s con %s' % (chat_id, identifier, reply))
    
    #n para las noticias
    elif query.data[0] == 'n':
    	dummy, identifier, reply = query.data.split(".")
    	if reply == 'si':
    		text="Vale!"
    	else:
    		text="Vaya..."
    	with open(FILE_NEWS_RESULTS, "a") as myfile:
    		myfile.write("%s \t %s \t %s \t %s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	logging.info('Usuario %i responde news %s con %s' % (chat_id, identifier, reply))
    else:
    	print ('No entiendo')


def echo(bot, update):
    update.message.reply_text(update.message.text)

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))

def todays_news(bot,job):
	global calendar
	global users
	global FILE_NEWS
	logging.info('Se lanza todays_news')
	if os.path.exists(FILE_NEWS) and os.stat(FILE_NEWS).st_size > 0:
		num_news = load_calendar(FILE_NEWS, calendar)
		todays_key = datetime.date.today().strftime("%Y-%m-%d")
		if calendar.has_key(todays_key):
			for key in users:
				if users[key][2] == '1':
					bot.sendMessage(chat_id=int(key), text=calendar[todays_key])

					keyboard = [[InlineKeyboardButton("Si", callback_data='n.'+todays_key+'.si'),
					InlineKeyboardButton("No", callback_data='n.'+todays_key+'.no')]]
					reply_markup = InlineKeyboardMarkup(keyboard)

					if int(users[str(key)][1]):
						bot.sendMessage(chat_id=int(key), text='Te ha parecido interesante?', reply_markup=reply_markup)

	else:
		logging.warn('todays_news: no hay fichero de noticias')


def main():
	global users
	global calendar
	global FILE_USERS
	global FILE_TEXT
	global FILE_NEWS
	global FILE_NEWS_RESULTS
	global FILE_RANDOM
	global FILE_RANDOM_RESULTS
	global FILE_LOG


	# Load configuration parameters
	config = ConfigParser.ConfigParser()
	config.readfp(open(r'config.txt'))
	TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
	FILE_USERS = config.get('Files', 'users')
	FILE_NEWS = config.get('Files', 'news')
	FILE_NEWS_RESULTS = config.get('Files', 'news_results')
	FILE_TEXT = config.get('Files', 'freetext')
	FILE_RANDOM = config.get('Files', 'randomfacts')
	FILE_RANDOM_RESULTS = config.get('Files', 'randomfacts_results')
	FILE_LOG = config.get('Files', 'log')

	logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename=FILE_LOG,
                    filemode='a')
	logging.getLogger().addHandler(logging.StreamHandler())

	# Global variables
	users = defaultdict(list)
	calendar = defaultdict(list)

	# Load previous configuration 
	if os.path.exists(FILE_USERS) and os.stat(FILE_USERS).st_size > 0:
		num_users = load_config_users(FILE_USERS, users)
		logging.info('Arranco el bot con %s usuarios' % num_users)
	else:
		logging.info('Arranco el bot sin usuarios')


	# Create the EventHandler and pass it your bot's token.
	updater = Updater(TELEGRAM_TOKEN)
	

	#Job queue to schedule updates
	jq = updater.job_queue
	#Cada 24 horas
	job_news = Job(todays_news, 24*60*60)
	#Calculo segundos hasta Hora de las news
	now = datetime.datetime.now()
	time_news = now.replace(hour=9, minute=0, second=0, microsecond=0)
	seconds = (time_news - now).total_seconds()
	if seconds < 0:
		seconds = seconds + 24*60*60
	#para probar las noticias ya
	#seconds = 3
	jq.put(job_news, next_t=seconds)


	# Get the dispatcher to register handlers
	dp = updater.dispatcher

	# on different commands - answer in Telegram
	dp.add_handler(CommandHandler("alert", alert, pass_args=True))
	dp.add_handler(CommandHandler("admin", admin))
	dp.add_handler(CommandHandler("start", start))
	dp.add_handler(CommandHandler("stats", stats))
	dp.add_handler(CommandHandler("help", help))
	dp.add_handler(CommandHandler("randomfact", randomfact))
	dp.add_handler(CommandHandler("settings", settings))
	dp.add_handler(CommandHandler("freetext", freetext, pass_args=True))

	dp.add_handler(CallbackQueryHandler(button))

	# on noncommand i.e message - echo the message on Telegram
	#dp.add_handler(MessageHandler(Filters.text, echo))

	# log all errors
	dp.add_error_handler(error)

	# Start the Bot
	updater.start_polling()


	# Run the bot until the you presses Ctrl-C or the process receives SIGINT,
	# SIGTERM or SIGABRT. This should be used most of the time, since
	# start_polling() is non-blocking and will stop the bot gracefully.
	updater.idle()


if __name__ == '__main__':
	main()



