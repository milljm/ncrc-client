#!/usr/bin/env python3
import os, sys, getpass, argparse, requests, urllib, urllib3, json

# Disable SSL Certificate warning (for now)
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

import logging
logging.getLogger(requests.packages.urllib3.__package__).setLevel(logging.ERROR)

try:
    import conda.cli.python_api as conda_api
except:
    print('Unable to import Conda API. Please install conda: `conda install conda`')
    sys.exit(1)

class Client:
    def __init__(self, args):
        self.__args = args

    def getChannel(self):
        (user, password) = self.getCredentials()
        try:
            response = requests.get('https://%s/%s/index.html' % (self.__args.uri, self.__args.application), auth=(user, password), verify=False, timeout=5)
            if response.status_code == 200:
                return 'https://%s:%s@%s/%s' % (user, password, self.__args.uri, self.__args.application)
            elif response.status_code == 401:
                print('Invalid credentials, permission denied.')
            elif response.status_code == 404:
                print('Application not available.')
            else:
                print('Enable to get channel. Error: %s' % (response.status_code))
        except requests.exceptions.ConnectTimeout:
            print('Unable to establish a connection to https://%s\n\nPlease check your https_proxy environment.\nMore help can be found at: https://mooseframework.inl.gov/help/inl/hpc_remote.html' % (self.__args.uri))
        except urllib3.exceptions.ProxySchemeUnknown:
            print('Proxy information incorrect: %s' % (os.getenv('https_proxy')))
        except urllib3.exceptions.NewConnectionError:
            print('Connection refused, please try again.')

        sys.exit(1)

    def getCredentials(self):
        try:
            if not self.__args.username:
                self.__args.username = input("Username: ")
            if not self.__args.password:
                self.__args.password = getpass.getpass()
        except KeyboardInterrupt:
            sys.exit(1)
        return (self.__args.username, self.__args.password)

    def install(self):
        channel = self.getChannel()
        print('Installing %s...' % (self.__args.application))
        try:
            (raw_std, raw_err, exit_code) = conda_api.run_command('search',
                                                                  self.__args.application,
                                                                  '--channel', channel,
                                                                  '--info',
                                                                  '--json')
            package_info = json.loads(raw_std)

            (raw_std, raw_err, exit_code) = conda_api.run_command('info',
                                                                  '--json')
            conda_info = json.loads(raw_std)

            file_name = '-'.join([self.__args.application,
                                  package_info[self.__args.application][0]['version'],
                                  package_info[self.__args.application][0]['build']])

            meta_files = [ os.path.sep.join([env_dir,
                                             self.__args.application,
                                             'conda-meta',
                                             '%s.json' % (file_name)]) for env_dir in conda_info['envs_dirs'] ]

            conda_api.run_command('create',
                                  '--name', self.__args.application,
                                  '--channel', channel,
                                  '--channel', 'idaholab',
                                  '--channel', 'conda-forge',
                                  '--strict-channel-priority',
                                  'ncrc',
                                  self.__args.application,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)

            conda_api.run_command('clean', '--all')

            # remove clear text password from meta file to protect the user.
            # This password is not visible using any conda commands. But it
            # is written inside this meta file in clear text on the system,
            # and no one wants that.
            for meta_file in meta_files:
                if os.path.exists(meta_file):
                    with open(meta_file, 'r+') as f:
                        meta_json = json.load(f)
                        meta_json['url'] = "https://%s/%s" % (self.__args.uri, self.__args.application)
                        f.seek(0)
                        json.dump(meta_json, f)
                        f.truncate()

        except Exception:
            sys.exit(1)

    def update(self):
        try:
            channel = self.getChannel()
            conda_api.run_command('update',
                                  '--all',
                                  '--channel', channel,
                                  '--channel', 'idaholab',
                                  '--channel', 'conda-forge',
                                  '--strict-channel-priority',
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)
            conda_api.run_command('clean', '--all')

        except Exception:
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
    install_parser.add_argument('-u', '--username', help='Supply username instead of being challenged for one')
    install_parser.add_argument('-p', '--password', help='Supply password instead of being challenged for one')

    update_parser = subparser.add_parser('update', parents=[parent], help='Update application', formatter_class=formatter)
    update_parser.add_argument('-u', '--username', help='Supply username instead of being challenged for one')
    update_parser.add_argument('-p', '--password', help='Supply password instead of being challenged for one')

    return verifyArgs(parser)

if __name__ == '__main__':
    args = parseArgs()
    ncrc = Client(args)
    if args.command == 'install':
        ncrc.install()
    elif args.command == 'update':
        ncrc.update()
    sys.exit(0)
