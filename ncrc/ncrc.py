#!/usr/bin/env python3
import os, sys, getpass, argparse, requests, urllib, urllib3, json, re

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
        self.__channel_common = ['--channel', 'idaholab',
                                 '--channel', 'conda-forge',
                                 '--strict-channel-priority']

        ssl_verify = conda_api.run_command('config',
                                           '--get', 'ssl_verify')[0]
        self.ssl_verify = False
        if 'True' in ssl_verify:
            self.ssl_verify = not self.ssl_verify

        self.__orig = self.ssl_verify

    def getChannel(self):
        (user, password) = self.getCredentials()
        try:
            response = requests.get('https://%s/%s/index.html' % (self.__args.uri, self.__args.package), auth=(user, password), verify=False, timeout=5)
            if response.status_code == 200:
                return 'https://%s:%s@%s/%s' % (user, password, self.__args.uri, self.__args.package)
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
        ssl_value = self.__orig if ssl_value is None else ssl_value
        if ssl_value != self.ssl_verify:
            conda_api.run_command('config',
                                  '--set', 'ssl_verify', str(ssl_value))
            self.ssl_verify = not self.ssl_verify

    def install(self):
        channel = self.getChannel()
        (raw_std, raw_err, exit_code) = conda_api.run_command('info', '--json')
        info = json.loads(raw_std)
        active_env = os.path.basename(info['active_prefix'])
        print('Installing %s...' % (self.__args.application))
        if active_env == self.__args.package:
            conda_api.run_command('install',
                                  '--channel', channel,
                                  *self.__channel_common,
                                  'ncrc',
                                  self.__args.application,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)
        else:
            conda_api.run_command('create',
                                  '--name', self.__args.package,
                                  '--channel', channel,
                                  *self.__channel_common,
                                  'ncrc',
                                  self.__args.application,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)
        print('Finalizing...')
        self.cleanUp()

    def update(self):
        channel = self.getChannel()
        conda_api.run_command('update',
                              '--all',
                              '--channel', channel,
                              *self.__channel_common,
                              stdout=sys.stdout,
                              stderr=sys.stderr)
        print('Finalizing...')
        self.cleanUp()

    def search(self):
        channel = self.getChannel()
        conda_api.run_command('search',
                              '--override-channels',
                              '--channel', channel,
                              '*%s*' % (self.__args.package),
                              stdout=sys.stdout,
                              stderr=sys.stderr)
        self.cleanUp()

    def findMeta(self):
        (raw_std, raw_err, exit_code) = conda_api.run_command('info', '--json')
        conda_info = json.loads(raw_std)

        meta_files = []
        # pkgs_dir
        for pkg_dir in conda_info['pkgs_dirs']:
            meta_files.append(os.path.join(pkg_dir, 'urls.txt'))
            meta_files.append(os.path.join(pkg_dir, self.__args.package + '*', 'info', 'repodata_record.json'))

        # env_dir
        for env_dir in conda_info['envs_dirs']:
            meta_files.append(os.path.join(env_dir, self.__args.package, 'conda-meta', 'history'))
            meta_files.append(os.path.join(env_dir, 'conda-meta', 'history'))
            meta_files.append(os.path.join(os.path.sep, *env_dir.split(os.path.sep)[:-1], 'conda-meta', 'history'))
            meta_files.append(os.path.join(os.path.sep, *env_dir.split(os.path.sep)[:-1], 'conda-meta', self.__args.package + '*'))
            meta_files.append(os.path.join(env_dir, self.__args.package, 'conda-meta', self.__args.package + '*'))

        # correct for wild cards
        app_find = re.compile(self.__args.package + '.*')
        for i, meta_file in enumerate(meta_files):
            dirname = os.path.dirname(meta_file.split('*')[0])
            if '*' in meta_file and os.path.exists(dirname):
                for item in os.listdir(dirname):
                    if app_find.findall(item):
                        meta_files[i] = meta_file.replace(self.__args.package + '*', app_find.findall(item)[0])

        return meta_files

    def cleanUp(self):
        """
        Perform clean up operation;
        clear text passwords, etc
        """
        clean_conda = subprocess.Popen(['conda', 'clean', '--yes', '--all'], stdout=subprocess.DEVNULL)
        clean_conda.wait()
        meta_files = self.findMeta()
        stuff = self.getCredentials()
        for meta_file in meta_files:
            if os.path.exists(meta_file) and os.access(meta_file, os.W_OK):
                with open(meta_file, 'r+') as f:
                    raw = f.read()
                    _new = raw.replace('%s:%s@' % (self.__args.username, self.__args.password), '')
                    f.seek(0)
                    f.write(_new)
                    f.truncate()

def verifyArgs(parser):
    args = parser.parse_args()
    if not args.application:
        print('You must supply an NCRC Application to update')
        sys.exit(1)
    if len(args.application.split('=')) > 2:
        (args.package, args.version, args.build) = args.application.split('=')
    elif len(args.application.split('=')) > 1:
        (args.package, args.version) = args.application.split('=')
        args.build = None
    else:
        args.package = args.application
        args.build = None
        args.version = None
    return args

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
