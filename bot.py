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
import math
from dateutil import parser


TIPO_FEEDBACK, CLASE_VALORADA, PEDIR_PROBLEMA, PROBLEMA_PEDIDO, SOLUCION_A_ENVIAR, SOLUCION_ENVIADA, TEXTO_ENVIADO = range(7)

TIPO_SETTINGS = range(1)

TIPO_STATS = range(1)

REL_TOL = 1e-4

reply_keyboard_feedback = [['Valorar clase','Votar problema'],['Enviar solución','Nada']]
reply_keyboard_clase = [['Más teoría', 'Más problemas'], ['Está bien así', 'Ns/Nc'], ['Enviar texto libre']]
reply_keyboard_settings = [['Cambiar configuración'],['Nada']]
reply_keyboard_stats = [['Problemas más votados'],['Soluciones correctas'],['Tabla de clasificación'],['Nada']]

def load_calendar( file, calendar ):
	with codecs.open(file, 'r', 'utf-8') as myfile:
		for myline in myfile:
			(date, text) = myline.split("\t")
			calendar[date] = text
		return len(calendar)

def start(bot, update):
	global config_users
	global FILE_USERS
	global FILE_NICKS

	chat_id = str(update.message.chat_id)

	if chat_id not in config_users.sections():
		logging.info('/start nuevo usuario: %s ' % chat_id)

		config_users.add_section(chat_id)
		config_users.set(chat_id, 'news', 'True')
		config_users.set(chat_id, 'admin', 'False')
		config_users.set(chat_id, 'firstseen', str(datetime.datetime.now()))
		
		nicks = codecs.open(FILE_NICKS, 'r', 'utf-8').read().splitlines()
		nick = random.choice(nicks)
		config_users.set(chat_id, 'nick', nick)
		update.message.reply_text('Hola! Por defecto, notificaciones activadas'
			'(usa el comando /help para ayuda). Te ha tocado el nick '
			'%s, puedes usar el comando /start para recordarlo'
			'y para reiniciar el bot si algo va mal' % nick)

		f = codecs.open(FILE_NICKS, 'w', 'utf-8')
		for line in nicks:
			if nick not in line:
				f.write(line+"\n")
		f.close()

		save_config_users(FILE_USERS)

	else:
		update.message.reply_text('Hola de nuevo, tu nick es %s' % config_users.get(chat_id, 'nick'), reply_markup=ReplyKeyboardHide())
		logging.info('/start vuelve usuario %i ' % update.message.chat_id)
		return ConversationHandler.END
	

def help(bot, update):
	global config_users
	chat_id = str(update.message.chat_id)

	logging.info('Usuario %s comando /help ' % chat_id)

	texto = texto + ('/feedback Solicitar problemas en clase, valorar la última clase, '
		'o enviar solución a problemas propuestos\n'
		'/help Muestra este mensaje\n'
		'/settings Cambiar configuración\n'
		'/start Reiniciar el bot\n'
		'/stats Ver estadísticas\n'
		)

	update.message.reply_text(texto)


def button(bot, update):
    global config_users
    global FILE_USERS
    global FILE_RANDOM_RESULTS
    global FILE_NEWS_RESULTS
    global FILE_CLASES
	
    query = update.callback_query
    chat_id=str(query.message.chat_id)
    message_id=query.message.message_id

    logging.info('Usuario %s button %s ' % (chat_id, query.data) )

    #s para los settings
    if query.data[0] == 's':
    	dummy, parameter, reply = query.data.split(".")
    	if parameter == 'news':
    		if reply == 'si':
    			text="Notificaciones activadas"
    			config_users.set(chat_id, 'news', 'True')
    		else:
    			text="Notificaciones desactivadas"
    			config_users.set(chat_id, 'news', 'False')
    	else:
    		text="Parametro de settings no reconocido"
    	bot.editMessageText(text=text, chat_id=int(chat_id), message_id=message_id)
    	save_config_users( FILE_USERS )
    	logging.info('Usuario %s pone configuracion news: %s' % (chat_id, config_users.get(chat_id, 'news')))

    #n para las noticias
    elif query.data[0] == 'n':
    	dummy, identifier, reply = query.data.split(".")
    	if reply == 'si':
    		text="Vale!"
    	else:
    		text="Vaya..."
    	with codecs.open(FILE_NEWS_RESULTS, "a", "utf-8") as myfile:
    		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), identifier, str(chat_id), reply))    	
    	bot.editMessageText(text=text, chat_id=int(chat_id), message_id=message_id)
    	logging.info('Usuario %s responde news %s con %s' % (chat_id, identifier, reply))

    else:
    	print ('No entiendo')


def echo(bot, update):
    update.message.reply_text('No entiendo. Escriba /help para ayuda')


def error(bot, update, error):
    logging.warn('Update "%s" caused error "%s"' % (update, error))


def todays_news(bot,job):
	global config_users
	global calendar
	global FILE_NEWS
	logging.info('Se lanza todays_news')
	
	num_news = load_calendar(FILE_NEWS, calendar)
	todays_key = datetime.date.today().strftime("%Y-%m-%d")
	
	if todays_key in calendar:
		for user in config_users.sections():
			if eval(config_users.get(user,'news')):
				bot.sendMessage(chat_id=int(user), text=calendar[todays_key], parse_mode='HTML')
				keyboard = [[InlineKeyboardButton("Si", callback_data='n.'+todays_key+'.si'),
				InlineKeyboardButton("No", callback_data='n.'+todays_key+'.no')]]
				reply_markup = InlineKeyboardMarkup(keyboard)
				bot.sendMessage(chat_id=int(key), text='¿Te ha parecido interesante?', reply_markup=reply_markup)


def feedback(bot, update, user_data):
	user_data['capitulo'] = -1
	logging.info('Usuario %i comando /feedback ' % update.message.chat_id)
	update.message.reply_text('Qué tipo de feedback quieres dar:', reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
	return TIPO_FEEDBACK

def feedback_clase(bot, update):
	update.message.reply_text('Feedback sobre la última clase:', reply_markup=ReplyKeyboardMarkup(reply_keyboard_clase, one_time_keyboard=True))
	return CLASE_VALORADA

def feedback_clase_valorada(bot, update):
	global FILE_CLASES
	chat_id = str(update.message.chat_id)
	text = update.message.text
	with codecs.open(FILE_CLASES, "a", "utf-8") as myfile:
		myfile.write("%s\t%s\t%s\t%s\n" % (str(datetime.datetime.now()), "ultclase", chat_id, text))
	update.message.reply_text('Gracias por la valoración, ¿alguna cosa más?',  reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
	return TIPO_FEEDBACK

def feedback_votar(bot, update, user_data):
	numero = update.message.text
	if (int(user_data['capitulo'])<0):
		user_data['capitulo']=0
		reply_keyboard = [['1','2','3','4'],['5','6','7']]
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
	
	update.message.reply_text('Problema %s.%s solicitado, ¿algo más?' %(user_data['capitulo'], user_data['problema']),
	  reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
	
	user_data['capitulo']=-1	
	return TIPO_FEEDBACK	


def feedback_elegir_problema(bot, update, user_data):
	global FILE_SOLUCIONES
	global config_users
	chat_id = str(update.message.chat_id)
	propuestos = list()

	with codecs.open(FILE_SOLUCIONES, 'r', 'utf-8') as myfile:
		for myline in myfile:
			(prob, sol) = myline.strip('\n').split("\t")
			if 'Propuesto' in sol:
				propuestos.append(prob)

	if propuestos == list():
		update.message.reply_text('No hay ningún problema propuesto actualmente. '
			'¿Alguna otra cosa?',  reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		reply_keyboard_propuestos = []
		reply_keyboard_propuestos.append(propuestos)
		update.message.reply_text('Elige problema para enviar solución: ', reply_markup=ReplyKeyboardMarkup(reply_keyboard_propuestos, one_time_keyboard=True))
		return TIPO_FEEDBACK


def feedback_solucion(bot, update, user_data):
	global FILE_SOLUCIONES
	global config_users
	chat_id = str(update.message.chat_id)
	problema = update.message.text

	if config_users.has_option(chat_id, problema):
		txt = 'Para el problema '+problema+' ya tenías la solución '+config_users.get(chat_id, problema)+'. '
		txt = txt + 'Escribe tu solución o "Zzz" para cancelar: '
	else:
		txt = 'Escribe tu solución para el problema '+problema+': '

	user_data['solucion']=0
	user_data['prob'] = problema
	update.message.reply_text(txt)
	return SOLUCION_A_ENVIAR


def feedback_solucion_recibida(bot, update, user_data):
	global config_users
	chat_id = str(update.message.chat_id)

	user_data['solucion'] = update.message.text
	user_data['timestamp'] = str(datetime.datetime.now())
	if user_data['solucion'] == 'Zzz':
		update.message.reply_text('Cancelado. Elija opción:', reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		reply_keyboard = [["Sí","No"]]
		update.message.reply_text('Solución a enviar: %s \n ¿Confirmar?' % user_data['solucion'], 
			reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
		return SOLUCION_ENVIADA

def feedback_solucion_enviada(bot, update, user_data):
	global FILE_USERS
	global config_users
	chat_id = str(update.message.chat_id)

	if update.message.text=='Sí':
		config_users.set(chat_id, user_data['prob'], user_data['solucion'])
		config_users.set(chat_id, user_data['prob']+'timestamp', user_data['timestamp'])
		save_config_users(FILE_USERS)
		update.message.reply_text('Solución guardada, ¿alguna cosa más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
		return TIPO_FEEDBACK
	else:
		update.message.reply_text('No se ha guardado la solución. Escribe la solución del problema propuesto (xxx para cancelar):')
		return SOLUCION_A_ENVIAR

def feedback_texto(bot, update):
	update.message.reply_text('Texto libre para enviar:')
	return TEXTO_ENVIADO

def feedback_texto_recibido(bot, update):
	global FILE_TEXT
	with codecs.open(FILE_TEXT, "a", "utf-8") as myfile:
		myfile.write("%s\t%s\t%s\n" % (str(datetime.datetime.now()), str(update.message.chat_id), str(update.message.text)))
	update.message.reply_text('Texto guardado. ¿Alguna cosa más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_feedback, one_time_keyboard=True))
	return TIPO_FEEDBACK

def feedback_done(bot, update, user_data):
	update.message.reply_text('Ok!')
	user_data.clear()
	return ConversationHandler.END


def settings(bot, update):
	global config_users
	chat_id = str(update.message.chat_id)
	logging.info('Usuario %s comando /settings ' % chat_id)

	if eval(config_users.get(chat_id,'news')):
		avisos = 'activados'
	else:
		avisos = 'desactivados'

	update.message.reply_text('Tienes los avisos %s. '
		'Elige si quieres cambiar la configuración o nada' % avisos, reply_markup=ReplyKeyboardMarkup(reply_keyboard_settings, one_time_keyboard=True))
	return TIPO_SETTINGS

def settings_config(bot, update):
	logging.info('Usuario %i comando /settings-config ' % update.message.chat_id)

	keyboard = [[InlineKeyboardButton("Sí", callback_data='s.news.si'),
		InlineKeyboardButton("No", callback_data='s.news.no')]]
	reply_markup = InlineKeyboardMarkup(keyboard)
	update.message.reply_text('Recibir notificaciones sobre efemérides y anécdotas relacionada con la asignatura:', reply_markup=reply_markup)

	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_settings, one_time_keyboard=True))
	return TIPO_SETTINGS

def settings_done(bot, update):
	update.message.reply_text('Vale!')
	return ConversationHandler.END


def stats(bot, update):
	global config_users
	global FILE_USERS
	global FILE_LOG
	chat_id = str(update.message.chat_id)

	logging.info('Usuario %s comando /stats ' % chat_id)
	update.message.reply_text('Qué quieres saber', reply_markup=ReplyKeyboardMarkup(reply_keyboard_stats, one_time_keyboard=True))
	return TIPO_STATS


def stats_problems(bot, update):
	global FILE_PROBLEMAS

	update.message.reply_text('Problemas más votados:')
	df = pd.read_csv(FILE_PROBLEMAS,sep='\t',header=0,names=['date','uid','prob'])
	psol = df.groupby('prob').uid.nunique()
	psol.sort_values(ascending=False,inplace=True)
	update.message.reply_text('%s' % psol.to_string() )

	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_stats, one_time_keyboard=True))
	return TIPO_STATS


def stats_solutions(bot, update):
	global FILE_SOLUCIONES
	global config_users
	chat_id = str(update.message.chat_id)

	txt_soluciones = "<b>Soluciones hasta ahora:</b>\n"
	with codecs.open(FILE_SOLUCIONES, 'r', 'utf-8') as myfile:
		for myline in myfile:
			(prob, sol) = myline.split("\t")
			if 'Propuesto' not in sol:
				txt_soluciones = txt_soluciones + prob + ": Solución = " + sol
				# OJO QUE SE USAN COMAS PARA DECIMALES (EN VEZ DE PUNTOS)
				solucion = float(sol.replace(",",".")) 
				respondieron = 0
				acertaron = 0
				txt_extra = "\n"
				for user in config_users.sections():
					if config_users.has_option(user,prob):
						respondieron += 1
						sol_enviada = float(config_users.get(user,prob).replace(",","."))

						if math.isclose(solucion, sol_enviada, rel_tol = REL_TOL):
							acertaron += 1
							if user == chat_id:
								txt_extra = ' (incl. la tuya)\n'					

				txt_soluciones = txt_soluciones + "Respuestas: " + str(respondieron) + " Correctas: " + str(acertaron) + txt_extra


	update.message.reply_text(txt_soluciones, parse_mode='HTML')

	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_stats, one_time_keyboard=True))
	return TIPO_STATS


def stats_ranking(bot, update):
	global FILE_SOLUCIONES
	global config_users
	chat_id = str(update.message.chat_id)
	MAX_LINES = 3

	soluciones = dict()

	with codecs.open(FILE_SOLUCIONES, 'r', 'utf-8') as myfile:
		for myline in myfile:
			(prob, sol) = myline.strip('\n').split("\t")
			if 'Propuesto' not in sol:
				soluciones[prob] = sol

	puntos = dict()
	for user in config_users.sections():
		puntos[user] = 0

	for prob in soluciones:
		sol_correcta = float(soluciones[prob].replace(",","."))
		ts_first = datetime.datetime.now()
		ts_last = datetime.datetime(2014, 5, 29, 20, 45) #LA DECIMAAAAAA

		for user in config_users.sections():
			if config_users.has_option(user,prob):
				sol_enviada = float(config_users.get(user,prob).replace(",","."))
				if  math.isclose(sol_correcta, sol_enviada, rel_tol = REL_TOL):
					ts_sol = parser.parse(config_users.get(user,prob+'timestamp'))
					if ts_sol < ts_first:
						ts_first = ts_sol
					if ts_sol > ts_last:
						ts_last = ts_sol

		prob_delta_minutes = (ts_last-ts_first).days*24*60 + (ts_last-ts_first).seconds/60

		for user in config_users.sections():
			if config_users.has_option(user,prob):
				sol_enviada = float(config_users.get(user,prob).replace(",","."))
				if  math.isclose(sol_correcta, sol_enviada, rel_tol = REL_TOL):
					ts_sol = parser.parse(config_users.get(user,prob+'timestamp'))
					points_extra = (ts_last - ts_sol).days*24*60 + (ts_last - ts_sol).seconds/60
					points_extra = points_extra/prob_delta_minutes
					puntos[user] += 1.0 + points_extra

	user_is_top = 0
	i = 1
	txt = "<b>Top "+ str(MAX_LINES) + " de la clasificación:</b>\n"
	for user in sorted(puntos, key=puntos.get, reverse=True):
	    if user == chat_id:
	        txt = txt + str(i) + '. ' + config_users.get(user,'nick') + " (tú)\t" + str(puntos[user]) + "\n"
	        if i <= MAX_LINES:
	            user_is_top = 1
	    else:
	        txt = txt + str(i) + '. ' + config_users.get(user,'nick') + "\t" + str(puntos[user]) + "\n"
	    i +=1

	txt_reply = ''
	i = 1
	for line in txt.splitlines():
	    if i <= MAX_LINES+1:
	        txt_reply = txt_reply + line + '\n'
	    i += 1

	if user_is_top == 0:
	    txt_reply = txt_reply + '---\n'
	    for line in txt.splitlines():
	        if config_users.get(user,'nick') in line:
	            txt_reply = txt_reply + line + '\n---\n'


	update.message.reply_text(txt_reply, parse_mode='HTML')

	update.message.reply_text('¿Algo más?', reply_markup=ReplyKeyboardMarkup(reply_keyboard_stats, one_time_keyboard=True))
	return TIPO_STATS


def stats_done(bot, update):
	update.message.reply_text('Ok')
	return ConversationHandler.END


def load_config_users( file ):
	global config_users
	config_users = configparser.ConfigParser()
	config_users.read_file(codecs.open(file, "r", "utf-8"))
	return len(config_users.sections())

def save_config_users( file ):
	global config_users

	with codecs.open(file, "w", "utf-8") as configfile: 
		config_users.write(configfile)


def main():
	global config_users
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
	global FILE_SOLUCIONES
	global FILE_NICKS
	global DIR_PROBLEMAS

	
	# Load configuration parameters
	config = configparser.ConfigParser()
	config.readfp(open(r'config.txt'))
	TELEGRAM_TOKEN = config.get('Tokens', 'telegram_token')
	FILE_USERS = config.get('Files', 'users')
	FILE_NEWS = config.get('Files', 'news')
	FILE_NEWS_RESULTS = config.get('Files', 'news_results')
	FILE_TEXT = config.get('Files', 'freetext')
	FILE_LOG = config.get('Files', 'log')
	FILE_CLASES = config.get('Files', 'clases')
	FILE_PROBLEMAS = config.get('Files', 'problemas')
	FILE_SOLUCIONES = config.get('Files', 'soluciones')
	FILE_NICKS = config.get('Files', 'nicks')

	#logging.basicConfig(level=logging.INFO,
    #                format='%(asctime)s %(levelname)s %(message)s',
    #                filename=FILE_LOG,
    #                filemode='a', encoding='utf-8')
	
	logging.basicConfig(handlers=[logging.FileHandler(FILE_LOG, 'a', 'utf-8')],
		level=logging.INFO,
		format='%(asctime)s %(levelname)s %(message)s')
	logging.getLogger().addHandler(logging.StreamHandler())

	# Global variables
	# users = defaultdict(list)
	calendar = defaultdict(list)
	num_users = load_config_users(FILE_USERS)
	logging.info('Arranco el bot con %s usuarios' % num_users)

	# Create the EventHandler and pass it your bot's token.
	updater = Updater(TELEGRAM_TOKEN)

	#Job queue to schedule updates
	jq = updater.job_queue
	#Cada 24 horas
	job_news = Job(todays_news, 24*60*60)
	#Calculo segundos hasta Hora de las news
	now = datetime.datetime.now()
	time_news = now.replace(hour=10, minute=0, second=0, microsecond=0)
	seconds = (time_news - now).total_seconds()
	if seconds < 0:
		seconds = seconds + 24*60*60
	jq.put(job_news, next_t=seconds)

	# Get the dispatcher to register handlers
	dp = updater.dispatcher

	conv_handler_feedback = ConversationHandler(
		entry_points=[CommandHandler('feedback', feedback, pass_user_data=True)],

		states={
			TIPO_FEEDBACK: [RegexHandler('^Valorar clase$', feedback_clase),
			RegexHandler('^(Votar problema|Votar otro problema)$', feedback_votar, pass_user_data=True),
			RegexHandler('^Enviar solución$', feedback_elegir_problema, pass_user_data=True),
			RegexHandler('^P[0-2][0-9]$', feedback_solucion, pass_user_data=True),
			RegexHandler('^(Nada|No)$', feedback_done, pass_user_data=True) 
			],

			CLASE_VALORADA: [RegexHandler('^Enviar texto libre$', feedback_texto),
			MessageHandler(Filters.text, feedback_clase_valorada),
			],

			PEDIR_PROBLEMA: [MessageHandler(Filters.text, feedback_votar, pass_user_data=True),
			],

			PROBLEMA_PEDIDO: [MessageHandler(Filters.text, feedback_problema_votado, pass_user_data=True),
			],

			SOLUCION_A_ENVIAR: [MessageHandler(Filters.text, feedback_solucion_recibida, pass_user_data=True),
			],

			SOLUCION_ENVIADA:[MessageHandler(Filters.text, feedback_solucion_enviada, pass_user_data=True),
			],

			TEXTO_ENVIADO: [MessageHandler(Filters.text, feedback_texto_recibido), 
			]
		},

		fallbacks=[RegexHandler('^(Nada|No)$', feedback_done, pass_user_data=True), 
		CommandHandler('start', start)]
	)
	dp.add_handler(conv_handler_feedback)


	conv_handler_settings = ConversationHandler(
		entry_points=[CommandHandler('settings', settings)],

		states={
			TIPO_SETTINGS: [RegexHandler('^Cambiar configuración$', settings_config),
			RegexHandler('^Nada$', settings_done) 
			],
		},

		fallbacks=[RegexHandler('^(Nada|No)$', settings_done), 
		CommandHandler('start', start)]
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

		fallbacks=[RegexHandler('^(Nada|No)$', stats_done),
		CommandHandler('start', start)]
	)
	dp.add_handler(conv_handler_stats)


	# on different commands - answer in Telegram
	dp.add_handler(CommandHandler("start", start))
	dp.add_handler(CommandHandler("help", help))
	
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
