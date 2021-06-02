# NCRC Client

ncrc authenticates a user to an RSA SecurID protected resource, and saves the cookie session for later use.


## Install

For now, ncrc is available via the Idaholab Conda channel:

```bash
conda config --add channels idaholab
conda install ncrc
```

## Use

To use ncrc:

```bash
ncrc search mastodon

```
Lists all available versions of mastodon

```bash
ncrc install mastodon
ncrc install mastodon=2021.01.01
ncrc install mastodon=2021.01.01=build_3
```
Install the latest version of mastodon, or a specific version, or a specific version at a specific build.

```bash
ncrc update mastodon
```
Update mastodon (and everything else that may require an update)
