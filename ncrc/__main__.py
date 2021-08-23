#!/usr/bin/env python3
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
from unittest import mock
from io import StringIO
import logging
import requests
import urllib3
logging.getLogger(requests.packages.urllib3.__package__).setLevel(logging.ERROR)

try:
    import conda.cli.python_api as conda_api
    from conda.gateways.connection.session import CondaSession
    from conda.gateways.connection import BaseAdapter
except ImportError:
    print('Unable to import Conda API. Please install conda: `conda install conda`')
    sys.exit(1)

class Client:
    def __init__(self, args):
        self.session = requests.Session()
        self.__args = args
        self.__channel_common = ['--channel', 'https://conda.software.inl.gov/public',
                                 '--channel', 'conda-forge',
                                 '--strict-channel-priority']
        if self.__args.insecure:
            self.__channel_common.append('--insecure')

    def _saveCookie(self):
        cookie_file = '%s' % (os.path.sep).join([os.path.expanduser("~"),
                                                 '.RSASecureID_login',
                                                 self.__args.fqdn])
        if not os.path.exists(os.path.dirname(cookie_file)):
            try:
                os.makedirs(os.path.dirname(cookie_file))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        with open(cookie_file, 'wb') as f:
            pickle.dump(self.session.cookies, f)

    def _getCredentials(self):
        try:
            username = input('Username: ')
            passcode = getpass.getpass('PIN+TOKEN: ')
        except KeyboardInterrupt:
            sys.exit(1)
        return (username, passcode)

    def _connectionExists(self):
        cookie = getCookie(self.__args.fqdn)
        self.session.cookies.update(cookie)
        response = self.session.get('https://%s/%s/channeldata.json' % (self.__args.fqdn,
                                                                        self.__args.package),
                                    verify=not self.__args.insecure)
        if response.status_code == 200 and 'application' in response.headers['Content-Type']:
            return True
        return False

    def _createSecureConnection(self):
        if self._connectionExists():
            return
        self.session.cookies.clear()
        try:
            response = self.session.get('https://%s/webauthentication' % (self.__args.fqdn),
                                        verify=not self.__args.insecure)
            if response.status_code != 200:
                print('ERROR connecting to %s' % (self.__args.fqdn))
                sys.exit(1)
            token = re.findall(r'name="csrftoken" value="(\w+)', response.text)
            (username, passcode) = self._getCredentials()
            response = self.session.post('https://%s/webauthentication' % (self.__args.fqdn),
                                         verify=not self.__args.insecure,
                                         data={'csrftoken' : token[0],
                                               'username'  : username,
                                               'passcode'  : passcode})
            if response.status_code != 200:
                print('ERROR authenticating to %s' % (self.__args.fqdn))
                sys.exit(1)
            elif not re.search('Authentication Succeeded', response.text):
                print('ERROR authenticating, credentials invalid.')
                sys.exit(1)
            self._saveCookie()
            return

        except requests.exceptions.ConnectTimeout:
            print('Unable to establish a connection to: https://%s' % (self.__args.fqdn))
        except (requests.exceptions.ProxyError,
                urllib3.exceptions.ProxySchemeUnknown,
                urllib3.exceptions.NewConnectionError):
            print('Proxy information incorrect: %s' % (os.getenv('https_proxy')))
        except requests.exceptions.SSLError:
            print('Unable to establish a secure connection.',
                  'If you trust this server, you can use --insecure')
        except ValueError:
            print('Unable to determine SOCKS version from https_proxy',
                  'environment variable')
        except requests.exceptions.ConnectionError:
            print('General error connecting to server: https://%s' % (self.__args.fqdn))
        sys.exit(1)

    def install(self):
        self._createSecureConnection()
        print('Installing %s...' % (self.__args.application))
        pkg_variant = list(filter(None, [self.__args.package,
                                         self.__args.version,
                                         self.__args.build]))
        name_variant = list(filter(None, [self.__args.application,
                                          self.__args.version,
                                          self.__args.build]))
        conda_api.run_command('create',
                              '--name', '_'.join(name_variant),
                              '--channel', self.__args.uri,
                              *self.__channel_common,
                              'ncrc',
                              '='.join(pkg_variant),
                              stdout=sys.stdout,
                              stderr=sys.stderr)

    def update(self):
        self._createSecureConnection()
        print('Updating %s...' % (self.__args.application))
        conda_api.run_command('update',
                              '--all',
                              '--channel', self.__args.uri,
                              *self.__channel_common,
                              stdout=sys.stdout,
                              stderr=sys.stderr)

    def search(self):
        run_command = ['search',
                       '--override-channels',
                       '--channel',
                       self.__args.uri,
                       self.__args.package]
        if self.__args.insecure:
            run_command.append('--insecure')
        try:
            conda_api.run_command(*run_command,
                                  stdout=sys.stdout,
                                  stderr=sys.stderr)
        except: # pylint: disable=bare-except
            pass

class SecureIDAdapter(BaseAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.log = logging.getLogger(__name__)

    def send(self, request, stream=None, timeout=None, verify=None, cert=None, proxies=None):
        session = requests.Session()
        request.url = request.url.replace('rsa://', 'https://')
        fqdn = urlparse(request.url).hostname
        cookie = getCookie(fqdn)
        session.cookies.update(cookie)
        response = session.get(request.url,
                               stream=stream,
                               timeout=1,
                               verify=verify,
                               cert=cert,
                               proxies=proxies)
        response.request = request
        return self.properResponse(response, request, fqdn)

    def close(self):
        pass

    def properResponse(self, response, request, fqdn):
        """ Return non exception causing response when certain conditions arise """
        # RSA sites are Text, while Conda is application/*
        if 'application' not in response.headers['Content-Type']:
            null_response = requests.Response()
            null_response.raw = StringIO()
            null_response.url = request.url
            null_response.request = request
            null_response.status_code = 204
            self.log.warning('RSA Token expired or channel does not exist')
            return null_response
        return response

class CondaSessionRSA(CondaSession):
    def __init__(self, *args, **kwargs):
        CondaSession.__init__(self, *args, **kwargs)
        self.mount("rsa://", SecureIDAdapter(*args, **kwargs))

def getCookie(fqdn):
    cookie_file = '%s' % (os.path.sep).join([os.path.expanduser("~"),
                                             '.RSASecureID_login',
                                             fqdn])
    cookie = {}
    if os.path.exists(cookie_file):
        with open(cookie_file, 'rb') as f:
            cookie.update(pickle.load(f))
    return cookie

def verifyArgs(args, parser):
    if not args.application and args.command not in ['update', 'list']:
        print('You must supply additional information when performing this action')
        sys.exit(1)
    conda_environment = os.getenv('CONDA_DEFAULT_ENV', '')
    ncrc_app = None
    if args.prefix in conda_environment:
        ncrc_app = conda_environment.split('_')[0]

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
    args.application = '%s' % (args.package.replace(args.prefix, ''))
    args.package = '%s' % (args.package.replace(args.prefix, ''))
    args.package = '%s' % (''.join(e for e in args.package if e.isalnum()))
    args.package = '%s%s' % (args.prefix, args.package.lower())
    if (args.command == 'install' and conda_environment != 'base'):
        print(' Cannot install %s while not inside the base evironment.\n' % (args.package),
              'Enter the base environment first with `conda activate base`.')
        sys.exit(1)

    if (args.command == 'update' and ncrc_app is None):
        print(' Cannot perform an update while not inside said evironment. Please\n',
              'activate the environment first and then run the command again. Use:\n',
              '\n\tconda env list\n\nTo view available environments to activate.')
        sys.exit(1)
    elif (args.command == 'update' and ncrc_app and len(conda_environment) > 1):
        print(' You installed a specific version of %s.' % (ncrc_app), 'If you wish\n',
              'to update to the lastest version, it would be best to install\n',
              'it into a new environment instead:\n\n\tconda activate base\n\tncrc install',
              '%s\n\n or activate that environment and perform the update there.' % (ncrc_app))
        sys.exit(1)

    if args.insecure:
        from urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    args.fqdn = urlparse('rsa://%s' % (args.server)).hostname
    if args.command in ['search', 'list']:
        args.uri = 'https://%s/ncrc-applications' % (args.server)
    else:
        args.uri = 'rsa://%s/%s' % (args.server, args.package)
    return args

def parseArgs(argv=None):
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
    subparser.add_parser('update', parents=[parent], help='Update application',
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
    return verifyArgs(args, parser)

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parseArgs(argv)
    with mock.patch('conda.gateways.connection.session.CondaSession',
                    return_value=CondaSessionRSA()):
        ncrc = Client(args)
        if args.command == 'install':
            ncrc.install()
        elif args.command == 'remove':
            print(' Due to the way ncrc wraps itself into conda commands, it is best to\n',
                  'remove the environment in which the application is installed. Begin\n',
                  'by deactivating the application environment and then remove it:',
                  '\n\tconda deactivate\n\tconda env remove -n %s' % (args.application))
        elif args.command == 'update':
            ncrc.update()
        elif args.command in ['search', 'list']:
            ncrc.search()

if __name__ == '__main__':
    main()
