#!/usr/bin/env python3
###############################################################################
# matrix-bot
#
# Description:    monitor a logfile and send messages to the
#                 configured chat room from Matrix [1].

# This program is a fork from [1] by Olivier van der Toorn.
#
# [1] Matrix-Python-SDK: https://github.com/matrix-org/matrix-python-sdk
# [2] https://github.com/lordievader/matrix-zabbix-bot
###############################################################################

###############################################################################
### Python modules
import argparse
import configparser
import imp
import logging
import os
import sys
from matrix_client.client import MatrixClient
import datetime
import time 
import re

###############################################################################
### Program settings
version = 0.2

###############################################################################
### Subrotines

#------------------------------------------------------------------------------
def flags():
    """Parses the arguments given.

    :return: dictionary of the arguments
    """
    parser = argparse.ArgumentParser(description='Python to Matrix bridge.')

    parser.add_argument('message', type=str, nargs='?',
                        help='the message to Matrix')
    parser.add_argument('room', type=str, nargs='?',
                        help='room to deliver message to')
    parser.add_argument('-u', '--user', type=str, dest='username',
                        help='username to use (overrides the config)')
    parser.add_argument('--port', type=str, dest='port',
                        help='server port  (overrides the config)')
    parser.add_argument('-p', '--password', type=str, dest='password',
                        help='password to use (overrides the config)')
    parser.add_argument('-c', '--config', type=str, dest='config',
                        default='testbed-bot.conf',
                        help=('specifies the config file '
                              '(defaults to /etc/matrix.conf)'))
    parser.add_argument('-t', '--type', type=str, dest='message_type',
                        help=('sets the message type'))
    parser.add_argument('-d', '--debug', action='store_const', dest='debug',
                        const=True, default=False,
                        help='enables the debug output')
    return vars(parser.parse_args())


#------------------------------------------------------------------------------
def read_config(config_file, conf_section='Matrix'):
    """Reads a matrix config file.

    :param config_file: path to the config file
    :type config_file: str
    :param conf_section: section of the config file to read
    :type conf_section: str
    :return: config dictionary
    """
    config_file = os.path.expanduser(config_file)
    if os.path.isfile(config_file) is False:
        raise FileNotFoundError('config file "{0}" not found'.format(
            config_file))

    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(config_file)
    return {key: value for key, value in config[conf_section].items()}


#------------------------------------------------------------------------------
def merge_config(args, config):
    """This function merges the args and the config together.
    The command line arguments are prioritized over the configured values.

    :param args: command line arguments
    :type args: dict
    :param config: option from the config file
    :type config: dict
    :return: dict with values merged
    """
    for key, value in args.items():
        if value is not None:
            config[key] = value

    if 'domain' not in config:
        config['domain'] = config['homeserver']

    return config


#------------------------------------------------------------------------------
def setup(config):
    """Sets up the Matrix client. Makes sure the (specified) room is joined.
    """
    loginargs = {}
    if 'token' in config:
        loginargs['user_id'] = '@{0}:{1}'.format(
            config['username'],
            config['domain'])
        loginargs['token'] = config['token']

    client = MatrixClient("https://{0}:{1}".format(
        config['homeserver'], int(config['port'])), **loginargs)

    if 'token' not in config:
        token = client.login_with_password(
            username=config['username'], password=config['password'])
        logging.info("Authenticated, received token: \"%s\"", token)

    room = client.join_room('{0}:{1}'.format(
        config['room'], config['domain']))
    return client, room


#------------------------------------------------------------------------------
def send_message(config, room):
    """Sends a message into the room. The config dictionary hold the message.

    :param config: config dictionary
    :type config: dictionary
    :param room: reference to the Matrix room
    :type room: MatrixClient.room
    """
    message = config['message']
    time = datetime.datetime.now().isoformat().split(".",-1)[0]
    formatted_message = '<font color=\"#c4c4c4\">{}</font> {}'.format(time,message)
    logging.debug('sending message:\n%s', formatted_message)
    room.send_html(formatted_message, msgtype=config['message_type'])


#------------------------------------------------------------------------------
def set_log_level(level=None):
    """Sets the log level of the notebook. Per default this is 'INFO' but
    can be changed.

    :param level: level to be passed to logging (defaults to 'INFO')
    :type level: str
    """
    imp.reload(logging)
    logging.basicConfig(format='%(asctime)s: %(levelname)8s - %(message)s',
                        level=level)

###############################################################################
### Main Process

##BEGIN

if __name__ == '__main__':

    args = flags()
    if args['debug'] is True:
        set_log_level('DEBUG')
        print (args)
    else:
        set_log_level()

    # read configuration file
    try:
        config = merge_config(args, read_config(args['config']))
        config['logfile'] = config['logfile'].replace("\"","")
        logging.debug('config: %s', config)

    except FileNotFoundError:
        config = args
        if None in [config['username'], config['password'], config['room']]:
            raise

    # check file to 'tail'
    if not (os.path.exists(config['logfile'])):
        print ("File {} cannot be found!".format(config['logfile']))

    f = open(config['logfile'],'r')
    if not f:
        print ("File {} cannot be read!".format(config['logfile']))

    # tail process
    while True:
       line = f.readline()
       if not line:
           time.sleep(10)
       else:
           logging.debug('msg: %s', line.rstrip())
           config['message'] = line.rstrip()

       # ignore msgs that match to regex
       if re.search(r'.*requesting.*', line):
           continue
       else:
           client, room = setup(config)
           send_message(config, room)
           client.logout()
##END
