#!/usr/bin/env python3
import os, sys, getpass, argparse, requests, urllib, urllib3, json

# Sigh. Conda API is broken (clean does not work)
import subprocess

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
        ssl_verify = conda_api.run_command('config',
                                           '--get', 'ssl_verify')[0]
        self.ssl_verify = False
        if 'True' in ssl_verify:
            self.ssl_verify = not self.ssl_verify

        self.__orig = self.ssl_verify

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

    def toggleSSL(self, ssl_value=None):
        if ssl_value is None:
            ssl_value = self.__orig

        if ssl_value != self.ssl_verify:
            conda_api.run_command('config',
                                  '--set', 'ssl_verify', str(ssl_value))
            self.ssl_verify = not self.ssl_verify

    def install(self):
        channel = self.getChannel()
        print('Installing %s...' % (self.__args.application))
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
        print('Finalizing...')
        self.cleanUp(channel)

    def update(self):
        channel = self.getChannel()
        conda_api.run_command('update',
                              '--all',
                              '--channel', channel,
                              '--channel', 'idaholab',
                              '--channel', 'conda-forge',
                              '--strict-channel-priority',
                              stdout=sys.stdout,
                              stderr=sys.stderr)
        print('Finalizing...')
        self.cleanUp(channel)

    def search(self):
        channel = self.getChannel()
        conda_api.run_command('search',
                              '--override-channels',
                              '--channel', channel,
                              '*%s*' % (self.__args.application),
                              stdout=sys.stdout,
                              stderr=sys.stderr)

    def findMeta(self, channel):
        (raw_std, raw_err, exit_code) = conda_api.run_command('search',
                                                              self.__args.application,
                                                              '--channel', channel,
                                                              '--override-channels',
                                                              '--info',
                                                              '--json')
        package_info = json.loads(raw_std)
        (raw_std, raw_err, exit_code) = conda_api.run_command('info', '--json')
        conda_info = json.loads(raw_std)
        file_names = []
        for version in package_info[self.__args.application]:
            file_names.append('-'.join([self.__args.application,
                                        version['version'],
                                        version['build']]))
        meta_files = []
        for file_name in file_names:
            for env_dir in conda_info['envs_dirs']:
                meta_files.append(os.path.sep.join([env_dir,
                                                    self.__args.application,
                                                    'conda-meta',
                                                    '%s.json' % (file_name)]))
        return meta_files

    def cleanUp(self, channel):
        """
        Perform clean up operation; remove protected tarball(s),
        clear text passwords, etc
        """
        # Conda clean API does not work
        # conda_api.run_command('clean', '--all')
        clean_conda = subprocess.Popen(['conda', 'clean', '--yes', '--all'], stdout=subprocess.DEVNULL)
        clean_conda.wait()

        # Remove clear text password from meta file to protect the user.
        meta_files = self.findMeta(channel)
        for meta_file in meta_files:
            if os.path.exists(meta_file):
                with open(meta_file, 'r+') as f:
                    meta_json = json.load(f)
                    meta_json['url'] = "https://%s/%s" % (self.__args.uri, self.__args.application)
                    f.seek(0)
                    json.dump(meta_json, f)
                    f.truncate()

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

    search_parser = subparser.add_parser('search', parents=[parent], help='Search for application', formatter_class=formatter)
    search_parser.add_argument('-u', '--username', help='Supply username instead of being challenged for one')
    search_parser.add_argument('-p', '--password', help='Supply password instead of being challenged for one')

    return verifyArgs(parser)

if __name__ == '__main__':
    args = parseArgs()
    ncrc = Client(args)
    ncrc.toggleSSL(False)
    if args.command == 'install':
        ncrc.install()
    elif args.command == 'update':
        ncrc.update()
    elif args.command == 'search':
        ncrc.search()
    ncrc.toggleSSL()
    sys.exit(0)
