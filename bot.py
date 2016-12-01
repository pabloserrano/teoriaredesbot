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
import configparser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardHide
from telegram.ext import (Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackQueryHandler, RegexHandler, Job)
import codecs

TIPO_FEEDBACK, CLASE_VALORADA, PEDIR_PROBLEMA, PROBLEMA_PEDIDO, SOLUCION_A_ENVIAR, SOLUCION_ENVIADA = range(6)


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
	with codecs.open(file, 'r') as myfile:
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
	global FILE_RANDOM_RESULTS

	logging.info('Usuario %i comando /randomfact ' % update.message.chat_id)

	# Cargo los random facts que existen
	randomfact_ids = set()
	randomfact_txts = defaultdict(list)
	with codecs.open(FILE_RANDOM, "r", "utf-8") as myfile:
	    for myline in myfile:
	            identifier, text = myline.split("\t")
	            randomfact_ids.add(identifier)
	            randomfact_txts[identifier] = text

	# Saco los que ya ha leido / votado
	if os.path.exists(FILE_RANDOM_RESULTS) and os.stat(FILE_RANDOM_RESULTS).st_size > 0:
		randomfactsseen = defaultdict(set)
		with codecs.open(FILE_RANDOM_RESULTS, "r", "utf-8") as myfile:
			for myline in myfile:
				timestamp, random_id, chat_id, reply = myline.split("\t")
				randomfactsseen[str(chat_id)].add(random_id)

		randomnotseen = randomfact_ids - randomfactsseen[str(update.message.chat_id)]
	else:
		randomnotseen = randomfact_ids

	if randomnotseen == set():
		update.message.reply_text('Ya has visto todas las curiosidades disponibles de momento :(')
		logging.info('Usuario %i ya ha visto todos randoms ' % update.message.chat_id)
	else:
		identifier = random.sample(randomnotseen,1)[0]
		text = randomfact_txts[identifier]
		logging.info('Usuario %i se le manda random %s ' % (update.message.chat_id, identifier))

		#update.message.reply_text(text)
		bot.sendMessage(update.message.chat_id, text=text, parse_mode='HTML')

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
		num_users = sum(1 for line in open(FILE_USERS)) 
		update.message.reply_text('Hay %i usuarios' % num_users)
		today = datetime.date.today()
		update.message.reply_text('Dia: %s actividad: %i' % (today.strftime("%Y-%m-%d"), activity_count(today,FILE_LOG)))
		for d in range(1,3):
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
    		myfile.write("%s\t%s\t%s\n" % (str(datetime.datetime.now()), str(chat_id), str(update.message.text)))
    	update.message.reply_text('Texto guardado')



def button(bot, update):
    global users
    global FILE_USERS
    global FILE_RANDOM_RESULTS
    global FILE_NEWS_RESULTS
    global FILE_CLASES
	
    query = update.callback_query
    chat_id=query.message.chat_id
    message_id=query.message.message_id

    logging.info('Usuario %i button %s ' % (chat_id, query.data) )

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
    		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	

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
    		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	logging.info('Usuario %i responde news %s con %s' % (chat_id, identifier, reply))

    #p para los polls
    elif query.data[0] == 'p':
    	dummy, identifier = query.data.split(".")
    	if identifier == 'clase':
    		bot.editMessageText(text="Lanzando encuesta sobre la última clase", chat_id=chat_id, message_id=message_id)
    		poll_clase(bot, chat_id)
    	elif identifier == 'pedir':
    		bot.editMessageText(text="Ante el vicio de pedir", chat_id=chat_id, message_id=message_id)#
    	elif identifier == 'solucion':
    		bot.editMessageText(text="La solución sería", chat_id=chat_id, message_id=message_id)

    #c Para las clases
    elif query.data[0] == 'c':
    	dummy, reply = query.data.split(".")
    	if reply == 'teoria':
    		text="Más teoría, entendido"
    	elif reply == 'problemas':
    		text="Más problemas habrá"
    	elif reply == 'bien':
    		text="¡Gracias!"
    	else:
    		text="Vaya..."
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	logging.info('Usuario %i responde clase con %s' % (chat_id, reply))

    	with open(FILE_CLASES, "a") as myfile:
    		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), "Ultclase", str(chat_id), reply))

    else:
    	print ('No entiendo')


def echo(bot, update):
    update.message.reply_text('No entiendo. Escriba /help para ayuda' %update.message.text)

def error(bot, update, error):
    logging.warn('Update "%s" caused error "%s"' % (update, error))

def todays_news(bot,job):
	global calendar
	global users
	global FILE_NEWS
	logging.info('Se lanza todays_news')
	if os.path.exists(FILE_NEWS) and os.stat(FILE_NEWS).st_size > 0:
		num_news = load_calendar(FILE_NEWS, calendar)
		todays_key = datetime.date.today().strftime("%Y-%m-%d")
		if todays_key in calendar:
			for key in users:
				if users[key][2] == '1':
					bot.sendMessage(chat_id=int(key), text=calendar[todays_key], parse_mode='HTML')

					keyboard = [[InlineKeyboardButton("Si", callback_data='n.'+todays_key+'.si'),
					InlineKeyboardButton("No", callback_data='n.'+todays_key+'.no')]]
					reply_markup = InlineKeyboardMarkup(keyboard)

					if int(users[str(key)][1]):
						bot.sendMessage(chat_id=int(key), text='¿Te ha parecido interesante?', reply_markup=reply_markup)

	else:
		logging.warn('todays_news: no hay fichero de noticias')



def polls(bot, update, user_data):
	user_data['capitulo'] = -1
	logging.info('Usuario %i comando /polls ' % update.message.chat_id)

	reply_keyboard = [['Valorar última clase'], ["Pedir problema"], ["Solución problema propuesto"], ["Nada"]]
	#update.message.reply_text('Elige opción:', reply_markup=reply_markup)
	update.message.reply_text('Elige opción:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

	return TIPO_FEEDBACK


def poll_clase(bot, update):
	#keyboard = [[InlineKeyboardButton("Más teoría", callback_data='c.teoria'),InlineKeyboardButton("Más problemas", callback_data='c.problemas')],
	#[InlineKeyboardButton("Estuvo bien", callback_data='c.bien'),InlineKeyboardButton("NS/NC", callback_data='c.nsnc')]]
	#reply_markup = InlineKeyboardMarkup(keyboard)
	#bot.sendMessage(chat_id=update.message.chat_id, text="Valora la última clase", reply_markup=reply_markup)
	reply_keyboard = [['Más teoría'], ['Más problemas'], ['Está bien así'], ['Ns/Nc']]
	update.message.reply_text('Valora la última clase:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return CLASE_VALORADA

def poll_clase_valorada(bot, update):
	text = update.message.text
	reply_keyboard = [["Pedir problema"], ["Solución problema propuesto"], ["Nada"]]
	update.message.reply_text('Gracias por la valoración, ¿alguna cosa más?',  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_FEEDBACK


def poll_pedir(bot, update, user_data):
	numero = update.message.text
	if (int(user_data['capitulo'])<0):
		user_data['capitulo']=0
		reply_keyboard = [['1','2','3'],['4','5','6'],['7','8','9']]
		update.message.reply_text('De qué capítulo', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return PEDIR_PROBLEMA
	else:
		user_data['capitulo']=numero
		reply_keyboard = [['1','2','3','4','5','6'],['7','8','9','10','11','12'],['13','14','15','16','17','18'],['19','20','21','22','23','24']]
		update.message.reply_text('Qué problema', reply_markup=ReplyKeyboardMarkup(reply_keyboard))
		return PROBLEMA_PEDIDO

def poll_problema_pedido(bot, update, user_data):
	numero = update.message.text
	user_data['problema']=numero
	reply_keyboard = [["Pedir otro problema"], ["No"]]
	update.message.reply_text('Problema %s.%s solicitado, ¿algo más?' %(user_data['capitulo'],user_data['problema']),
	  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	user_data['capitulo']=-1	
	return TIPO_FEEDBACK	


def poll_solucion(bot, update, user_data):
	user_data['solucion']=0
	update.message.reply_text('Escribe la solución del problema propuesto (-1 para cancelar):')
	return SOLUCION_A_ENVIAR


def poll_solucion_recibida(bot, update, user_data):
	user_data['solucion'] = update.message.text
	if user_data['solucion'] == '-1':
		reply_keyboard = [['Valorar última clase'], ["Pedir problema"], ["Solución problema propuesto"], ["Nada"]]
		update.message.reply_text('Cancelado. Elija opción:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		reply_keyboard = [["Sí"], ["No"]]
		update.message.reply_text('Solución a enviar: %s \n ¿Confirmar?' % user_data['solucion'], 
			reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return SOLUCION_ENVIADA


def poll_solucion_enviada(bot, update, user_data):
	if update.message.text=='Sí':
		reply_keyboard = [['Valorar última clase'], ["Pedir problema"], ["Nada"]]
		update.message.reply_text('Solución guardada, ¿alguna cosa más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		update.message.reply_text('No se ha guardado la solución. Escribe la solución del problema propuesto (-1 para cancelar):')
		return SOLUCION_A_ENVIAR


def poll_done(bot, update, user_data):
	update.message.reply_text('Ok!')
	user_data.clear()
	return ConversationHandler.END



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
	global FILE_CLASES

	
	# Load configuration parameters
	config = configparser.ConfigParser()
	config.readfp(open(r'config.txt'))
	TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
	FILE_USERS = config.get('Files', 'users')
	FILE_NEWS = config.get('Files', 'news')
	FILE_NEWS_RESULTS = config.get('Files', 'news_results')
	FILE_TEXT = config.get('Files', 'freetext')
	FILE_RANDOM = config.get('Files', 'randomfacts')
	FILE_RANDOM_RESULTS = config.get('Files', 'randomfacts_results')
	FILE_LOG = config.get('Files', 'log')
	FILE_CLASES = config.get('Files', 'clases')

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


	conv_handler = ConversationHandler(
		entry_points=[CommandHandler('polls', polls, pass_user_data=True)],

		states={
			TIPO_FEEDBACK: [RegexHandler('^Valorar última clase$',poll_clase),
			RegexHandler('^(Pedir problema|Pedir otro problema)$', poll_pedir, pass_user_data=True),
			RegexHandler('^Solución problema propuesto$',poll_solucion, pass_user_data=True),
			RegexHandler('^(Nada|No)$',poll_done,pass_user_data=True) 
			],

			CLASE_VALORADA: [MessageHandler(Filters.text, poll_clase_valorada),
			],

			PEDIR_PROBLEMA: [MessageHandler(Filters.text, poll_pedir, pass_user_data=True),
			],

			PROBLEMA_PEDIDO: [MessageHandler(Filters.text, poll_problema_pedido, pass_user_data=True),
			],

			SOLUCION_A_ENVIAR: [MessageHandler(Filters.text, poll_solucion_recibida, pass_user_data=True),
			],

			SOLUCION_ENVIADA:[MessageHandler(Filters.text, poll_solucion_enviada, pass_user_data=True),
			],
		},

		fallbacks=[RegexHandler('^Done$', poll_done, pass_user_data=True)]
	)

	dp.add_handler(conv_handler)

	# on different commands - answer in Telegram
	dp.add_handler(CommandHandler("admin", admin))
	dp.add_handler(CommandHandler("alert", alert, pass_args=True))
	dp.add_handler(CommandHandler("freetext", freetext, pass_args=True))
	dp.add_handler(CommandHandler("start", start))
	dp.add_handler(CommandHandler("stats", stats))
	dp.add_handler(CommandHandler("help", help))
	#dp.add_handler(CommandHandler("polls", polls))
	dp.add_handler(CommandHandler("randomfact", randomfact))
	dp.add_handler(CommandHandler("settings", settings))
	

	dp.add_handler(CallbackQueryHandler(button))

	# on noncommand i.e message - echo the message on Telegram
	dp.add_handler(MessageHandler(Filters.text, echo))

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



