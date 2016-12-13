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
import pandas as pd
from subprocess import call



TIPO_FEEDBACK, CLASE_VALORADA, PEDIR_PROBLEMA, PROBLEMA_PEDIDO, SOLUCION_A_ENVIAR, SOLUCION_ENVIADA = range(6)

TIPO_SETTINGS = range(1)

TIPO_STATS = range(1)




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
		update.message.reply_text('Hola! Por defecto, noticias y encuestas activadas (comando /help para ayuda)')
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
		update.message.reply_text('/alert Manda una alerta a todos\n/help Muestra este mensaje\n/feedback Para votar problemas para clase, valorar la última clase o enviar la solución al examen\n/freetext Para enviar texto libre\n/randomfact Para una curiosidad al azar\n/settings Configuración\n/stats Estadísticas')
	else:
		update.message.reply_text('/help Muestra este mensaje\n/feedback Para solicitar problemas en clase, valorar la última clase o enviar la solución al examen\n/freetext Para enviar texto libre\n/randomfact Para una curiosidad al azar\n/settings Configuración\n/stats Estadísitcas')


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



def freetext(bot, update, args):
	#TODO HAY QUE FORMATEAR LA ENTRADA QUE NO SEAN TILDES O COSAS RARAS
    global FILE_TEXT
    logging.info('Usuario %i comando /freetext ' % update.message.chat_id)
    chat_id = update.message.chat_id
    if len(args) == 0:
    	update.message.reply_text('Uso: /freetext <texto>')
    else:
    	with codecs.open(FILE_TEXT, "a", "utf-8") as myfile:
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
    			text="Notificaciones activadas"
    			users[str(chat_id)][2] = '1'
    		else:
    			text="Notificaciones desactivadas"
    			users[str(chat_id)][2] = '0'
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
    	with codecs.open(FILE_RANDOM_RESULTS, "a", "utf-8") as myfile:
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
    	with codecs.open(FILE_NEWS_RESULTS, "a", "utf-8") as myfile:
    		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	
    	bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id)
    	logging.info('Usuario %i responde news %s con %s' % (chat_id, identifier, reply))

    else:
    	print ('No entiendo')


def echo(bot, update):
    update.message.reply_text('No entiendo. Escriba /help para ayuda')

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





def feedback(bot, update, user_data):
	user_data['capitulo'] = -1
	logging.info('Usuario %i comando /feedback ' % update.message.chat_id)

	reply_keyboard = [['Valorar clase','Votar problema'],['Enviar solución','Nada']]
	#update.message.reply_text('Elige opción:', reply_markup=reply_markup)
	update.message.reply_text('Qué tipo de feedback quieres dar:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

	return TIPO_FEEDBACK


def feedback_clase(bot, update):
	#keyboard = [[InlineKeyboardButton("Más teoría", callback_data='c.teoria'),InlineKeyboardButton("Más problemas", callback_data='c.problemas')],
	#[InlineKeyboardButton("Estuvo bien", callback_data='c.bien'),InlineKeyboardButton("NS/NC", callback_data='c.nsnc')]]
	#reply_markup = InlineKeyboardMarkup(keyboard)
	#bot.sendMessage(chat_id=update.message.chat_id, text="Valora la última clase", reply_markup=reply_markup)
	reply_keyboard = [['Más teoría', 'Más problemas'], ['Está bien así', 'Ns/Nc']]
	update.message.reply_text('Feedback sobre la última clase:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return CLASE_VALORADA

def feedback_clase_valorada(bot, update):
	global FILE_CLASES
	chat_id = str(update.message.chat_id)
	text = update.message.text


	#Esto da fallo con el UTF-8
	logging.info('Usuario %s responde ultclase con %s' % (chat_id, text))
	with codecs.open(FILE_CLASES, "a", "utf-8") as myfile:
		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), "ultclase", chat_id, text))

	reply_keyboard = [['Valorar clase','Votar problema'],['Enviar solución','No']]
	update.message.reply_text('Gracias por la valoración, ¿alguna cosa más?',  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_FEEDBACK


def feedback_votar(bot, update, user_data):
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


def feedback_problema_votado(bot, update, user_data):
	global FILE_PROBLEMAS
	chat_id = str(update.message.chat_id)
	numero = update.message.text
	user_data['problema']=numero
	
	logging.info('Usuario %s solicita problema %s.%s' % (chat_id, user_data['capitulo'], user_data['problema']))
	with codecs.open(FILE_PROBLEMAS, "a", "utf-8") as myfile:
		myfile.write("%s\t%s\t%s-%s\n" % (str(datetime.datetime.now()), chat_id, user_data['capitulo'], user_data['problema']))	
	
	reply_keyboard = [['Valorar clase','Votar otro problema'],['Enviar solución','No']]
	update.message.reply_text('Problema %s.%s solicitado, ¿algo más?' %(user_data['capitulo'], user_data['problema']),
	  reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	
	user_data['capitulo']=-1	
	return TIPO_FEEDBACK	


def feedback_solucion(bot, update, user_data):
	user_data['solucion']=0
	update.message.reply_text('Escribe la solución del problema propuesto (xxx para cancelar):')
	return SOLUCION_A_ENVIAR


def feedback_solucion_recibida(bot, update, user_data):
	user_data['solucion'] = update.message.text
	if user_data['solucion'] == 'xxx':
		reply_keyboard = [['Valorar clase','Votar problema'],['Enviar solución','Nada']]
		update.message.reply_text('Cancelado. Elija opción:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		reply_keyboard = [["Sí","No"]]
		update.message.reply_text('Solución a enviar: %s \n ¿Confirmar?' % user_data['solucion'], 
			reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return SOLUCION_ENVIADA


def feedback_solucion_enviada(bot, update, user_data):
	if update.message.text=='Sí':
		reply_keyboard = [['Valorar clase','Votar problema'],['Enviar solución','No']]
		update.message.reply_text('Solución guardada, ¿alguna cosa más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		update.message.reply_text('No se ha guardado la solución. Escribe la solución del problema propuesto (xxx para cancelar):')
		return SOLUCION_A_ENVIAR


def feedback_done(bot, update, user_data):
	update.message.reply_text('Ok!')
	user_data.clear()
	return ConversationHandler.END




def settings(bot, update):
	global users
	logging.info('Usuario %i comando /settings ' % update.message.chat_id)

	reply_keyboard = ['Resetear contador'],['Cambiar configuración','Nada']
	update.message.reply_text('Has visto X de Y randomfacts y tienes los avisos (des)activados. Elige opción', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_SETTINGS


def settings_reset(bot, update):
	logging.info('Usuario %i comando /settings-reset ' % update.message.chat_id)

	reply_keyboard = ['Resetear contador'],['Cambiar configuración','No']
	update.message.reply_text('Registro de randomfacts vistos a 0. ¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_SETTINGS


def settings_config(bot, update):
	global users
	logging.info('Usuario %i comando /settings-config ' % update.message.chat_id)

	keyboard = [[InlineKeyboardButton("Sí", callback_data='s.news.si'),
		InlineKeyboardButton("No", callback_data='s.news.no')]]
	reply_markup = InlineKeyboardMarkup(keyboard)
	update.message.reply_text('Recibir notificaciones sobre efemérides y anécdotas relacionada con la asignatura:', reply_markup=reply_markup)

	reply_keyboard = ['Resetear contador'],['Cambiar configuración','No']
	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_SETTINGS



def settings_done(bot, update):
	update.message.reply_text('Vale!')
	return ConversationHandler.END






def stats(bot, update):
	global users
	global FILE_USERS
	global FILE_LOG

	logging.info('Usuario %i comando /stats ' % update.message.chat_id)
	

	if int(users[str(update.message.chat_id)][0]):
		FILE_INFO = 'files/activity_info.log'
		cmd = "cat " + FILE_LOG + " | grep INFO | grep comando > " + FILE_INFO
		call(cmd, shell=True)

		df = pd.read_csv(FILE_INFO,sep=' ',header=0,usecols=(0,4,6), names=['date', 'uid', 'command'], parse_dates=['date'])
		end_date = datetime.date.today()
		start_date = end_date - datetime.timedelta(days=7)
		mask = (df['date'] >= start_date ) & (df['date'] <= end_date )
		df = df.loc[mask]

		update.message.reply_text('Usuarios únicos por día')
		uni_users=df.groupby('date').uid.nunique()
		update.message.reply_text('%s' % uni_users.to_string() )

		update.message.reply_text('Actividad por día')
		activity=df.groupby('date').count()
		update.message.reply_text('%s' % activity.command.to_string() )

		update.message.reply_text('Usuarios más activos')
		users_active=df.groupby('uid').count()
		users_active.sort_values(by='command',ascending=False,inplace=True)
		update.message.reply_text('%s' % users_active.command.to_string() )

	reply_keyboard = [['Problemas más votados'],['Soluciones correctas'],['Tabla de clasificación'],['Nada']]
	update.message.reply_text('Qué quieres saber', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_STATS


def stats_problems(bot, update):
	global FILE_PROBLEMAS

	update.message.reply_text('Problemas más votados:')
	df = pd.read_csv(FILE_PROBLEMAS,sep='\t',header=0,names=['date','uid','prob'])
	psol = df.groupby('prob').uid.nunique()
	psol.sort_values(ascending=False,inplace=True)
	update.message.reply_text('%s' % psol.to_string() )

	reply_keyboard = [['Problemas más votados'],['Soluciones correctas'],['Tabla de clasificación'],['Nada']]
	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_STATS

def stats_solutions(bot, update):
	reply_keyboard = [['Problemas más votados'],['Soluciones correctas'],['Tabla de clasificación'],['Nada']]
	update.message.reply_text('Aquí las estadísticas sobre las soluciones hasta ahora. ¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_STATS

def stats_ranking(bot, update):
	reply_keyboard = [['Problemas más votados'],['Soluciones correctas'],['Tabla de clasificación'],['Nada']]
	update.message.reply_text('Aquí viene el ranking de usuarios. ¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
	return TIPO_STATS


def stats_done(bot, update):
	update.message.reply_text('Ok')
	return ConversationHandler.END




def feedback(bot, update, user_data):
	user_data['capitulo'] = -1
	logging.info('Usuario %i comando /feedback ' % update.message.chat_id)

	reply_keyboard = [['Valorar clase','Votar problema'],['Enviar solución','Nada']]
	#update.message.reply_text('Elige opción:', reply_markup=reply_markup)
	update.message.reply_text('Qué tipo de feedback quieres:', reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

	return TIPO_FEEDBACK



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
	global FILE_PROBLEMAS

	
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
	FILE_PROBLEMAS = config.get('Files', 'problemas')

	#logging.basicConfig(level=logging.INFO,
    #                format='%(asctime)s %(levelname)s %(message)s',
    #                filename=FILE_LOG,
    #                filemode='a', encoding='utf-8')
	
	logging.basicConfig(handlers=[logging.FileHandler(FILE_LOG, 'a', 'utf-8')],
		level=logging.INFO,
		format='%(asctime)s %(levelname)s %(message)s')
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



	conv_handler_feedback = ConversationHandler(
		entry_points=[CommandHandler('feedback', feedback, pass_user_data=True)],

		states={
			TIPO_FEEDBACK: [RegexHandler('^Valorar clase$', feedback_clase),
			RegexHandler('^(Votar problema|Votar otro problema)$', feedback_votar, pass_user_data=True),
			RegexHandler('^Enviar solución$', feedback_solucion, pass_user_data=True),
			RegexHandler('^(Nada|No)$', feedback_done,pass_user_data=True) 
			],

			CLASE_VALORADA: [MessageHandler(Filters.text, feedback_clase_valorada),
			],

			PEDIR_PROBLEMA: [MessageHandler(Filters.text, feedback_votar, pass_user_data=True),
			],

			PROBLEMA_PEDIDO: [MessageHandler(Filters.text, feedback_problema_votado, pass_user_data=True),
			],

			SOLUCION_A_ENVIAR: [MessageHandler(Filters.text, feedback_solucion_recibida, pass_user_data=True),
			],

			SOLUCION_ENVIADA:[MessageHandler(Filters.text, feedback_solucion_enviada, pass_user_data=True),
			],
		},

		fallbacks=[RegexHandler('^(Nada|No)$', feedback_done, pass_user_data=True)]
	)
	dp.add_handler(conv_handler_feedback)


	conv_handler_settings = ConversationHandler(
		entry_points=[CommandHandler('settings', settings)],

		states={
			TIPO_SETTINGS: [RegexHandler('^Resetear contador$', settings_reset),
			RegexHandler('^Cambiar configuración$', settings_config),
			RegexHandler('^Nada$', settings_done) 
			],
		},

		fallbacks=[RegexHandler('^(Nada|No)$', settings_done)]
	)
	dp.add_handler(conv_handler_settings)


	conv_handler_stats = ConversationHandler(
		entry_points=[CommandHandler('stats', stats)],

		states={
			TIPO_STATS: [RegexHandler('^Problemas más votados$', stats_problems),
			RegexHandler('^Soluciones correctas$', stats_solutions),
			RegexHandler('^Tabla de clasificación$', stats_ranking),
			RegexHandler('^Nada$', stats_done) 
			],
		},

		fallbacks=[RegexHandler('^(Nada|No)$', stats_done)]
	)
	dp.add_handler(conv_handler_stats)




	# on different commands - answer in Telegram
	dp.add_handler(CommandHandler("admin", admin))
	dp.add_handler(CommandHandler("alert", alert, pass_args=True))
	dp.add_handler(CommandHandler("freetext", freetext, pass_args=True))
	dp.add_handler(CommandHandler("start", start))
	#dp.add_handler(CommandHandler("stats", stats))
	dp.add_handler(CommandHandler("help", help))
	dp.add_handler(CommandHandler("randomfact", randomfact))
	#dp.add_handler(CommandHandler("settings", settings))
	

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



