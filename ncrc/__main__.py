#!/usr/bin/env python3
""" Allow connections to RSA protected Conda Channels """
#BSD 3-clause license
#  Copyright (c) 2015-2021, conda-forge contributors
#  All rights reserved.
#
#  Redistribution and use in source and binary forms,
#  with or without modification, are permitted
#  provided that the following conditions are met:
#
#  1. Redistributions of source code must retain the
#      above copyright notice, this list of conditions
#      and the following disclaimer.
#
#  2. Redistributions in binary form must reproduce
#     the above copyright notice, this list of
#     conditions and the following disclaimer in the
#     documentation and/or other materials provided
#     with the distribution.
#
#  3. Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse
#     or promote products derived from this software
#     without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
#  WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
#  EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
#  NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
#  IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#  ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import sys
import getpass
import argparse
import re
import pickle
import errno
from urllib.parse import urlparse
import logging
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

#pylint: disable=no-member
logging.getLogger(requests.packages.urllib3.__package__).setLevel(logging.ERROR)

try:
    import conda # Determin version
    import conda.cli.python_api as conda_api
    from conda.api import Solver
except ImportError:
    print('Unable to import Conda API. Please install conda: `conda install conda`')
    sys.exit(1)

class RSAPackage:
    """ Class to handle obtaining the NCRC Tarball behind an RSA protected server """
    def __init__(self):
        self.session = requests.Session()

    @staticmethod
    def __get_credentials():
        """ Get credentials from command line user input """
        try:
            username = input('Username: ')
            passcode = getpass.getpass('PIN+TOKEN: ')
        except KeyboardInterrupt:
            sys.exit(1)
        return (username, passcode)

    def __connection_exists(self):
        """ Check if connection exists, and if we can use existing cookie """
        cookie = self.__get_cookie()
        self.session.cookies.update(cookie)
        response = self.session.get((f'{self.__url}'
                                      'channeldata.json'), verify=self.__ssl_verify)
        if response.status_code == 200 and 'application' in response.headers['Content-Type']:
            return True
        return False

    def __get_cookie(self):
        """ return the cookie, if it exists """
        cookie_file = (os.path.sep).join([os.path.expanduser('~'),
                                        '.RSASecureID_login',
                                        self.__fqdn])
        cookie = {}
        if os.path.exists(cookie_file):
            with open(cookie_file, 'rb') as file_o:
                cookie.update(pickle.load(file_o))
        return cookie

    def __save_cookie(self):
        """ Save the request object's cookie for additional connections """
        cookie_file = os.path.sep.join([os.path.expanduser("~"),
                                        ".RSASecureID_login",
                                        self.__fqdn])

        if not os.path.exists(os.path.dirname(cookie_file)):
            try:
                os.makedirs(os.path.dirname(cookie_file))
            except OSError as error_o:
                if error_o.errno != errno.EEXIST:
                    raise
        with open(cookie_file, 'wb') as file_o:
            pickle.dump(self.session.cookies, file_o)

    def __create_connection(self):
        """ Create connection using requests """
        if self.__connection_exists():
            return True
        self.session.cookies.clear()
        try:
            response = self.session.get(f'https://{self.__fqdn}/webauthentication',
                                        verify=self.__ssl_verify)
            if response.status_code != 200:
                print(f'ERROR connecting to {self.__fqdn}')
                sys.exit(1)
            token = re.findall(r'name="csrftoken" value="(\w+)', response.text)
            (username, passcode) = self.__get_credentials()
            response = self.session.post(f'https://{self.__fqdn}/webauthentication',
                                         verify=self.__ssl_verify,
                                         data={'csrftoken' : token[0],
                                               'username'  : username,
                                               'passcode'  : passcode})
            if response.status_code != 200:
                print(f'ERROR authenticating to {self.__fqdn}')
                sys.exit(1)
            elif not re.search('Authentication Succeeded', response.text):
                print('ERROR authenticating, credentials invalid.')
                sys.exit(1)
            self.__save_cookie()
            return True

        except requests.exceptions.ConnectTimeout:
            print(f'Unable to establish a connection to: https://{self.__fqdn}')
        except (requests.exceptions.ProxyError,
                urllib3.exceptions.ProxySchemeUnknown,
                urllib3.exceptions.NewConnectionError):
            print(f'Proxy information incorrect: {os.getenv("https_proxy")}')
        except requests.exceptions.SSLError:
            print('Unable to establish a secure connection.',
                  'If you trust this server, you can use --insecure')
        except ValueError:
            print('Unable to determine SOCKS version from https_proxy',
                  'environment variable')
        except requests.exceptions.ConnectionError:
            print(f'General error connecting to server: https://{self.__fqdn}')
        sys.exit(1)

    def get(self, url, ssl_verify=True):
        """ Download package from url and return the contents of downloaded file """
        self.__url = url
        self.__fqdn = urlparse(url).hostname
        self.__package = os.path.basename(url)
        self.__ssl_verify = ssl_verify
        if self.__create_connection():
            try:
                print(f'Downloading {self.__url}...')
                with self.session.get(url, verify=self.__ssl_verify) as pkg_stream:
                    if pkg_stream.status_code == 200:
                        return pkg_stream.content
                    else:
                        print('An error was encountered while downloading package:'
                              f'HTTP: {pkg_stream.status_code}:\n{pkg_stream.text}')
                        sys.exit(1)
            except KeyboardInterrupt:
                print('Exiting...')
                sys.exit(1)

class CondaNCRC:
    """ Class responsible for interfacing with Conda API to install packages """
    def __init__(self, args):
        self.ncrc_package = RSAPackage()
        self.__args = args
        self.__required_version = ['23', '11', '0']
        self.__channel_common = [f'https://{self.__args.server}/public',
                                 'conda-forge']

    def solve_request(self, package, version, build):
        """ Return URI from Conda solver """
        print('Trying to figure out what to download. Sometimes this can take a while...')
        specs = [package]
        for x in [version, build]:
            if x:
                specs.append(f'{x}')

        solver = Solver(prefix='', channels=[f'https://{self.__args.server}/ncrc-applications',
                                             *self.__channel_common],
                                             specs_to_add=['='.join(specs)])
        return solver.solve_final_state()

    def check_condaversion(self):
        """ Verify we are using an up to date Conda """
        for k_iter, value in enumerate(conda.__version__.split(".")):
            if int(value) < int(self.__required_version[k_iter]):
                print((f'\nConda out of date:\t{conda.__version__}\n'
                       f'Required version:\t{".".join(self.__required_version)}\n'
                        'Please update Conda:\n\n\t`conda update conda`\n'))
                sys.exit(1)
            elif int(value) > int(self.__required_version[k_iter]):
                return

    def install_package(self):
        """ Install package using Conda API """
        self.check_condaversion()
        package_meta = self.solve_request(self.__args.package,
                                          self.__args.version,
                                          self.__args.build)
        try:
            url = package_meta[-1].url.replace('ncrc-applications', self.__args.package)
        except KeyError:
            print('ERROR parsing solve data')
            sys.exit(1)

        package_content = self.ncrc_package.get(url)

        print(f'Installing {os.path.basename(url)}...')
        sys.exit()
        pkg_variant = list(filter(None, [self.__args.package,
                                         self.__args.version,
                                         self.__args.build]))
        name_variant = list(filter(None, [self.__args.application,
                                          self.__args.version,
                                          self.__args.build]))
        conda_api.run_command('create',
                              '--name', '_'.join(name_variant),
                              '--channel', self.__args.uri,
                              *[f'--channel {x}' for x in self.__channel_common],
                              'ncrc',
                              '='.join(pkg_variant),
                              f'{"" if self.__args.insecure else "--insecure"}',
                              stdout=sys.stdout,
                              stderr=sys.stderr)

    def search_package(self):
        """ Search for package, and report a formatted list """
        run_command = ['search',
                       '--override-channels',
                       '--channel',
                       self.__args.uri,
                       self.__args.package]
        if self.__args.insecure:
            run_command.append('--insecure')
        try:
            if self.__args.command == 'list':
                std_out = conda_api.run_command(*run_command,
                                                stderr=sys.stderr)
                app_list = ['\t' + x.split()[0].replace('ncrc-', '')
                            for x in std_out[0].split('\n')[3:-1:]]
                unique_apps = '\n'.join(set(app_list))
                print('# Use \'ncrc search name-of-application\' to list more detail\n# NCRC',
                      f'applications available:\n\n{unique_apps}')
            else:
                conda_api.run_command(*run_command,
                                      stdout=sys.stdout,
                                      stderr=sys.stderr)
        except: # pylint: disable=bare-except
            pass

# Parsing arguments always requires lots of branches
#pylint: disable=too-many-branches
def verify_args(args):
    """ Verify arguments supplied to ncrc """
    if not args.application and args.command not in ['update', 'list']:
        print('You must supply additional information when performing this action')
        sys.exit(1)
    conda_environment = os.getenv('CONDA_DEFAULT_ENV', '')
    ncrc_app = None
    if args.prefix in conda_environment:
        ncrc_app = conda_environment.split('_')[0]
    elif os.getenv('NCRC_APP', ''):
        ncrc_app = os.getenv('NCRC_APP', '').lower()

    if len(args.application.split('=')) > 2:
        (args.package, args.version, args.build) = args.application.split('=')
    elif len(args.application.split('=')) > 1:
        (args.package, args.version) = args.application.split('=')
        args.build = None
    else:
        args.package = args.application
        args.build = None
        args.version = None

    if ncrc_app and args.package == '':
        args.package = ncrc_app

    # format package name (strip special characters, make lower case, prefix/brand it)
    args.application = args.package.replace(args.prefix, '')
    args.package = args.package.replace(args.prefix, '')
    args.package = ''.join(e for e in args.package if e.isalnum())
    args.package = f'{args.prefix}{args.package.lower()}'
    if (args.command == 'install' and conda_environment != 'base'):
        print(f' Cannot install {args.package} while not inside the base evironment.',
              '\nEnter the base environment first with `conda activate base`.')
        sys.exit(1)

    if (args.command == 'update' and ncrc_app is None):
        print(' Cannot perform an update while not inside said evironment. Please\n',
              'activate the environment first and then run the command again. Use:\n',
              '\n\tconda env list\n\nTo view available environments to activate.')
        sys.exit(1)
    elif (args.command == 'update' and ncrc_app and len(conda_environment.split('_')) > 1):
        print(f' You installed a specific version of {ncrc_app}. If you wish\n',
              'to update to the lastest version, it would be best to install\n',
              'it into a new environment instead:\n\n\tconda activate base\n\tncrc install',
              f'{ncrc_app}\n\n or activate that environment and perform the update there.')
        sys.exit(1)

    if args.insecure:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    args.fqdn = urlparse(f'https://{args.server}').hostname
    if args.command in ['search', 'list']:
        args.uri = f'https://{args.server}/ncrc-applications'
    else:
        args.uri = f'https://{args.server}/{args.package}'
    return args

def parse_args(argv=None):
    """ Parse arguments with argparser """
    parser = argparse.ArgumentParser(description='Manage NCRC packages')
    formatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=22, width=90)
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument('application', nargs="?", default='',
                        help='The application you wish to work with')
    parent.add_argument('server', nargs="?", default='conda.software.inl.gov',
                        help='The server containing the conda packages (default: %(default)s)')
    parent.add_argument('-k', '--insecure', action="store_true", default=False,
                        help=('Allow untrusted connections'))
    subparser = parser.add_subparsers(dest='command', help='Available Commands.')
    subparser.required = True
    subparser.add_parser('install', parents=[parent], help='Install application',
                         formatter_class=formatter)
    subparser.add_parser('remove', parents=[parent],
                         help=('Prints information on how to remove application'),
                         formatter_class=formatter)
    subparser.add_parser('search', parents=[parent],
                         help=('Perform a regular expression search for NCRC application'),
                         formatter_class=formatter)
    subparser.add_parser('list', parents=[parent],
                         help=('List all available NCRC applications'),
                         formatter_class=formatter)
    args = parser.parse_args(argv)

    # Set the prefix for all apps. Perhaps someday this will be made into an argument (support
    # different application branding)
    args.prefix = 'ncrc-'
    return verify_args(args)

def main(argv=None):
    """ entry point to NCRC client """
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    ncrc = CondaNCRC(args)
    if args.command == 'install':
        ncrc.install_package()
    elif args.command == 'remove':
        print(' Due to the way ncrc wraps itself into conda commands, it is best to\n',
                'remove the environment in which the application is installed. Begin\n',
                'by deactivating the application environment and then remove it:',
                f'\n\tconda deactivate\n\tconda env remove -n {args.application}')
    elif args.command in ['search', 'list']:
        ncrc.search_package()

if __name__ == '__main__':
    main()
