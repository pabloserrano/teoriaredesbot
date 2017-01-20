#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import random
import logging
import configparser
import string
from telegram import (InlineKeyboardButton,
                      InlineKeyboardMarkup,
                      ReplyKeyboardMarkup,
                      ReplyKeyboardHide)
from telegram.ext import (Updater,
                          CommandHandler,
                          ConversationHandler,
                          MessageHandler,
                          Filters,
                          CallbackQueryHandler,
                          RegexHandler,
                          Job)
import codecs
import math
from dateutil import parser


REL_TOL = 1e-4


class TRBot:
    def __init__(self):
        config = configparser.ConfigParser()
        config.readfp(open(r'config.txt'))
        tokenBot = config.get('Tokens', 'tokenBot')
        file_log = config.get('General', 'log')
        self.file_avisos = config.get('General', 'avisos')
        self.file_users = config.get('General', 'users')
        self.file_nicks = config.get('General', 'nicks')
        # Bloque de Noticias a enviar diariamente
        self.file_news_texto = config.get('Noticias', 'texto')
        self.file_news_votos = config.get('Noticias', 'votos')
        # Bloque Opinar sobre clases
        self.file_opinar_texto = config.get('Opinar', 'texto')
        self.file_opinar_votos = config.get('Opinar', 'votos')
        # Bloque Solicitar problemas a hacer en clase
        self.file_solicitar_probs = config.get('Solicitar', 'problemas')
        # Bloque Reto hacer problemas
        self.file_reto_probs = config.get('Reto', 'propuestos')

        logging.basicConfig(
            handlers=[logging.FileHandler(file_log, 'a', 'utf-8')],
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s')
        logging.getLogger().addHandler(logging.StreamHandler())
        self.users = configparser.ConfigParser()
        self.users.read_file(codecs.open(self.file_users, "r", "utf-8"))
        self.updater = Updater(tokenBot)
        self._schedule_noticias()

        # Get the dispatcher to register handlers
        dp = self.updater.dispatcher
        dp.add_handler(RetoConversationHandler(self))
        dp.add_handler(OpinarConversationHandler(self))
        dp.add_handler(SettingsConversationHandler(self))
        dp.add_handler(SolicitarConversationHandler(self))
        # on different commands - answer in Telegram
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help))
        dp.add_handler(CallbackQueryHandler(self.button))
        # on noncommand i.e message - echo the message on Telegram
        dp.add_handler(MessageHandler(Filters.text, self.echo))
        # log all errors
        dp.add_error_handler(self.error)

    def run(self):
        logging.info('Arranco el bot')
        self.updater.start_polling()

        # Run the bot until the you presses Ctrl-C
        # or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        self.updater.idle()

    def _schedule_noticias(self):
        # Job queue to schedule updates
        jq = self.updater.job_queue
        # Cada 24 horas
        job_news = Job(self.noticias, 24 * 60 * 60)
        # Calculo segundos hasta Hora de las news
        now = datetime.datetime.now()
        time_news = now.replace(hour=10, minute=0, second=0, microsecond=0)
        seconds = (time_news - now).total_seconds()
        if seconds < 0:
            seconds = seconds + 24 * 60 * 60
        jq.put(job_news, next_t=seconds)

    def noticias(self, bot, job):
        logging.info('Se lanza noticias')
        today = datetime.date.today().strftime("%Y-%m-%d")
        with codecs.open(self.file_news_texto, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (date, text) = myline.split("\t")
                if date == today:
                    for user in self.users.sections():
                        if self.users.get(user, 'news') == 'True':
                            bot.sendMessage(chat_id=int(user),
                                            text=text,
                                            parse_mode='HTML')
                            keyboard = [[
                                InlineKeyboardButton("Si",
                                        callback_data='n.' + today + '.si'),
                                InlineKeyboardButton("No",
                                        callback_data='n.' + today + '.no')]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            bot.sendMessage(
                                chat_id=int(user),
                                text='¿Te ha parecido interesante?',
                                reply_markup=reply_markup)

    def error(self, bot, update, error):
        logging.warn('Update "%s" caused error "%s"' % (update, error))

    def echo(self, bot, update):
        logging.info('Usuario %i comando raro que no se entiende '
                     % update.message.chat_id)
        update.message.reply_text('No entiendo. Escriba /help para ayuda')

    def start(self, bot, update):
        chat_id = str(update.message.chat_id)
        if chat_id not in self.users.sections():
            logging.info('/start nuevo usuario: %s ' % chat_id)
            self.users.add_section(chat_id)
            self.users.set(chat_id, 'news', 'True')
            self.users.set(chat_id, 'ignore', 'False')
            self.users.set(chat_id, 'admin', 'False')
            self.users.set(chat_id, 'votados', '')

            nicks = codecs.open(self.file_nicks, 'r', 'utf-8')\
                          .read()\
                          .splitlines()
            # Comprobamos que haya nicks libres
            libres = 0
            for line in nicks:
                nick, taken = line.split(',')
                if taken == '0':
                    libres += 1

            if libres > 0:
                nick_taken = 1
                while nick_taken == 1:
                    nick, nick_taken = random.choice(nicks).split(",")
            else:
                # PBL TODO XXX FIX ENVIAR NOTIFICACION
                logging.info('No hay nicks disponibles')
                nick = 'N' + ''.join(
                    random.SystemRandom().choice(string.digits)
                    for _ in range(10))

            self.users.set(chat_id, 'nick', nick)
            update.message.reply_text(
                '¡Hola! Por defecto, notificaciones activadas'
                '(usa el comando /help para ayuda). Te ha tocado el nick '
                '%s, puedes usar el comando /start para recordarlo '
                'y para reiniciar el bot si algo va mal' % nick)
            f = codecs.open(self.file_nicks, 'w', 'utf-8')
            for line in nicks:
                if nick not in line:
                    f.write(line + "\n")
                else:
                    f.write(nick + ",1\n")
            f.close()
            self.save_config_users()
        else:
            update.message.reply_text(
                'Hola de nuevo, tu nick es %s'
                % self.users.get(chat_id, 'nick'),
                reply_markup=ReplyKeyboardHide())
            logging.info('/start vuelve usuario %i ' % update.message.chat_id)
            return ConversationHandler.END

    def help(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('Usuario %s comando /help ' % chat_id)

        texto = (
            '/feedback Solicitar problemas en clase, valorar la última clase, '
            'o enviar solución a problemas propuestos\n'
            '/help Muestra este mensaje\n'
            '/settings Cambiar configuración\n'
            '/start Reiniciar el bot\n'
            '/stats Ver estadísticas\n'
        )
        update.message.reply_text(texto, parse_mode='HTML')

    def button(self, bot, update):
        query = update.callback_query
        chat_id = str(query.message.chat_id)
        message_id = query.message.message_id
        logging.info('Usuario %s button %s ' % (chat_id, query.data))
        self.users.set(chat_id, 'lastseen', str(datetime.datetime.now()))
        # s para los settings
        if query.data[0] == 's':
            dummy, parameter, reply = query.data.split(".")
            if parameter == 'news':
                if reply == 'si':
                    text = "Notificaciones activadas"
                    self.users.set(chat_id, 'news', 'True')
                else:
                    text = "Notificaciones desactivadas"
                    self.users.set(chat_id, 'news', 'False')
            bot.editMessageText(text=text,
                                chat_id=int(chat_id),
                                message_id=message_id)
            self.save_config_users()
            logging.info('Usuario %s pone configuracion news: %s'
                         % (chat_id, self.users.get(chat_id, 'news')))
        # n para las noticias
        elif query.data[0] == 'n':
            dummy, identifier, reply = query.data.split(".")
            if reply == 'si':
                text = "Vale!"
            else:
                text = "Vaya..."
            with codecs.open(self.file_news_votos, "a", "utf-8") as myfile:
                myfile.write("%s\t%s\t%s\t%s\n"
                             % (str(datetime.datetime.now()),
                                identifier,
                                str(chat_id),
                                reply))
            bot.editMessageText(text=text,
                                chat_id=int(chat_id),
                                message_id=message_id)
            logging.info('Usuario %s responde news %s con %s'
                         % (chat_id, identifier, reply))

    def save_config_users(self):
        with codecs.open(self.file_users, "w", "utf-8") as configfile:
            self.users.write(configfile)


class OpinarConversationHandler(ConversationHandler):

    OPINAR_ENTRADA = 1
    OPINAR_VOTADO = 2
    OPINAR_TEXTO = 3

    kb_opinar = [
        ['Valorar última clase'],
        ['Enviar texto libre'],
        ['Nada']
    ]
    kb_votos = [
        ['Más teoría', 'Más problemas'],
        ['Está bien así', 'Ns/Nc']
    ]

    def __init__(self, tr_bot):
        self.tr_bot = tr_bot
        super().__init__(
            entry_points=[
                CommandHandler('opinar',
                               self.opinar,
                               pass_user_data=True)],
            states={
                self.OPINAR_ENTRADA: [
                    RegexHandler('^Valorar última clase$',
                                 self.opinar_votar),
                    RegexHandler('^Enviar texto libre$',
                                 self.opinar_texto,
                                 pass_user_data=True),
                    RegexHandler('^(Nada|No)$',
                                 self.opinar_fin,
                                 pass_user_data=True)
                ],
                self.OPINAR_VOTADO: [
                    MessageHandler(Filters.text,
                                   self.opinar_voto_recibido),
                ],
                self.OPINAR_TEXTO: [
                    MessageHandler(Filters.text,
                                   self.opinar_texto_recibido),
                ]
            },
            fallbacks=[
                RegexHandler('^(Nada|No)$',
                             self.opinar_fin,
                             pass_user_data=True),
                CommandHandler('start', self.tr_bot.start)
            ]
        )

    def opinar(self, bot, update, user_data):
        user_data['capitulo'] = -1
        logging.info('Usuario %i comando /feedback ' % update.message.chat_id)
        update.message.reply_text(
            'Qué tipo de opinión quieres dar:',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_votar(self, bot, update):
        update.message.reply_text(
            'Opinión sobre la última clase:',
            reply_markup=ReplyKeyboardMarkup(self.kb_votos,
                                             one_time_keyboard=True))
        return self.OPINAR_VOTADO

    def opinar_voto_recibido(self, bot, update):
        chat_id = str(update.message.chat_id)
        text = update.message.text
        with codecs.open(
                self.tr_bot.file_opinar_votos, "a", "utf-8") as myfile:
            myfile.write("%s\t%s\t%s\n"
                         % (str(datetime.datetime.now()), chat_id, text))
        update.message.reply_text(
            'Gracias por la valoración, ¿alguna cosa más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_texto(self, bot, update, user_data):
        update.message.reply_text('Texto libre para enviar:')
        return self.OPINAR_TEXTO

    def opinar_texto_recibido(self, bot, update):
        with codecs.open(self.tr_bot.file_opinar_texto, "a", "utf-8") as myfile:
            myfile.write("%s\t%s\t%s\n"
                         % (str(datetime.datetime.now()),
                            str(update.message.chat_id),
                            str(update.message.text)))
        update.message.reply_text(
            'Texto guardado. ¿Alguna cosa más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_fin(self, bot, update, user_data):
        update.message.reply_text('Ok!', reply_markup=ReplyKeyboardHide())
        user_data.clear()
        return ConversationHandler.END


class RetoConversationHandler(ConversationHandler):

    RETO_ENTRADA = 1
    RETO_RECIBIDA = 2

    kb_reto = [
        [['Ver enunciados'], ['Ver soluciones']],
        [['Enviar solución'], ['Clasificación']],
        [['Nada']]
    ]

    def __init__(self, tr_bot):
        self.tr_bot = tr_bot
        super().__init__(
            entry_points=[
                CommandHandler('reto', self.reto, pass_user_data=True)
            ],
            states={
                self.RETO_ENTRADA: [
                    RegexHandler('^P[0-2][0-9]$',
                                 self.reto_enviar,
                                 pass_user_data=True),
                    RegexHandler('^Ver enunciados$',
                                 self.reto_enunciados),
                    RegexHandler('^Ver soluciones$',
                                 self.reto_soluciones),
                    RegexHandler('^Enviar solución$',
                                 self.reto_elegir,
                                 pass_user_data=True),
                    RegexHandler('^Tabla de clasificación$',
                                 self.reto_tabla),
                    RegexHandler('^Nada$',
                                 self.reto_fin)
                ],
                self.RETO_RECIBIDA: [
                    MessageHandler(Filters.text,
                                   self.reto_recibida,
                                   pass_user_data=True),
                ]
            },
            fallbacks=[RegexHandler('^(Nada|No)$', self.reto_fin),
                       CommandHandler('start', self.tr_bot.start)]
        )

    def reto(self, bot, update, user_data):
        user_data['capitulo'] = -1   # Pues esto no estará bien
        chat_id = str(update.message.chat_id)

        logging.info('Usuario %s comando /stats ' % chat_id)
        update.message.reply_text(
            'Qué quieres hacer',
            reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                             one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_enunciados(self, bot, update):
        reto_activo = False
        with codecs.open(self.tr_bot.file_reto_probs, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (prob, sol) = myline.strip('\n').split("\t")
                if 'Propuesto' in sol:
                    reto_activo = True
        if reto_activo:
            texto = (
                'El enunciado de los problemas propuestos está '
                '<a href="http://www.it.uc3m.es/pablo/propuestos.pdf">'
                'en este enlace</a>. \n '
            )
        else:
            texto = 'Ahora mismo no hay problemas propuestos \n'

        texto += 'Alguna cosa más?'
        update.message.reply_text(texto,
                                  reply_markup=ReplyKeyboardMarkup(
                                            self.kb_reto,
                                            one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_soluciones(self, bot, update):
        chat_id = str(update.message.chat_id)
        txt = "<b>Soluciones hasta ahora:</b>\n"
        with codecs.open(self.tr_bot.file_reto_probs, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (prob, sol) = myline.split("\t")
                if 'Propuesto' not in sol:
                    txt = txt + prob + ": Solución = " + sol
                    # OJO QUE SE USAN COMAS PARA DECIMALES (EN VEZ DE PUNTOS)
                    solucion = float(sol.replace(",", "."))
                    respondieron = 0
                    acertaron = 0
                    txt_extra = "\n"
                    for user in self.tr_bot.users.sections():
                        if self.tr_bot.users.has_option(user, prob):
                            respondieron += 1
                            sol_enviada = \
                                float(self.tr_bot.users.get(user, prob)
                                                       .replace(",", "."))
                            if math.isclose(solucion, sol_enviada,
                                            rel_tol=REL_TOL):
                                acertaron += 1
                                if user == chat_id:
                                    txt_extra = ' (incl. la tuya)\n'
                    txt = (txt + "Respuestas: " + str(respondieron) +
                           " Correctas: " + str(acertaron) + txt_extra)
        update.message.reply_text(txt, parse_mode='HTML')
        update.message.reply_text(
            '¿Algo más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                             one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_elegir(self, bot, update, user_data):
        # chat_id = str(update.message.chat_id)
        propuestos = list()
        with codecs.open(self.tr_bot.file_reto_probs, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (prob, sol) = myline.strip('\n').split("\t")
                if 'Propuesto' in sol:
                    propuestos.append(prob)
        if propuestos == list():
            update.message.reply_text(
                'No hay ningún problema propuesto actualmente. '
                '¿Alguna otra cosa?',
                reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                                 one_time_keyboard=True))
            return self.RETO_ENTRADA
        else:
            kb_probs = []
            kb_probs.append(propuestos)
            update.message.reply_text(
                'El enunciado de los problemas propuestos está '
                '<a href="http://www.it.uc3m.es/pablo/propuestos.pdf">'
                'en este enlace</a>. '
                'Elige problema para enviar solución: ',
                reply_markup=ReplyKeyboardMarkup(kb_probs,
                                                 one_time_keyboard=True),
                parse_mode='HTML')
            return self.RETO_ENTRADA

    def reto_enviar(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        problema = update.message.text
        if self.tr_bot.users.has_option(chat_id, problema):
            txt = ('Para el problema ' + problema + ' ya tenías la solución ' +
                   self.tr_bot.users.get(chat_id, problema) + '. ' +
                   'Escribe tu solución o "Zzz" para cancelar: ')
        else:
            txt = 'Escribe tu solución para el problema ' + problema + ': '
        user_data['solucion'] = 0
        user_data['prob'] = problema
        update.message.reply_text(txt, reply_markup=ReplyKeyboardHide())
        return self.RETO_RECIBIDA

    def reto_recibida(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        user_data['solucion'] = update.message.text
        user_data['timestamp'] = str(datetime.datetime.now())
        if user_data['solucion'] == 'Zzz':
            update.message.reply_text(
                'Cancelado. Elija opción:',
                reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                                 one_time_keyboard=True))
            return self.RETO_ENTRADA
        else:
            self.tr_bot.users.set(chat_id, user_data['prob'],
                                  user_data['solucion'])
            self.tr_bot.users.set(chat_id, user_data['prob'] + 'timestamp',
                                  user_data['timestamp'])
            self.tr_bot.save_config_users()
            update.message.reply_text(
                'Solución guardada, ¿alguna cosa más?',
                reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                                 one_time_keyboard=True))
            return self.RETO_ENTRADA

    def reto_tabla(self, bot, update):
        chat_id = str(update.message.chat_id)
        MAX_LINES = 3
        soluciones = dict()
        with codecs.open(self.tr_bot.file_reto_probs, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (prob, sol) = myline.strip('\n').split("\t")
                if 'Propuesto' not in sol:
                    soluciones[prob] = sol
        puntos = dict()
        for user in self.tr_bot.users.sections():
            puntos[user] = 0

        for prob in soluciones:
            sol_correcta = float(soluciones[prob].replace(",", "."))
            ts_first = datetime.datetime.now()
            ts_last = datetime.datetime(2014, 5, 29, 20, 45)  # LA DECIMAAAAAA
            for user in self.tr_bot.users.sections():
                if self.tr_bot.users.has_option(user, prob):
                    sol_enviada = float(self.tr_bot.users.get(user, prob)
                                                         .replace(",", "."))
                    if math.isclose(sol_correcta, sol_enviada,
                                    rel_tol=REL_TOL):
                        ts_sol = parser.parse(
                            self.tr_bot.users.get(user,
                                                  prob + 'timestamp'))
                        if ts_sol < ts_first:
                            ts_first = ts_sol
                        if ts_sol > ts_last:
                            ts_last = ts_sol
            delta = ((ts_last - ts_first).days * 24 * 60 +
                     (ts_last - ts_first).seconds / 60)
            for user in self.tr_bot.users.sections():
                if self.tr_bot.users.has_option(user, prob):
                    sol_enviada = float(self.tr_bot.users.get(user, prob)
                                                         .replace(",", "."))
                    if math.isclose(sol_correcta, sol_enviada,
                                    rel_tol=REL_TOL):
                        if delta > 0:
                            ts_sol = parser.parse(
                                self.tr_bot.users.get(user,
                                                      prob + 'timestamp'))
                            points_extra = ((ts_last - ts_sol).days * 24 * 60 +
                                            (ts_last - ts_sol).seconds / 60)
                            points_extra = points_extra / delta
                            puntos[user] += 1.0 + points_extra
                        else:
                            puntos[user] += 2.0
        user_is_top = 0
        i = 1
        txt = "<b>Top " + str(MAX_LINES) + " de la clasificación:</b>\n"
        for user in sorted(puntos, key=puntos.get, reverse=True):
            if user == chat_id:
                txt = (txt + str(i) + '. ' +
                       self.tr_bot.users.get(user, 'nick') +
                       " (tú)\t" + str(puntos[user]) + "\n")
                if i <= MAX_LINES:
                    user_is_top = 1
            else:
                txt = (txt + str(i) + '. ' +
                       self.tr_bot.users.get(user, 'nick') +
                       "\t" + str(puntos[user]) + "\n")
            i += 1
        txt_reply = ''
        i = 1
        for line in txt.splitlines():
            if i <= MAX_LINES + 1:
                txt_reply = txt_reply + line + '\n'
            i += 1
        if user_is_top == 0:
            txt_reply = txt_reply + '---\n'
            for line in txt.splitlines():
                if self.tr_bot.users.get(user, 'nick') in line:
                    txt_reply = txt_reply + line + '\n---\n'
        update.message.reply_text(txt_reply, parse_mode='HTML')
        update.message.reply_text(
            '¿Algo más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                             one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_fin(self, bot, update):
        update.message.reply_text('Ok')
        return ConversationHandler.END


class SolicitarConversationHandler(ConversationHandler):

    SOLICITAR_ENTRADA = 1
    SOLICITAR_CAPITULO = 2
    SOLICITAR_VOTADO = 3

    kb_solicitar = [
        ['Solicitar problema'],
        ['Ver más solicitados'],
        ['Nada']
    ]

    def __init__(self, tr_bot):
        self.tr_bot = tr_bot
        super().__init__(
            entry_points=[
                CommandHandler('solicitar',
                               self.solicitar,
                               pass_user_data=True)],
            states={
                self.SOLICITAR_ENTRADA: [
                    RegexHandler('^(Solicitar problema|\
                                    Solicitar otro problema)$',
                                 self.solicitar_votar,
                                 pass_user_data=True),
                    RegexHandler('^Ver más solicitados$',
                                 self.solicitar_stats,
                                 pass_user_data=True),
                    RegexHandler('^(Nada|No)$',
                                 self.solicitar_fin,
                                 pass_user_data=True)
                ],
                self.SOLICITAR_CAPITULO: [
                    MessageHandler(Filters.text,
                                   self.solicitar_votar,
                                   pass_user_data=True),
                ],
                self.SOLICITAR_VOTADO: [
                    MessageHandler(Filters.text,
                                   self.solicitar_votado,
                                   pass_user_data=True),
                ],
            },
            fallbacks=[
                RegexHandler('^(Nada|No)$',
                             self.solicitar_fin,
                             pass_user_data=True),
                CommandHandler('start', self.tr_bot.start)
            ]
        )

    def solicitar(self, bot, update, user_data):
        user_data['capitulo'] = -1
        logging.info('Usuario %i comando /feedback ' % update.message.chat_id)
        update.message.reply_text(
            'Qué quieres hacer:',
            reply_markup=ReplyKeyboardMarkup(self.kb_solicitar,
                                             one_time_keyboard=True))
        return self.SOLICITAR_ENTRADA

    def solicitar_votar(self, bot, update, user_data):
        problemas = configparser.ConfigParser()
        problemas.read_file(
            codecs.open(self.tr_bot.file_solicitar_probs, "r", "utf-8"))
        numero = update.message.text

        if (int(user_data['capitulo']) < 0):
            user_data['capitulo'] = 0
            kb_capitulo = []
            kb_capitulo.append(problemas.sections())
            # reply_keyboard = [['1','2','3','4'],['5','6','7']]
            update.message.reply_text(
                'De qué capítulo',
                reply_markup=ReplyKeyboardMarkup(kb_capitulo,
                                                 one_time_keyboard=True))
            return self.SOLICITAR_CAPITULO
        else:
            user_data['capitulo'] = numero
            kb_problema = []
            for problema in problemas.options(numero):
                if not eval(problemas.get(numero, problema)):
                    kb_problema.append(problema)
            update.message.reply_text(
                'Qué problema',
                reply_markup=ReplyKeyboardMarkup(kb_problema))
            return self.SOLICITAR_VOTADO

    def solicitar_votado(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        numero = update.message.text
        user_data['problema'] = numero
        logging.info('Usuario %s solicita problema %s.%s'
                     % (chat_id, user_data['capitulo'], user_data['problema']))
        prob_votados = set(
            self.tr_bot.users.get(chat_id, 'votados').split(','))
        votado = user_data['capitulo'] + '.' + user_data['problema']
        if votado in prob_votados:
            texto = 'Ya habías votado el problema ' + votado + ', ¿algo más?'
        else:
            texto = 'Problema ' + votado + ' votado, ¿algo más?'
            prob_votados.add(votado)
            votados_str = ','.join(str(e) for e in prob_votados)
            self.tr_bot.users.set(chat_id, 'votados', votados_str)
            self.tr_bot.save_config_users()
        update.message.reply_text(
            texto,
            reply_markup=ReplyKeyboardMarkup(self.kb_solicitar,
                                             one_time_keyboard=True))
        user_data['capitulo'] = -1
        return self.SOLICITAR_ENTRADA

    def solicitar_stats(self, bot, update, user_data):
        problemas = configparser.ConfigParser()
        problemas.read_file(
            codecs.open(self.tr_bot.file_solicitar_probs, "r", "utf-8"))
        votos = dict()
        for capitulo in problemas.sections():
            for problema in problemas.options(capitulo):
                if not eval(problemas.get(capitulo, problema)):
                    prob = str(capitulo) + '.' + str(problema)
                    peticiones = 0

                    for user in self.tr_bot.users.sections():
                        prob_votados = \
                            set(self.tr_bot.users.get(user, 'votados')
                                .split(','))
                        if prob in prob_votados:
                            peticiones += 1
                    if peticiones > 0:
                        votos[prob] = peticiones
        texto = "<b>Top problemas más votados</b>\n"
        for w in sorted(votos, key=votos.get, reverse=True):
            texto = texto + str(w) + ' ' + str(votos[w]) + '\n'
        update.message.reply_text(texto, parse_mode='HTML')
        update.message.reply_text(
            '¿Algo más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_solicitar,
                                             one_time_keyboard=True))
        return self.SOLICITAR_ENTRADA

    def solicitar_fin(self, bot, update, user_data):
        update.message.reply_text('Vale!', reply_markup=ReplyKeyboardHide())
        return ConversationHandler.END

class SettingsConversationHandler(ConversationHandler):

    TIPO_SETTINGS = 1
    BORRAR_CONFIRMACION = 2

    keyboard_settings = [
        ['Cambiar configuración'],
        ['Borrar toda actividad'],
        ['Nada']
    ]

    def __init__(self, tr_bot):
        self.tr_bot = tr_bot
        super().__init__(
            entry_points=[
                CommandHandler('settings', self.settings)],
            states={
                self.TIPO_SETTINGS: [
                    RegexHandler('^Cambiar configuración$',
                                 self.settings_config),
                    RegexHandler('^Borrar toda actividad$',
                                 self.settings_borrar),
                    RegexHandler('^Nada$',
                                 self.settings_done)
                ],
                self.BORRAR_CONFIRMACION: [
                    MessageHandler(Filters.text, self.settings_borrado),
                ]
            },
            fallbacks=[
                RegexHandler('^(Nada|No)$', self.settings_done),
                CommandHandler('start', self.tr_bot.start)
            ]
        )

    def settings(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('Usuario %s comando /settings ' % chat_id)
        if eval(self.tr_bot.users.get(chat_id, 'news')):
            avisos = 'activados'
        else:
            avisos = 'desactivados'
        update.message.reply_text(
            'Tienes los avisos %s. '
            'Elige si quieres cambiar la configuración de los avisos, '
            'borrar toda la actividad (o nada)'
            % avisos,
            reply_markup=ReplyKeyboardMarkup(self.keyboard_settings,
                                             one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_borrar(self, bot, update):
        logging.info('Usuario %i comando /settings-borrar '
                     % update.message.chat_id)
        update.message.reply_text(
            'Se va a borrar toda la actividad del usuario en el bot. '
            'Para confirmar, escriba el texto "GUARDIOLA" ',
            reply_markup=ReplyKeyboardHide())
        return self.BORRAR_CONFIRMACION

    def settings_borrado(self, bot, update):
        usr = str(update.message.chat_id)
        if update.message.text == 'GUARDIOLA':
            logging.info('Usuario %s borra toda su actividad en el bot '
                         % usr)

            # Borrar configuración sobre los problemas propuestos
            for i in range(3):
                for j in range(10):
                    pr = 'P' + str(i) + str(j)
                    if self.tr_bot.users.has_option(usr, pr):
                        self.tr_bot.users.remove_option(usr, pr)
                        self.tr_bot.users.remove_option(usr, pr + 'timestamp')
            # Borrar configuración sobre los votados
            self.tr_bot.users.set(usr, 'votados', '')
            self.tr_bot.users.set(usr, 'lastseen',
                                  str(datetime.datetime.now()))
            self.tr_bot.save_config_users()

            # Borrar todo feedback en los ficheros: FILE_NEWS_RESULTS,
            #     FILE_FREETEXT, file_opinar_votos,
            news_results_lines = \
                codecs.open(self.tr_bot.file_news_votos, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_news_votos, 'w', 'utf-8')
            for line in news_results_lines:
                if usr not in line:
                    f.write(line + '\n')
            f.close()
            freetext_lines = \
                codecs.open(self.tr_bot.file_freetext, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_freetext, 'w', 'utf-8')
            for line in freetext_lines:
                if usr not in line:
                    f.write(line + '\n')
            f.close()
            encuestas_lines = \
                codecs.open(self.tr_bot.file_opinar_votos, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_opinar_votos, 'w', 'utf-8')
            for line in encuestas_lines:
                if usr not in line:
                    f.write(line + '\n')
            f.close()
            update.message.reply_text(
                'Se ha borrado toda la actividad en el bot, '
                '¿alguna cosa más?',
                reply_markup=ReplyKeyboardMarkup(self.keyboard_settings,
                                                 one_time_keyboard=True))
        else:
            logging.info('Usuario %s no borra toda la actividad en el bot '
                         % usr)
            update.message.reply_text(
                'No se ha borrado la actividad en el bot, '
                '¿alguna cosa más?',
                reply_markup=ReplyKeyboardMarkup(self.keyboard_settings,
                                                 one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_config(self, bot, update):
        logging.info('Usuario %i comando /settings-config '
                     % update.message.chat_id)

        keyboard = [
            [
                InlineKeyboardButton("Sí", callback_data='s.news.si'),
                InlineKeyboardButton("No", callback_data='s.news.no')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            'Recibir notificaciones sobre efemérides y anécdotas '
            'relacionada con la asignatura:',
            reply_markup=reply_markup)
        update.message.reply_text(
            '¿Algo más?',
            reply_markup=ReplyKeyboardMarkup(self.keyboard_settings,
                                             one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_done(self, bot, update):
        update.message.reply_text('Vale!', reply_markup=ReplyKeyboardHide())
        return ConversationHandler.END


def main():
    bot = TRBot()
    bot.run()


if __name__ == '__main__':
    main()
