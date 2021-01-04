#!/usr/bin/env python3
import os, re, sys, getpass, argparse, requests, urllib, urllib3

# Disable SSL Certificate warning (for now)
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

import logging
logging.getLogger(requests.packages.urllib3.__package__).setLevel(logging.ERROR)

try:
    import conda.cli.python_api as conda_api
except:
    print("Unable to import Conda's API.")
    sys.exit(1)

class Client:
    def __init__(self, args):
        self.__args = args

    def getChannel(self):
        (user, password) = self.getCredentials()
        try:
            response = requests.get('https://%s/%s/' % (self.__args.uri, self.__args.application), auth=(user, password), verify=False, timeout=5)
            if response.status_code == 200:
                return 'https://%s:%s@%s/%s' % (user, password, self.__args.uri, self.__args.application)
            elif response.status_code == 401:
                print("Invalid credentials, permission denied.")
            elif response.status_code == 404:
                print("Application not available.")
            else:
                print("Enable to get channel. Error: %s" % (response.status_code))
        except requests.exceptions.ConnectTimeout:
            print("Unable to establish a connection to https://%s\n\nPlease check your https_proxy environment.\nMore help can be found at: https://mooseframework.inl.gov/help/inl/hpc_remote.html" % (self.__args.uri))
        except urllib3.exceptions.ProxySchemeUnknown:
            print("Proxy information incorrect: %s" % (os.getenv("https_proxy")))
        sys.exit(1)

    def getCredentials(self):
        user = input("Username: ")
        password = getpass.getpass()
        return (user, password)

    def install(self):
        channel = self.getChannel()
        print('Installing %s, this can take a very long time. Please be patient...' % (self.__args.application))
        try:
            conda_api.run_command('create',
                                  '-n', self.__args.application,
                                  '--channel', channel,
                                  '--channel', 'idaholab',
                                  '--channel', 'conda-forge',
                                  '--strict-channel-priority',
                                  'conda',
                                  self.__args.application)
            conda_api.run_command('clean', '--all')
            print('%s installed. To use, switch to the same named environment:\n\n\tconda activate %s' % (self.__args.application, self.__args.application))

        except:
            print('There was an error installing %s' % (self.__args.application))
            sys.exit(1)

    def update(self):
        active_env = re.compile('active environment : (\w+)')
        env = active_env.findall(conda_api.run_command('info')[0])[0]
        if env != self.__args.application:
            print('You must first activate the environment you intend to update:\n\n\tconda activate %s' % (self.__args.application))
            sys.exit(1)
        try:
            channel = self.getChannel()
            conda_api.run_command('update',
                                  '--all',
                                  '--channel', channel,
                                  '--channel', 'idaholab',
                                  '--channel', 'conda-forge',
                                  '--strict-channel-priority')
            conda_api.run_command('clean', '--all')
            print('%s updated, or was already up-to-date' % (self.__args.application))

        except:
            print('There was an error updating %s' % (self.__args.application))
            sys.exit(1)

def verifyArgs(parser):
    return parser.parse_args()

def parseArgs():
    parser = argparse.ArgumentParser(description='Manage NCRC packages')
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=22, width=90)
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument('application', nargs="?", help='The application you wish to work with')
    parent.add_argument('uri', nargs="?", default='hpcsc.hpc.inl.gov/ssl/conda_packages', help='The URI containing the conda packages (default: %(default)s)')

    subparser = parser.add_subparsers(dest='command', help='Available Commands.')
    subparser.required = True

    install_parser = subparser.add_parser('install', parents=[parent], help='Install application', formatter_class=formatter)
    update_parser = subparser.add_parser('update', parents=[parent], help='Update application', formatter_class=formatter)
    return verifyArgs(parser)

if __name__ == '__main__':
    args = parseArgs()
    ncrc = Client(args)
    if args.command == 'install':
        ncrc.install()
    elif args.command == 'update':
        ncrc.update()
    sys.exit(0)
