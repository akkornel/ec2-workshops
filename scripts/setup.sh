# setup.sh script.

# Copyright (C) 2018 The Board of Trustees of the Leland Stanford Junior University.

# The contents of this file are licensed under the
# GNU General Public License, Version 3.
# In addition, documentation in this file is licensed under the
# Creative Commons Attribution-ShareAlike 3.0 Unported.
# See the files `LICENSE` and `LICENSE.cc-by-sa-3` for full license text.

# BASE_PATH is the path to the root of the Git checkout.
# (The default snippet placed here is from https://stackoverflow.com/q/59895)
BASE_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )/.."

# VENV_PATH is the path to where all of the Python binaries live.
# (Including module-provided binaries, like the `aws` command.)
# For containment purposes, this should be the path to a venv.
VENV_PATH=${BASE_PATH}/venv

# If you need to load any modules, or change $PATH, this is the place to do it!
module load python/3.6.1

# AWS_CONFIG_FILE points to a .ini file.  The only configuration item we use is
# 'region', which is the name of the AWS region you normally use.
# All configuration items must be in the 'default' group.
export AWS_CONFIG_FILE=${BASE_PATH}/awscli_config.ini

# AWS_SHARED_CREDENTIALS_FILE points to a .ini file which contains the AWS
# access key ID and the secret access key to use.
# All configuration items must be in the 'default' group.
export AWS_SHARED_CREDENTIALS_FILE=${BASE_PATH}/awscli_creds.ini

# CREATE_INSTANCES_CONFIG contains the list of workshops to configure.
# To start out, this can be an empty file.
export CREATE_INSTANCES_CONFIG=${BASE_PATH}/create_instances.ini
