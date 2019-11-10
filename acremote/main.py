#!/usr/bin/env python3

# Standard library imports
import json
import os
import pprint
import sys
import subprocess
import time
from functools import wraps

# 3rd party modules
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# Project modules
from acremote.thermo import W1Thermo
from acremote.vestel import VestelACRemote


class _ConfigHandler():
    def __init__(self, config_file=None):
        if config_file:
            self._CONFIG_FILE = config_file
        else:
            self._CONFIG_FILE = '/etc/acremote.json'

    def read_config(self) -> dict:
        with open(self._CONFIG_FILE, 'r') as file_handle:
            return json.load(file_handle)

    def write_config(self, config: dict):
        with open(self._CONFIG_FILE, 'w') as file_handle:
            json.dump(config, file_handle, indent='\t')
        os.chmod(self._CONFIG_FILE, 0o600)


# TODO: Add a BotCommander class to separate bot functionality from AC-specific code


class ACRemote():

    def __init__(self, bot_token: str, gpio_pin: int, state_file: str,
                 admin_ids: list, user_ids: list, easter_eggs: dict):

        self._AC_HANDLER = VestelACRemote(gpio_pin)

        self._AC_STATE_FILE = state_file

        self._AC_START_TIME = 0

        self._AC_STOP_TIME = 0

        self._AC_COOLDOWN = 20

        self._AC_TIMER = 0.0

        self._BOT_KB = {
            'admin': ReplyKeyboardMarkup(keyboard=[
                ['/shutdown', '/restart', '/cpu_temp'],
                ['/main'],
            ], resize_keyboard=True)
        }

        self._AC_KB = {
            'main': ReplyKeyboardMarkup(keyboard=[
                ['/on', '/temp_up'],
                ['/off', '/temp_down'],
                ['/speed', '/mode', '/swing'],
                ['/get_stat', '/other'],
            ], resize_keyboard=True),
            'speed': ReplyKeyboardMarkup(keyboard=[
                ['/speed_auto', '/speed_low'],
                ['/speed_mid', '/speed_high'],
                ['/strong', '/sleep'],
                ['/main'],
            ], resize_keyboard=True),
            'mode': ReplyKeyboardMarkup(keyboard=[
                ['/mode_auto', '/mode_cool'],
                ['/mode_dry', '/mode_heat'],
                ['/mode_fan'],
                ['/main'],
            ], resize_keyboard=True),
            'other': ReplyKeyboardMarkup(keyboard=[
                ['/feeling', '/fresh'],
                ['/screen', '/timer'],
                ['/health', '/fungusproof'],
                ['/admin', '/main'],
            ], resize_keyboard=True),
            'timer': ReplyKeyboardMarkup(keyboard=[
                ['/timer_set', '/timer_up'],
                ['/timer_unset', '/timer_down'],
                ['/timer_get'],
                ['/other', '/main'],
            ], resize_keyboard=True),
        }

        self._BOT = telepot.Bot(bot_token)

        self._THERMO = W1Thermo()

        self._ADMIN_IDS = admin_ids

        self._ALLOWED_IDS = self._ADMIN_IDS + user_ids

        self._RESPONSES = easter_eggs

        self._COMMANDS = {
            # ADMIN MENU
            '/adm': self.menu_admin,
            '/admin': self.menu_admin,
            # USER MENU
            '/start': self.menu_start,
            '/main': self.menu_main,
            '/mode': self.menu_mode,
            '/speed': self.menu_speed,
            '/other': self.menu_other,
            '/timer': self.menu_timer,
            # ADMIN COMMANDS
            '/shutdown': self.cmd_shutdown,
            '/restart': self.cmd_restart,
            '/cpu_temp': self.cmd_cpu_temp,
            # COMMANDS
            '/temp_up': self.cmd_temp_up,
            '/temp_down': self.cmd_temp_down,
            '/set': self.cmd_set_temp,
            '/set_temp': self.cmd_set_temp,
            # '/get': self.cmd_get_temp,
            # '/get_temp': self.cmd_get_temp,
            '/get_stat': self.cmd_get_stat,
            '/swing': self.cmd_swing,
            '/speed_auto': self.cmd_speed_auto,
            '/speed_low': self.cmd_speed_low,
            '/speed_mid': self.cmd_speed_mid,
            '/speed_high': self.cmd_speed_high,
            '/on': self.cmd_turn_on,
            '/off': self.cmd_turn_off,
            '/mode_auto': self.cmd_mode_auto,
            '/mode_cool': self.cmd_mode_cool,
            '/mode_dry': self.cmd_mode_dry,
            '/mode_heat': self.cmd_mode_heat,
            '/mode_fan': self.cmd_mode_fan,
            '/health': self.cmd_health,
            '/strong': self.cmd_strong,
            '/sleep': self.cmd_sleep,
            '/timer_up': self.cmd_timer_up,
            '/timer_down': self.cmd_timer_down,
            '/timer_get': self.cmd_timer_get,
            '/timer_set': self.cmd_timer_set,
            '/timer_unset': self.cmd_timer_unset,
            '/screen': self.cmd_screen,
            '/clean': self.cmd_clean,
            '/fresh': self.cmd_fresh,
            '/feeling': self.cmd_feeling,
            '/fungusproof': self.cmd_fungusproof,
            '/help': self.cmd_help,
            '/test': self.cmd_test,
        }

        self._ILKB_COMMANDS = {
            'confirm': self.ilkb_confirm,
        }

        self._B2S = {  # boolean to string mapping
            True: 'ON',
            False: 'OFF',
        }

        self._SENT_MSG_ID = {}  # Last sent {from_id:message_id}

        self._CONFIRM_CMDS = {}  # {from_id:{'cmd':self.cmd,args:None,kwargs:None,'confirmed':False}}

        self._DEBUG = False

        self._load_remote_state()

    #################################################
    # DECORATORS
    #################################################

    def _confirm_cmd(cmd: callable):
        @wraps(cmd)
        def wrapper(*args, **kwargs):
            self = args[0]  # is this even legal? 🤔
            chat_id = args[1]
            try:
                confirm_cmd = self._CONFIRM_CMDS[chat_id]
            except KeyError:  # if the function was not cached
                self._CONFIRM_CMDS[chat_id] = {
                    'cmd': cmd,
                    'args': args,
                    'kwargs': kwargs,
                    'confirmed': False,
                }
                return self._send_confirm(chat_id)
            if confirm_cmd['confirmed']:
                return confirm_cmd['cmd'](*args, **kwargs)
        return wrapper

    def _admin_cmd(cmd: callable):
        @wraps(cmd)
        def wrapper(*args, **kwargs):
            self = args[0]  # also this 🤔
            chat_id = args[1]
            if chat_id in self._ADMIN_IDS:  # chat_id is also user's ID
                return cmd(*args, **kwargs)
            else:
                self._BOT.sendMessage(
                    chat_id,
                    text='<code>You are not an admin</code>',
                    parse_mode='HTML',
                )
        return wrapper

    #################################################
    # INTERNAL METHODS (AC SPECIFIC)
    #################################################

    @_confirm_cmd
    def _ac_switch(self, chat_id, start=False):
        start_cd = int(time.time()) - self._AC_START_TIME
        stop_cd = int(time.time()) - self._AC_STOP_TIME
        start_done = start_cd > self._AC_COOLDOWN
        stop_done = stop_cd > self._AC_COOLDOWN * 3
        if start_done and stop_done:
            if start:
                self._AC_START_TIME = int(time.time())
                self._BOT.sendMessage(chat_id, text='Turning on the AC')
                self._AC_HANDLER.btn_on()
            else:
                self._AC_STOP_TIME = int(time.time())
                self._BOT.sendMessage(chat_id, text='Turning off the AC')
                self._AC_HANDLER.btn_off()
        elif not stop_done:
            self._BOT.sendMessage(
                chat_id,
                text='AC is shutting down, please wait {}s'.format(self._AC_COOLDOWN * 3 - stop_cd)
            )
        elif not start_done:
            self._BOT.sendMessage(
                chat_id,
                text='AC is starting, please wait {}s'.format(self._AC_COOLDOWN - start_cd)
            )

    @property
    def _room_temp(self):
        return round(list(self._THERMO.poll().values())[0], 1)

    def _timer_dial(self, up=True):
        if up and self._AC_TIMER < 24.0:
            self._AC_TIMER += self._AC_HANDLER.timer_step(self._AC_TIMER)
        elif not up and self._AC_TIMER > 0.0:
            self._AC_TIMER -= self._AC_HANDLER.timer_step(self._AC_TIMER)

    def _save_remote_state(self):  # TODO add unittests for states
        remote_state = {
            attr: getattr(self._AC_HANDLER, attr)
            for attr in dir(self._AC_HANDLER)
            if type(getattr(self._AC_HANDLER, attr)) in (bool, str, int, float)
            and not attr.startswith('_')
            and attr not in ('max_temp', 'min_temp')
        }
        with open(self._AC_STATE_FILE, 'w') as file_handle:
            json.dump(remote_state, file_handle, separators=(',', ':'))

    def _load_remote_state(self):
        if not os.path.isfile(self._AC_STATE_FILE):
            return
        with open(self._AC_STATE_FILE, 'r') as file_handle:
            remote_state = json.load(file_handle)
        for attr in remote_state:
            try:
                setattr(self._AC_HANDLER, attr, remote_state[attr])
            except AttributeError:
                pass  # skip properties without setter

    def _cmd_response(self, chat_id, setting, value):
        self._BOT.sendMessage(
            chat_id,
            text='AC {0}: <b>{1}</b>'.format(setting, value),
            parse_mode='HTML',
        )

    #################################################
    # ADMIN COMMANDS
    #################################################

    @_admin_cmd
    @_confirm_cmd
    def cmd_shutdown(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='<code>Shutting down</code>',
            parse_mode='HTML',
        )
        subprocess.run(['/sbin/init', '0'])

    @_admin_cmd
    @_confirm_cmd
    def cmd_restart(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='<code>Restarting</code>',
            parse_mode='HTML',
        )
        subprocess.run(['/sbin/init', '6'])

    @_admin_cmd
    def cmd_cpu_temp(self, chat_id):
        result = subprocess.run(
            args=['/opt/vc/bin/vcgencmd', 'measure_temp'],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        result = result.stdout.strip().split('=')[1].replace('\'', '°')
        self._BOT.sendMessage(
            chat_id,
            text='<code>CPU temperature: {}</code>'.format(result),
            parse_mode='HTML',
        )

    #################################################
    # COMMANDS
    #################################################

    def cmd_get_stat(self, chat_id):
        reply = [
            'AC Status:',
            'Power       = {}'.format(self._B2S[self._AC_HANDLER.on]),
            'Mode        = {}'.format(self._AC_HANDLER.mode),
            'Temperature = {}°C'.format(self._AC_HANDLER.temp),
            'Room        = {}°C'.format(self._room_temp),
            'Speed       = {}'.format(self._AC_HANDLER.speed),
            'Timer       = {}'.format(self._AC_HANDLER.timer),
            'Strong      = {}'.format(self._B2S[self._AC_HANDLER.strong]),
            'Swing       = {}'.format(self._B2S[self._AC_HANDLER.swing]),
            'Sleep       = {}'.format(self._B2S[self._AC_HANDLER.sleep]),
            'Fresh       = {}'.format(self._B2S[self._AC_HANDLER.fresh]),
            'Feeling     = {}'.format(self._B2S[self._AC_HANDLER.feeling]),
            'Screen      = {}'.format(self._B2S[self._AC_HANDLER.screen]),
        ]
        reply = '<code>' + '\n'.join(line for line in reply) + '</code>'
        self._BOT.sendMessage(chat_id, text=reply, parse_mode='HTML')

    def cmd_set_temp(self, chat_id, *args):
        try:
            temp = args[0]
        except IndexError:
            self._BOT.sendMessage(chat_id, text='You need to supply temperature value')
            return

        try:
            self._AC_HANDLER.btn_tmp_set(temp)
            self._AC_START_TIME = time.time()
            reply = 'AC temperature: <b>{}°C</b>'.format(temp)
        except ValueError as error:
            reply = str(error)

        self._BOT.sendMessage(
            chat_id,
            text=reply,
            parse_mode='HTML',
        )

    def cmd_temp_up(self, chat_id, *args):
        if self._AC_HANDLER.btn_tmp_up():
            reply = 'AC temperature: <b>{}°C</b>'
        else:
            reply = 'AC temperature: <b>{}°C MAX</b>'

        self._BOT.sendMessage(
            chat_id,
            text=reply.format(self._AC_HANDLER.temp),
            parse_mode='HTML',
        )

    def cmd_temp_down(self, chat_id, *args):
        if self._AC_HANDLER.btn_tmp_down():
            reply = 'AC temperature: <b>{}°C</b>'
        else:
            reply = 'AC temperature: <b>{}°C MIN</b>'

        self._BOT.sendMessage(
            chat_id,
            text=reply.format(self._AC_HANDLER.temp),
            parse_mode='HTML',
        )

    def cmd_swing(self, chat_id, *args):
        self._AC_HANDLER.btn_swing()
        self._cmd_response(chat_id, 'swing', self._B2S[self._AC_HANDLER.swing])

    def cmd_health(self, chat_id, *args):
        self._AC_HANDLER.btn_health()
        self._cmd_response(chat_id, 'health', self._B2S[self._AC_HANDLER.health])

    def cmd_strong(self, chat_id, *args):
        self._AC_HANDLER.btn_strong()
        self._cmd_response(chat_id, 'strong', self._B2S[self._AC_HANDLER.strong])

    def cmd_sleep(self, chat_id, *args):
        self._AC_HANDLER.btn_sleep()
        self._cmd_response(chat_id, 'sleep', self._B2S[self._AC_HANDLER.sleep])

    def cmd_screen(self, chat_id):
        self._AC_HANDLER.btn_screen()
        self._cmd_response(chat_id, 'screen', self._B2S[self._AC_HANDLER.screen])

    def cmd_clean(self, chat_id):
        if self._AC_HANDLER.btn_clean():
            self._BOT.sendMessage(chat_id, text='AC cleaning mode')
        else:
            self._BOT.sendMessage(chat_id, text='AC must be off')

    def cmd_fresh(self, chat_id):
        self._AC_HANDLER.btn_fresh()  # TODO: Add check like cmd_clean
        self._cmd_response(chat_id, 'fresh', self._B2S[self._AC_HANDLER.fresh])

    def cmd_feeling(self, chat_id):
        self._AC_HANDLER.btn_feeling()
        self._cmd_response(chat_id, 'feeling', self._B2S[self._AC_HANDLER.feeling])

    def cmd_speed_auto(self, chat_id):
        self._AC_HANDLER.btn_speed('AUTO')
        self._cmd_response(chat_id, 'speed', self._AC_HANDLER.mode)

    def cmd_speed_low(self, chat_id):
        self._AC_HANDLER.btn_speed('LOW')
        self._cmd_response(chat_id, 'speed', self._AC_HANDLER.mode)

    def cmd_speed_mid(self, chat_id):
        self._AC_HANDLER.btn_speed('MID')
        self._cmd_response(chat_id, 'speed', self._AC_HANDLER.mode)

    def cmd_speed_high(self, chat_id):
        self._AC_HANDLER.btn_speed('HIGH')
        self._cmd_response(chat_id, 'speed', self._AC_HANDLER.mode)

    def cmd_turn_on(self, chat_id):
        self._ac_switch(chat_id, True)

    def cmd_turn_off(self, chat_id):
        self._ac_switch(chat_id, False)

    def cmd_mode_auto(self, chat_id):
        self._AC_HANDLER.btn_mode('AUTO')
        self._cmd_response(chat_id, 'mode', self._AC_HANDLER.mode)

    def cmd_mode_cool(self, chat_id):
        self._AC_HANDLER.btn_mode('COOL')
        self._cmd_response(chat_id, 'mode', self._AC_HANDLER.mode)

    def cmd_mode_dry(self, chat_id):
        self._AC_HANDLER.btn_mode('DRY')
        self._cmd_response(chat_id, 'mode', self._AC_HANDLER.mode)

    def cmd_mode_heat(self, chat_id):
        self._AC_HANDLER.btn_mode('HEAT')
        self._cmd_response(chat_id, 'mode', self._AC_HANDLER.mode)

    def cmd_mode_fan(self, chat_id):
        self._AC_HANDLER.btn_mode('FAN')
        self._cmd_response(chat_id, 'mode', self._AC_HANDLER.mode)

    def cmd_timer_up(self, chat_id):
        self._timer_dial(True)
        self._BOT.sendMessage(
            chat_id,
            text='Timer dial: <b>{}</b> hours'.format(self._AC_TIMER),
            parse_mode='HTML',
        )

    def cmd_timer_down(self, chat_id):
        self._timer_dial(False)
        self._BOT.sendMessage(
            chat_id,
            text='Timer dial: <b>{}</b> hours'.format(self._AC_TIMER),
            parse_mode='HTML',
        )

    def cmd_timer_get(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='AC timer set to: <b>{}</b> hours'.format(self._AC_HANDLER.timer),
            parse_mode='HTML',
        )

    def cmd_timer_set(self, chat_id, *args):
        try:
            self._AC_TIMER = args[0]
        except IndexError:
            pass  # Make the argument optional

        try:
            self._AC_HANDLER.btn_timer(self._AC_TIMER)
        except ValueError as error:
            self._AC_TIMER = self._AC_HANDLER.timer
            self._BOT.sendMessage(chat_id, text=str(error))

        self.cmd_timer_get(chat_id)

    def cmd_timer_unset(self, chat_id):
        self._AC_TIMER = 0.0
        self._AC_HANDLER.btn_timer(self._AC_TIMER)
        self.cmd_timer_get(chat_id)

    def cmd_fungusproof(self, chat_id):
        if self._AC_HANDLER.on:
            self._BOT.sendMessage(chat_id, text='AC must be off')
        else:
            self._AC_HANDLER.btn_clean()
            self._BOT.sendMessage(chat_id, text='AC fungusproof mode')

    def cmd_help(self, chat_id):
        reply = 'List of available commands:\n\n'
        reply += '\n\n'.join(sorted(self._COMMANDS.keys()))
        self._BOT.sendMessage(chat_id, text=reply)

    @_confirm_cmd
    def cmd_test(self, chat_id, *args):
        self._BOT.sendMessage(chat_id, text='Passed\nArguments: {}'.format(args))

    #################################################
    # INLINE KEYBOARD COMMANDS
    #################################################

    def ilkb_confirm(self, chat_id, value):
        if int(value) == 1:
            self._CONFIRM_CMDS[chat_id]['confirmed'] = True
            cmd = self._CONFIRM_CMDS[chat_id]['cmd']
            args = self._CONFIRM_CMDS[chat_id]['args']
            kwargs = self._CONFIRM_CMDS[chat_id]['kwargs']
            cmd(*args, **kwargs)
        del self._CONFIRM_CMDS[chat_id]

    #################################################
    # ADMIN MENU
    #################################################

    @_admin_cmd
    def menu_admin(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='<code>Admin:</code>',
            parse_mode='HTML',
            reply_markup=self._BOT_KB['admin']
        )

    #################################################
    # USER MENU
    #################################################

    def menu_start(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='Rise and shine <b>Mr. Freeman</b>',
            parse_mode='HTML',
            reply_markup=self._AC_KB['main']
        )

    def menu_main(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='Main:',
            reply_markup=self._AC_KB['main']
        )

    def menu_mode(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='AC mode: <b>{}</b>'.format(self._AC_HANDLER.mode),
            parse_mode='HTML',
            reply_markup=self._AC_KB['mode']
        )

    def menu_speed(self, chat_id):
        reply = '\n'.join([
            'AC speed: <b>{}</b>'.format(self._AC_HANDLER.speed),
            'AC strong: <b>{}</b>'.format(self._B2S[self._AC_HANDLER.strong]),
            'AC sleep: <b>{}</b>'.format(self._B2S[self._AC_HANDLER.sleep]),
        ])
        self._BOT.sendMessage(
            chat_id,
            text=reply,
            parse_mode='HTML',
            reply_markup=self._AC_KB['speed']
        )

    def menu_other(self, chat_id):
        self._BOT.sendMessage(
            chat_id,
            text='Other:',
            reply_markup=self._AC_KB['other']
        )

    def menu_timer(self, chat_id):
        reply = '\n'.join([
            'AC timer: {} hours'.format(self._AC_HANDLER.timer),
            'Remote dial: {} hours'.format(self._AC_TIMER),
        ])
        self._BOT.sendMessage(
            chat_id,
            text=reply,
            reply_markup=self._AC_KB['timer']
        )

    #################################################
    # ROUTINE METHODS
    #################################################

    def _send_confirm(self, chat_id):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text='Yes', callback_data='confirm:1'),
                InlineKeyboardButton(text='No', callback_data='confirm:0'),
            ]]
        )
        sent_msg = self._BOT.sendMessage(
            chat_id,
            text='Are you sure?',
            reply_markup=keyboard
        )
        self._SENT_MSG_ID[chat_id] = telepot.message_identifier(sent_msg)

    def _unknown_cmd(self, chat_id, cmd):
        self._BOT.sendMessage(
            chat_id,
            text='Unknown command "{}".\nTry "/help" to bring the list of commands'.format(cmd)
        )

    def _log_cmd(self, msg, cmd, args):
        log = 'user_id={} is_bot={} username={} first_name={} last_name={} command={}'.format(
            msg['from'].get('id'),
            msg['from'].get('is_bot'),
            msg['from'].get('username'),
            msg['from'].get('first_name'),
            msg['from'].get('last_name'),
            cmd,
        )

        if args:
            log += ' arguments={}'.format(args)
        print(log, flush=True)

    def _process_entities(self, msg):

        try:
            msg['entities']
            text = msg['text']
            chat_id = msg['chat']['id']  # TODO change to from->id
        except KeyError:
            return

        for entity in msg['entities']:
            if entity['type'] == 'bot_command':
                offset = entity['offset']
                length = entity['length']
                endpos = offset + length
                cmd = text[offset:endpos]
                try:
                    args = text[endpos:text.index('/', endpos)].split()
                except ValueError:
                    args = text[endpos:].split()
                self._log_cmd(msg, cmd, args)
                try:
                    self._COMMANDS[cmd](chat_id, *args)
                except KeyError:
                    self._unknown_cmd(chat_id, cmd)

    def _cleanup_ilkb(self, chat_id):  # clean cached stuff related to inline keyboards
        try:
            self._BOT.deleteMessage(self._SENT_MSG_ID[chat_id])
            del self._SENT_MSG_ID[chat_id]
        except KeyError:
            return

    def _on_chat_message(self, msg):
        if msg['date'] < int(time.time()) - 30:
            return

        content_type, chat_type, chat_id = telepot.glance(msg)
        self._cleanup_ilkb(chat_id)

        if content_type != 'text' or chat_type != 'private':
            return

        if self._DEBUG:
            pprint.pprint(msg)
        text = msg['text']
        if msg['from']['id'] not in self._ALLOWED_IDS:
            self._BOT.sendMessage(
                chat_id,
                text='These aren\'t the bots you are looking for. Move along.'
            )
            for admin_id in self._ADMIN_IDS:
                self._BOT.sendMessage(admin_id, text=str(msg))  # Send info about the trespasser
            return

        if text.lower() in self._RESPONSES:
            self._BOT.sendMessage(chat_id, text=self._RESPONSES[text.lower()])

        self._process_entities(msg)
        self._save_remote_state()

    def _on_callback_query(self, msg):
        if msg['message']['date'] < int(time.time()) - 30:
            return

        query_id, from_id, callback_data = telepot.glance(msg, flavor='callback_query')
        chat_id = msg['message']['chat']['id']  # TODO: chage to ['from']['id']

        ilkb_cmd, ilkb_args = callback_data.split(':')  # ':' is the border between cmd and args
        ilkb_args = ilkb_args.split(',')                # ',' is a delimiter for args
        self._log_cmd(msg['message'], ilkb_cmd, ilkb_args)
        self._ILKB_COMMANDS[ilkb_cmd](chat_id, *ilkb_args)

        if self._DEBUG:
            pprint.pprint(msg)
            self._BOT.answerCallbackQuery(query_id, text='Passed query: ' + callback_data)

        self._cleanup_ilkb(chat_id)
        self._save_remote_state()

    #################################################
    # USER METHODS
    #################################################

    def start(self):
        router = {
            'chat': self._on_chat_message,
            'callback_query': self._on_callback_query,
        }
        try:
            MessageLoop(self._BOT, router).run_as_thread()
            while True:
                time.sleep(10)

        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == '__main__':
    if os.getuid() != 0:
        print('ACRemote must be run as root', file=sys.stderr)
        sys.exit(1)

    config_handler = _ConfigHandler()
    config = config_handler.read_config()

    server = ACRemote(
        bot_token=config['bot_token'],
        gpio_pin=config['gpio_pin'],
        state_file=config['state_file'],
        admin_ids=config['admin_ids'],
        user_ids=config['user_ids'],
        easter_eggs=config['easter_eggs']
    )
    server.start()
