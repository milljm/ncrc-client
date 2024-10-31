# NCRC-client
NCRC-client

This is a simple wrapper script that will be used to enable the use of a two-factor authentication
mechanism for downloading NCRC controlled codes through the popular "Conda" distribution mechanism.


### Other Software
Idaho National Laboratory is a cutting edge research facility which is constantly producing high
quality research and software. Feel free to take a look at our other software and scientific
offerings at:

[Primary Technology Offerings Page](https://www.inl.gov/inl-initiatives/technology-deployment)

[Supported Open Source Software](https://github.com/idaholab)

[Raw Experiment Open Source Software](https://github.com/IdahoLabResearch)

[Unsupported Open Source Software](https://github.com/IdahoLabCuttingBoard)

### License

Copyright 2021 Battelle Energy Alliance, LLC

Licensed under the BSD 3-clause (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  https://opensource.org/licenses/BSD-3-Clause - LINK TO OSI FOR LICENSE 3-Clause BSD

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.


Licensing
-----
This software is licensed under the terms you may find in the file named "LICENSE" in this
directory.


Developers
-----
By contributing to this software project, you are agreeing to the following terms and conditions for
your contributions:

You agree your contributions are submitted under the BSD 3-Clause license. You represent you are
authorized to make the contributions and grant the license. If your employer has rights to
intellectual property that includes your contributions, you represent that you have received
permission to make contributions and grant the required license on behalf of that employer.


# NCRC Client

The NCRC client allows users to search, and install Conda packages contained behind an RSA protected
server. Technically, on the server-side, the packages produced for use by this tool must establish a
certain prefix ('ncrc-' in this case). The end-user however need not worry about any prefix
semantics. The NCRC client will handle whether or not users supply or not supply a prefix.

## Install NCRC

The NCRC client is available via INL's public Conda channel repository or from the Anaconda Idaholab
channel.

INL Conda Repository:
```bash
$> conda install ncrc --channel https://conda.software.inl.gov/public
```

## Install an NCRC Application

```bash
$> ncrc install bison
Username: johndoe
PIN+TOKEN:
Solving requirements for bison...
```

Once finished, follow the on-screen instructions:
```bash
$> conda activate bison
$> bison-opt --version
<version is displayed>
```
> [!NOTE]
> The first time you run the application after installation, the application may appear to hang.
> Consecutive runs will not be hindered.

### NCRC Syntax

```pre
usage: ncrc [-h] {install,remove,search,list} ...

Manage NCRC packages

positional arguments:
  {install,remove,search,list}
                        Available Commands.
    install             Install application
    remove              Prints information on how to remove application
    search              Perform a regular expression search for an NCRC
                        application
    list                List all available NCRC applications

optional arguments:
  -h, --help            show this help message and exit
```

### NCRC Usage Examples

```bash
$> ncrc list
# Use 'ncrc search name-of-application' to list more detail
# NCRC applications available:

	sockeye
	direwolf
	griffin
	pronghorn
	relap7
	bison
	bluecrab
	marmot
	sabertooth
```
List all available NCRC applications

```bash
$> ncrc search griffin
Loading channels: done
# Name                       Version           Build  Channel
ncrc-griffin              2021_07_29         build_0  ncrc-applications
```
Lists all available versions of griffin

```bash
$> ncrc install bison=2021_07_28
Username: johndoe
PIN+TOKEN:
Installing bison=2021_07_28...

# after installation completes
$> conda activate bison
$> bison-opt --version
<the version is displayed>
```
Install a specific version.

```bash
$> ncrc remove bison
 Due to the way ncrc wraps itself into conda commands, it is best to
 remove the environment in which the application is installed. Begin
 by deactivating the application environment and then remove it:
	conda deactivate
	conda env remove -n bison
```

The NCRC script being a wrapper tool, is unable to perform such a function. The user must deactivate
the environment and remove that environment using the appropraite conda commands.
