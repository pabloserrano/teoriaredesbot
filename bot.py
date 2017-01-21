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
from pushover import init, Client


REL_TOL = 1e-4


def split_list(alist, wanted_parts=1):
    length = len(alist)
    return [ alist[ i * length // wanted_parts: (i + 1) * length // wanted_parts] 
             for i in range(wanted_parts) ]

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
        # Bloque Pedir problemas a hacer en clase
        self.file_pedir_probs = config.get('Pedir', 'problemas')
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
        self._schedule_avisos()
        self._schedule_noticias()
        # Pushover Notifications
        po_key = config.get('Pushover', 'key')
        po_api = config.get('Pushover', 'api')
        self.po_client = Client(po_key, api_token=po_api)

        # Get the dispatcher to register handlers
        dp = self.updater.dispatcher
        dp.add_handler(OpinarConversationHandler(self))
        dp.add_handler(PedirConversationHandler(self))
        dp.add_handler(RetoConversationHandler(self))
        dp.add_handler(SettingsConversationHandler(self))
        # on different commands - answer in Telegram
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help))
        dp.add_handler(CallbackQueryHandler(self.button))
        # on noncommand i.e message - echo the message on Telegram
        dp.add_handler(MessageHandler(Filters.text, self.echo))
        # log all errors
        dp.add_error_handler(self.error)

    def run(self):
        logging.info('El bot arranca')
        self.updater.start_polling()
        self.po_client.send_message("Se acaba de arrancar el bot", title="Inicio bot")

        # Run the bot until the you presses Ctrl-C
        # or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        self.updater.idle()

    def _schedule_avisos(self):
        # Job queue to schedule updates
        jq = self.updater.job_queue
        # Cada 24 horas
        job_avisos = Job(self.avisos, 5 * 60)
        jq.put(job_avisos, next_t=0)

    def avisos(self, bot, job):
        logging.info('Se mira si hay avisos')
        # De paso, leo el fichero de configuracion otra vez
        self.users.read_file(codecs.open(self.file_users, "r", "utf-8"))

        avisos = codecs.open(self.file_avisos, 'r', 'utf-8')\
            .read().splitlines()

        f = codecs.open(self.file_avisos, 'w', 'utf-8')
        for aviso in avisos:
            (enviar, text) = aviso.split("\t")
            if enviar == '1':
                logging.info('Hay un aviso')
                for user in self.users.sections():
                    bot.sendMessage(chat_id=int(user),
                                    text='AVISO: ' + text,
                                    parse_mode='HTML')
                f.write('0\t%s\n' % text)
            else:
                f.write(aviso + '\n')
        f.close()

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
        logging.info('Se mira si hay noticias')
        today = datetime.date.today().strftime("%Y-%m-%d")
        with codecs.open(self.file_news_texto, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (date, text) = myline.split("\t")
                if date == today:
                    logging.info('Hay una noticia')
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
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [echo]' % chat_id)
        update.message.reply_text('No entiendo. Escriba /help para ayuda')

    def start(self, bot, update):
        chat_id = str(update.message.chat_id)
        if chat_id not in self.users.sections():
            logging.info('STATS [%s] [nuevo]' % chat_id)
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
                # Hay que guardar el nick usado
                f = codecs.open(self.file_nicks, 'w', 'utf-8')
                for line in nicks:
                    if nick not in line:
                        f.write(line + "\n")
                    else:
                        f.write(nick + ",1\n")
                f.close()
            else:
                # PBL TODO XXX FIX ENVIAR NOTIFICACION
                self.po_client.send_message("Se ha acabado la lista de nicks",
                    title="Nicks agotados")
                logging.info('No hay nicks disponibles')
                nick = 'N' + ''.join(
                    random.SystemRandom().choice(string.digits)
                    for _ in range(10))

            self.users.set(chat_id, 'nick', nick)
            update.message.reply_text(
                '¡Hola! Por defecto, noticias y curiosidades activadas '
                '(usa el comando /help para ayuda). Te ha tocado el nick '
                '%s, puedes usar el comando /start para recordarlo '
                'y para reiniciar el bot si algo va mal' % nick)
            self.save_config_users()
        else:
            logging.info('STATS [%s] [reinicia]' % chat_id)
            update.message.reply_text(
                'Hola de nuevo, tu nick es %s'
                % self.users.get(chat_id, 'nick'),
                reply_markup=ReplyKeyboardHide())
            return ConversationHandler.END

    def help(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [help]' % chat_id)
        
        texto = (
            '/help Muestra este mensaje\n'
            '/opinar Valorar última clase, enviar texto libre\n'
            '/pedir Votar para que se resuelvan problemas en la '
            'siguiente sesión de problemas\n'
            '/reto Participar en el reto: ver problemas propuestos, '
            'enviar solución, ver soluciones, ver clasificación\n'
            '/settings Cambiar configuración\n'
            '/start Reiniciar el bot\n'
        )
        update.message.reply_text(texto, parse_mode='HTML')

    def button(self, bot, update):
        query = update.callback_query
        chat_id = str(query.message.chat_id)
        message_id = query.message.message_id
        # s para los settings
        if query.data[0] == 's':
            dummy, parameter, reply = query.data.split(".")
            if parameter == 'news':
                if reply == 'si':
                    logging.info('STATS [%s] [settings-activa]' % chat_id)
                    text = "Notificaciones activadas"
                    self.users.set(chat_id, 'news', 'True')
                else:
                    logging.info('STATS [%s] [settings-desactiva]' % chat_id)
                    text = "Notificaciones desactivadas"
                    self.users.set(chat_id, 'news', 'False')
            bot.editMessageText(text=text,
                                chat_id=int(chat_id),
                                message_id=message_id)
            self.save_config_users()
        # n para las noticias
        elif query.data[0] == 'n':
            dummy, identifier, reply = query.data.split(".")
            if reply == 'si':
                logging.info('STATS [%s] [noticia-interesa] %i ' % (chat_id, identifier))
                text = "Vale!"
            else:
                logging.info('STATS [%s] [noticia-no-interesa] %i ' % (chat_id, identifier))
                text = "Vaya..."
            with codecs.open(self.file_news_votos, "a", "utf-8") as myfile:
                myfile.write("%s\t%s\t%s\t%s\t%s\n"
                             % (str(datetime.datetime.now()),
                                identifier,
                                chat_id,
                                self.users.get(chat_id, 'nick'),
                                reply))
            bot.editMessageText(text=text,
                                chat_id=int(chat_id),
                                message_id=message_id)

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
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [opinar]' % chat_id)
        user_data['capitulo'] = -1
        update.message.reply_text(
            'Qué tipo de opinión quieres dar:',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_votar(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [votar]' % chat_id)   
        update.message.reply_text(
            'Opinión sobre la última clase:',
            reply_markup=ReplyKeyboardMarkup(self.kb_votos,
                                             one_time_keyboard=True))
        return self.OPINAR_VOTADO

    def opinar_voto_recibido(self, bot, update):
        chat_id = str(update.message.chat_id)
        text = update.message.text
        logging.info('STATS [%s] [voto-recibido] %s' % (chat_id, text))
        with codecs.open(
                self.tr_bot.file_opinar_votos, "a", "utf-8") as myfile:
            myfile.write("%s\t%s\t%s\t%s\n"
                         % (str(datetime.datetime.now()),
                            chat_id,
                            self.tr_bot.users.get(chat_id, 'nick'),
                            text))
        update.message.reply_text(
            'Gracias por la valoración, ¿alguna cosa más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_texto(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [texto]' % chat_id)
        update.message.reply_text('Texto libre para enviar:')
        return self.OPINAR_TEXTO

    def opinar_texto_recibido(self, bot, update):
        chat_id = str(update.message.chat_id)
        text = update.message.text
        logging.info('STATS [%s] [texto-recibido] %s' % (chat_id, text))
        with codecs.open(self.tr_bot.file_opinar_texto,
                         "a", "utf-8") as myfile:
            myfile.write("%s\t%s\t%s\t%s\n"
                         % (str(datetime.datetime.now()),
                            chat_id,
                            self.tr_bot.users.get(chat_id, 'nick'),
                            text))
        update.message.reply_text(
            'Texto guardado. ¿Alguna cosa más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_opinar,
                                             one_time_keyboard=True))
        return self.OPINAR_ENTRADA

    def opinar_fin(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [opinar-fin]' % chat_id)
        update.message.reply_text('Ok!', reply_markup=ReplyKeyboardHide())
        user_data.clear()
        return ConversationHandler.END


class RetoConversationHandler(ConversationHandler):

    RETO_ENTRADA = 1
    RETO_RECIBIDA = 2

    kb_reto = [
        ['Ver enunciados', 'Ver soluciones'],
        ['Enviar solución', 'Clasificación'],
        ['Nada']
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
                    RegexHandler('^Clasificación$',
                                 self.reto_clasificacion),
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
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto]' % chat_id)
        user_data['capitulo'] = -1   # Pues esto no estará bien
        update.message.reply_text(
            'Qué quieres hacer',
            reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                             one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_enunciados(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto-enunciados]' % chat_id)
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
                                      one_time_keyboard=True),
                                  parse_mode='HTML')
        return self.RETO_ENTRADA

    def reto_soluciones(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto-soluciones]' % chat_id)
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
                        if self.tr_bot.users.get(user, 'ignore') == 'False':
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
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto-elegir]' % chat_id)
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
        logging.info('STATS [%s] [reto-enviar] %s' % (chat_id, problema))

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
        text = update.message.text
        logging.info('STATS [%s] [reto-recibida] %s' % (chat_id, text))

        user_data['solucion'] = text
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

    def reto_clasificacion(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto-clasificacion]' % chat_id)

        MAX_LINES = 3
        soluciones = dict()
        with codecs.open(self.tr_bot.file_reto_probs, 'r', 'utf-8') as myfile:
            for myline in myfile:
                (prob, sol) = myline.strip('\n').split("\t")
                if 'Propuesto' not in sol:
                    soluciones[prob] = sol
        puntos = dict()
        for user in self.tr_bot.users.sections():
            if self.tr_bot.users.get(user, 'ignore') == 'False':
                puntos[user] = 0

        for prob in soluciones:
            sol_correcta = float(soluciones[prob].replace(",", "."))
            ts_first = datetime.datetime.now()
            ts_last = datetime.datetime(2014, 5, 29, 20, 45)  # LA DECIMAAAAAA
            for user in self.tr_bot.users.sections():
                if self.tr_bot.users.get(user, 'ignore') == 'False':
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
                if self.tr_bot.users.get(user, 'ignore') == 'False':
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
        # Al menos, que haya 3 usuarios con puntos
        users_con_puntos = 0
        for user in puntos:
            if puntos[user] > 0:
                users_con_puntos += 1

        if users_con_puntos > 2:
            user_is_top = 0
            i = 1
            txt = "<b>Clasificación actual:</b>\n"
            for user in sorted(puntos, key=puntos.get, reverse=True):
                if user == chat_id:
                    txt = (txt + str(i) + '. ' +
                           self.tr_bot.users.get(user, 'nick') +
                           " (tú)\t" + str(puntos[user]) + "\n")
                    if i <= MAX_LINES:
                        user_is_top = True
                else:
                    txt = (txt + str(i) + '. ' +
                           self.tr_bot.users.get(user, 'nick') +
                           "\t" + str(puntos[user]) + "\n")
                i += 1

            txt_reply = ''
            i = 1
            for line in txt.splitlines():
                if i <= MAX_LINES + 1:
                    txt_reply += line + '\n'
                i += 1

            if not user_is_top:
                if self.tr_bot.users.get(chat_id, 'ignore') == 'False':
                    txt_reply = txt_reply + '---\n'
                    for line in txt.splitlines():
                        # PBL FIXME ver nick bien y el ignore
                        if self.tr_bot.users.get(chat_id, 'nick') in line:
                            txt_reply = txt_reply + line + '\n---\n'
        else:
            txt_reply = 'De momento hay pocos usuarios con puntos.\n'
        update.message.reply_text(
            txt_reply + '\n ¿Algo más?',
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup(self.kb_reto,
                                             one_time_keyboard=True))
        return self.RETO_ENTRADA

    def reto_fin(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [reto-fin]' % chat_id)
        update.message.reply_text('Ok')
        return ConversationHandler.END


class PedirConversationHandler(ConversationHandler):

    PEDIR_ENTRADA = 1
    PEDIR_CAPITULO = 2
    PEDIR_VOTADO = 3

    kb_pedir = [
        ['Pedir problema'],
        ['Ver más pedidos'],
        ['Nada']
    ]

    def __init__(self, tr_bot):
        self.tr_bot = tr_bot
        super().__init__(
            entry_points=[
                CommandHandler('pedir',
                               self.pedir,
                               pass_user_data=True)],
            states={
                self.PEDIR_ENTRADA: [
                    RegexHandler('^(Pedir problema|\
                                    Pedir otro problema)$',
                                 self.pedir_votar,
                                 pass_user_data=True),
                    RegexHandler('^Ver más pedidos$',
                                 self.pedir_stats,
                                 pass_user_data=True),
                    RegexHandler('^(Nada|No)$',
                                 self.pedir_fin,
                                 pass_user_data=True)
                ],
                self.PEDIR_CAPITULO: [
                    MessageHandler(Filters.text,
                                   self.pedir_votar,
                                   pass_user_data=True),
                ],
                self.PEDIR_VOTADO: [
                    MessageHandler(Filters.text,
                                   self.pedir_votado,
                                   pass_user_data=True),
                ],
            },
            fallbacks=[
                RegexHandler('^(Nada|No)$',
                             self.pedir_fin,
                             pass_user_data=True),
                CommandHandler('start', self.tr_bot.start)
            ]
        )

    def pedir(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [pedir]' % chat_id)

        user_data['capitulo'] = -1
        update.message.reply_text(
            'Qué quieres hacer:',
            reply_markup=ReplyKeyboardMarkup(self.kb_pedir,
                                             one_time_keyboard=True))
        return self.PEDIR_ENTRADA

    def pedir_votar(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [pedir-votar]' % chat_id)

        problemas = configparser.ConfigParser()
        problemas.read_file(
            codecs.open(self.tr_bot.file_pedir_probs, "r", "utf-8"))
        numero = update.message.text

        if (int(user_data['capitulo']) < 0):
            user_data['capitulo'] = 0
            kb_capitulo = []
            # kb_capitulo.append(problemas.sections())
            # reply_keyboard = [['1','2','3','4'],['5','6','7']]
            FILAS_DE_BOTONES = 2
            opciones = problemas.sections()
            for l_out in split_list(opciones, FILAS_DE_BOTONES):
                kb_capitulo.append(l_out)
            update.message.reply_text(
                'De qué capítulo',
                reply_markup=ReplyKeyboardMarkup(kb_capitulo,
                                                 one_time_keyboard=True))
            return self.PEDIR_CAPITULO
        else:
            prob_set = []
            user_data['capitulo'] = numero
            for problema in problemas.options(numero):
                if not eval(problemas.get(numero, problema)):
                    prob_set.append(problema)
            kb_problema = []
            FILAS_DE_BOTONES = 3
            for l_out in split_list(prob_set, FILAS_DE_BOTONES):
                kb_problema.append(l_out)
            update.message.reply_text(
                'Qué problema',
                reply_markup=ReplyKeyboardMarkup(kb_problema))
            return self.PEDIR_VOTADO

    def pedir_votado(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        numero = update.message.text
        user_data['problema'] = numero
        votado = user_data['capitulo'] + '.' + user_data['problema']
        logging.info('STATS [%s] [pedir-votado] %s' % (chat_id, votado))
        prob_votados = set(
            self.tr_bot.users.get(chat_id, 'votados').split(','))
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
            reply_markup=ReplyKeyboardMarkup(self.kb_pedir,
                                             one_time_keyboard=True))
        user_data['capitulo'] = -1
        return self.PEDIR_ENTRADA

    def pedir_stats(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [pedir-stats]' % chat_id)

        problemas = configparser.ConfigParser()
        problemas.read_file(
            codecs.open(self.tr_bot.file_pedir_probs, "r", "utf-8"))
        votos = dict()
        for capitulo in problemas.sections():
            for problema in problemas.options(capitulo):
                if not eval(problemas.get(capitulo, problema)):
                    prob = str(capitulo) + '.' + str(problema)
                    peticiones = 0

                    for user in self.tr_bot.users.sections():
                        if self.tr_bot.users.get(user, 'ignore') == 'False':
                            prob_votados = \
                                set(self.tr_bot.users.get(user, 'votados')
                                    .split(','))
                            if prob in prob_votados:
                                peticiones += 1
                    if peticiones > 0:
                        votos[prob] = peticiones
        texto = "<b>Problemas más pedidos</b>\n"
        for w in sorted(votos, key=votos.get, reverse=True):
            texto = texto + str(w) + ' ' + str(votos[w]) + '\n'
        update.message.reply_text(texto, parse_mode='HTML')
        update.message.reply_text(
            '¿Algo más?',
            reply_markup=ReplyKeyboardMarkup(self.kb_pedir,
                                             one_time_keyboard=True))
        return self.PEDIR_ENTRADA

    def pedir_fin(self, bot, update, user_data):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [pedir-fin]' % chat_id)

        update.message.reply_text('Vale!', reply_markup=ReplyKeyboardHide())
        return ConversationHandler.END


class SettingsConversationHandler(ConversationHandler):

    TIPO_SETTINGS = 1
    BORRAR_CONFIRMACION = 2

    kb_settings = [
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
        logging.info('STATS [%s] [settings]' % chat_id)
        if self.tr_bot.users.get(chat_id, 'news') == 'True':
            avisos = 'activadas'
        else:
            avisos = 'desactivadas'
        update.message.reply_text(
            'Tienes las notificaciones %s. '
            'Elige si quieres cambiar la configuración de las notificaciones, '
            'borrar toda la actividad (o nada)'
            % avisos,
            reply_markup=ReplyKeyboardMarkup(self.kb_settings,
                                             one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_borrar(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [settings-borrar]' % chat_id)
        update.message.reply_text(
            'Se va a borrar toda la actividad del usuario en el bot. '
            'Para confirmar, escriba el texto "GUARDIOLA" ',
            reply_markup=ReplyKeyboardHide())
        return self.BORRAR_CONFIRMACION

    def settings_borrado(self, bot, update):
        chat_id = str(update.message.chat_id)
        if update.message.text == 'GUARDIOLA':
            logging.info('STATS [%s] [settings-borrado-completo]' % chat_id)

            # Borrar configuración sobre los problemas propuestos
            for i in range(3):
                for j in range(10):
                    pr = 'P' + str(i) + str(j)
                    if self.tr_bot.users.has_option(chat_id, pr):
                        self.tr_bot.users.remove_option(chat_id, pr)
                        self.tr_bot.users.remove_option(chat_id, pr + 'timestamp')
            # Borrar configuración sobre los votados
            self.tr_bot.users.set(chat_id, 'votados', '')
            self.tr_bot.save_config_users()

            # Borrar todo feedback en los ficheros: FILE_NEWS_RESULTS,
            #     FILE_FREETEXT, file_opinar_votos,
            news_results_lines = \
                codecs.open(self.tr_bot.file_news_votos, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_news_votos, 'w', 'utf-8')
            for line in news_results_lines:
                if chat_id not in line:
                    f.write(line + '\n')
            f.close()
            freetext_lines = \
                codecs.open(self.tr_bot.file_opinar_texto, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_opinar_texto, 'w', 'utf-8')
            for line in freetext_lines:
                if chat_id not in line:
                    f.write(line + '\n')
            f.close()
            encuestas_lines = \
                codecs.open(self.tr_bot.file_opinar_votos, 'r', 'utf-8')\
                .read()\
                .splitlines()
            f = codecs.open(self.tr_bot.file_opinar_votos, 'w', 'utf-8')
            for line in encuestas_lines:
                if chat_id not in line:
                    f.write(line + '\n')
            f.close()
            update.message.reply_text(
                'Se ha borrado toda la actividad en el bot, '
                '¿alguna cosa más?',
                reply_markup=ReplyKeyboardMarkup(self.kb_settings,
                                                 one_time_keyboard=True))
        else:
            logging.info('STATS [%s] [settings-borrado-no]' % chat_id)
            update.message.reply_text(
                'No se ha borrado la actividad en el bot, '
                '¿alguna cosa más?',
                reply_markup=ReplyKeyboardMarkup(self.kb_settings,
                                                 one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_config(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [settings-config]' % chat_id)

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
            reply_markup=ReplyKeyboardMarkup(self.kb_settings,
                                             one_time_keyboard=True))
        return self.TIPO_SETTINGS

    def settings_done(self, bot, update):
        chat_id = str(update.message.chat_id)
        logging.info('STATS [%s] [settings-fin]' % chat_id)
        update.message.reply_text('Vale!', reply_markup=ReplyKeyboardHide())
        return ConversationHandler.END


def main():
    bot = TRBot()
    bot.run()


if __name__ == '__main__':
    main()
