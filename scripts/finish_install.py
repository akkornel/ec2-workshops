#!python3
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# Copyright © 2018 The Board of Trustees of the Leland Stanford Junior University.

# The contents of this file are licensed under the
# GNU General Public License, Version 3.
# In addition, documentation in this file is licensed under the
# Creative Commons Attribution-ShareAlike 3.0 Unported.
# See the files `LICENSE` and `LICENSE.cc-by-sa-3` for full license text.

# Import standard library stuff
import configparser
import getpass
import json
import pkg_resources
from os import environ
import sys
from sys import exit

# Try importing other stuff
try:
    import boto3
    from progress.spinner import Spinner
except ModuleNotFoundError as e:
    print('Failed to import module %s' % (e.name,))
    print('Run `finish_install`')
    exit()

# Let's start by making sure our environment variables are actually defined.
spinner = Spinner('Checking Environment ')

for var in (
    'AWS_CONFIG_FILE',
    'AWS_SHARED_CREDENTIALS_FILE',
    'CREATE_INSTANCES_CONFIG',
):
    if var not in environ:
        print('ERROR')
        print('The environment variable %s is not defined.' % (var,))
        print('This needs to contain the path to a .ini file.')
        print('The file does not need to exist yet, but the variable must be set.')
        exit()

    spinner.next()

print(' Complete')

# Now we can start checking out the contents of each config file.

# Start with the general config file.

print('')
print('Checking AWS configuration…')
aws_partition = None
aws_region = None

# Load the config.  If the file doesn't exist, this will fail silently.
aws_config = configparser.ConfigParser()
aws_config_fh = open(environ['AWS_CONFIG_FILE'],
    mode='a+t',
    encoding='utf-8',
)
aws_config_fh.seek(0, 0)
aws_config.read_file(
    f=aws_config_fh,
    source=environ['AWS_CONFIG_FILE']
)
if 'default' not in aws_config:
    aws_config['default'] = {}

# Read in iany values from the file
if 'workshop_partition' in aws_config['default']:
    aws_partition = aws_config['default']['workshop_partition']
if 'region' in aws_config['default']:
    aws_region = aws_config['default']['region']

# Unfortunately, boto3 doesn't give us human-readable descriptions via API.
# But, the descriptions are in a JSON file that we can parse!
# See https://github.com/boto/boto3/issues/1411
endpoints_list_file = pkg_resources.resource_filename(
    'botocore',
    'data/endpoints.json',
)
with open(endpoints_list_file, 'r') as endpoints_list_fh:
    endpoints_list = json.load(endpoints_list_fh)
partitions_list = endpoints_list['partitions']
partitions_dict = dict(
    (partition['partition'], partition) for partition in partitions_list
)

# Make sure our partition is valid
if aws_partition not in partitions_dict:
    # If the partition is bad, wipe both partition and region.
    aws_partition = None
    aws_region = None
else:
    # If the partition is good, check the region.
    if aws_region not in partitions_dict[aws_partition]['regions']:
        aws_partition = None
        aws_region = None

# If partition and region are good, ask if the user wants to change.
if aws_partition is not None and aws_region is not None:
    print('You currently have the following partition and default region:')
    print("AWS Partition: %s (%s)\nAWS Region:    %s (%s)" % (
        aws_partition,
        partitions_dict[aws_partition]['partitionName'],
        aws_region,
        partitions_dict[aws_partition]['regions'][aws_region]['description'],
    ))
    while True:
        try:
            response = input('Would you like to change this (y/n/q)? ')
        except EOFError:
            response = 'q'
        except KeyboardInterrupt:
            response = 'q'
        if response == 'q':
            print('Goodbye')
            exit()
        elif response == 'y':
            aws_partition = None
            aws_region = None
            break
        elif response == 'n':
            break
        else:
            print('Please enter y, n, or q')
    # Done getting input

# Build a list of partitions
partitions_list = ['(Quit)']
partitions_list.extend(list(partitions_dict.keys()))

# If the partition and region aren't set, get them
if aws_partition is None:
    print('You need to select an AWS partition in which to run instances.')
    print('Your partition selection will limit the AWS regions these scripts will use.')
    print('The following partitions are available:')
    for i in range(0, len(partitions_list)):
        print('%2d: %s (%s)' % (
            i,
            partitions_list[i],
            (partitions_dict[partitions_list[i]]['partitionName'] if i != 0 else 'n/a'),
        ))

# Have the user pick a partition
while aws_partition is None:
    try:
        response = input('Please choose a partition: ')
        response = int(response)
    except EOFError:
        response = 0
    except KeyboardInterrupt:
        response = 0
    except ValueError:
        print('Please enter a valid number')
        continue
    if response < 0:
        print('Please enter a non-negative number')
    elif response >= len(partitions_list):
        print('Please enter a number less than', len(partitions_list))
    elif response == 0:
        print('Goodbye')
        exit()
    else:
        print('Selected %s (%s)' % (
            partitions_list[response],
            partitions_dict[partitions_list[response]]['partitionName']
        ))
        aws_partition = partitions_list[response]
        try:
            response = input('Are you sure (y/n/q)? ')
        except EOFError:
            response = 'q'
        except KeyboardInterrupt:
            response = 'q'
        if response == 'q':
            print('Goodbye')
        elif response == 'y':
            pass
        else:
            # For all other responses, including "n", start over.
            aws_partition = None
# Done choosing the AWS partition.

# Build a list of regions
regions_list = ['(Quit)']
regions_list.extend(list(partitions_dict[aws_partition]['regions'].keys()))

# Now ask for a region
if aws_region is None:
    print('Select the closest region to your worksite.')
    print('This will not be used for instances, but will be used for misc. API calls.')
    print('The following regions are available:')
    for i in range(0, len(regions_list)):
        print('%2d: %s (%s)' % (
            i,
            regions_list[i],
            (partitions_dict[aws_partition]['regions'][regions_list[i]]['description'] if i != 0 else 'n/a'),
        ))

# Have the user pick a region
while aws_region is None:
    try:
        response = input('Please choose a region: ')
        response = int(response)
    except EOFError:
        response = 0
    except KeyboardInterrupt:
        response = 0
    except ValueError:
        print('Please enter a valid number')
        continue
    if response < 0:
        print('Please enter a non-negative number')
    elif response >= len(regions_list):
        print('Please enter a number less than', len(regions_list))
    elif response == 0:
        print('Goodbye')
        exit()
    else:
        print('Selected %s (%s)' % (
            regions_list[response],
            partitions_dict[aws_partition]['regions'][regions_list[response]]['description']
        ))
        aws_region = regions_list[response]
        try:
            response = input('Are you sure (y/n/q)? ')
        except EOFError:
            response = 'q'
        except KeyboardInterrupt:
            response = 'q'
        if response == 'q':
            print('Goodbye')
        elif response == 'y':
            pass
        else:
            # For all other responses, including "n", start over.
            aws_region = None
# Done choosing the AWS region.

# Write out any changes
aws_config['default']['workshop_partition'] = aws_partition
aws_config['default']['region'] = aws_region
aws_config_fh.seek(0, 0)
aws_config_fh.truncate(0)
aws_config.write(aws_config_fh)
aws_config_fh.close()

# Done with the config file!
del aws_partition
del aws_region
del aws_config
del aws_config_fh
del endpoints_list_file
del endpoints_list
del partitions_list
del partitions_dict
del regions_list
del response

# Check and validate AWS credentials

print('')
print('Checking AWS credentials…')
aws_access = None
aws_secret = None

# Load the config.  If the file doesn't exist, this will fail silently.
aws_creds = configparser.ConfigParser()
aws_creds_fh = open(environ['AWS_SHARED_CREDENTIALS_FILE'],
    mode='a+t',
    encoding='utf-8',
)
aws_creds_fh.seek(0, 0)
aws_creds.read_file(
    f=aws_creds_fh,
    source=environ['AWS_SHARED_CREDENTIALS_FILE']
)
if 'default' not in aws_creds:
    aws_creds['default'] = {}

# Read in any values from the file
if 'aws_access_key_id' in aws_creds['default']:
    aws_access = aws_creds['default']['aws_access_key_id']
if 'aws_secret_access_key' in aws_creds['default']:
    aws_secret = aws_creds['default']['aws_secret_access_key']

# If we don't have any secret, then wipe the access key ID
if aws_secret is None:
    aws_access is None

# If we have credentials, try them out
if aws_access is not None:
    print('The following credentials are already configured:')
    print("    AWS Access Key ID: %s\nAWS Secret Access Key: (Hidden)" % (
        aws_access,
    ))
    print('Checking credentials…')
    sys.stdout.flush()
    aws_access_session = boto3.session.Session(
        aws_access_key_id = aws_access,
        aws_secret_access_key = aws_secret,
    )
    aws_access_client = aws_access_session.client('ec2')

    # Try to get a list of instances
    try:
        aws_access_client.describe_instances()
    except Exception as e:
        print('Your credentials are not valid in your current region.')
        print('Error details: ', e)
        aws_access = None
        aws_secret = None

# Are the credentials still valid?  Give an opportunity to change.
if aws_access is not None:
    print('Your credentials are valid in your default region.')
    while True:
        try:
            response = input('Would you like to change credentials (y/n/q)? ')
        except (EOFError, KeyboardInterrupt):
            response = 'q'
        if response == 'q':
            print('Goodbye')
            exit()
        elif response == 'y':
            aws_access = None
            aws_secret = None
            break
        elif response == 'n':
            break
        else:
            print('Please enter y, n, or q')

# If we don't have any credentials, ask for some
if aws_access is None:
    print('AWS IAM User credentials are required.')
    print('We need full, read/write access to EC2.')
    print('Access is required at least for your default region.')
while aws_access is None:
    # Get credentials.  For empty input, just loop around.
    try:
        response = input(' Enter an AWS Access Key ID: ')
    except (EOFError, KeyboardInterrupt):
        print('Goodbye')
        exit()
    if response == '':
        continue
    aws_access = response

    try:
        response = getpass.getpass('Enter the Secret Access Key: ')
    except (EOFError, KeyboardInterrupt):
        print('Goodbye')
        exit()
    if response == '':
        continue
    aws_secret = response

    # We have candidate credentials; try to use them!
    print('Checking credentials…')
    sys.stdout.flush()
    aws_access_session = boto3.session.Session(
        aws_access_key_id = aws_access,
        aws_secret_access_key = aws_secret,
    )
    aws_access_client = aws_access_session.client('ec2')

    # Try to get a list of instances.  If it fails, loop around.
    try:
        aws_access_client.describe_instances()
    except Exception as e:
        print('Your credentials are not valid in your current region.')
        print('Error details: ', e)
        print('Please try again!')
        aws_access = None
        aws_secret = None
        continue

    # Confirm these are the credentials we want to use.
    print('The credentials you entered are valid!')
    print("    AWS Access Key ID: %s\nAWS Secret Access Key: (Hidden)" % (
        aws_access,
    ))
    while True:
        try:
            response = input('Use these credentials (y/n/q)? ')
        except (EOFError, KeyboardInterrupt):
            response = 'q'
        if response == 'q':
            print('Goodbye')
            exit()
        elif response == 'y':
            break
        elif response == 'n':
            aws_access = None
            aws_secret = None
            break
        else:
            print('Please enter y, n, or q')
# Done getting and validating credentials

# Write out any changes
aws_creds['default']['aws_access_key_id'] = aws_access
aws_creds['default']['aws_secret_access_key'] = aws_secret
aws_creds_fh.seek(0, 0)
aws_creds_fh.truncate(0)
aws_creds.write(aws_creds_fh)
aws_creds_fh.close()

# Done with the credentials file!
del aws_creds_fh
del aws_creds
del aws_access
del aws_secret
del aws_access_session
del aws_access_client
del response

# Check the script config file

print('')
print('Checking script configurations…')

# Load the config.  If the file doesn't exist, this will fail silently.
config = configparser.ConfigParser()
config_fh = open(environ['CREATE_INSTANCES_CONFIG'],
    mode='a+t',
    encoding='utf-8',
)
config_fh.seek(0, 0)
config.read_file(
    f=config_fh,
    source=environ['CREATE_INSTANCES_CONFIG']
)

# Go through each workshop in the config file
# We copy the list before iterating, in case we delete sections.
for workshop in list(config.sections()):
    spinner = Spinner('Checking workshop %s ' % (workshop,))

    # Check the region
    spinner.next()
    if 'region' not in config[workshop]:
        print(' Missing Setting!')
        print('The workshop "%s" does not have a region set.' % (workshop,))
        print('Older versions of this code defaulted to us-east-2, but now we don\'t.')
        print('What region should be used?  Enter an AWS region, or...')
        print('  d to delete this workshop\'s configuration')
        print('  s to continue without making an entry (dangerous!)')
        print('  q to quit')
        while 'region' not in config[workshop]:
            try:
                response = input('Make a selection: ')
            except (EOFError, KeyboardInterrupt):
                response = 'q'
            if response == 'q':
                print('Goodbye')
                exit()
            elif response == '':
                continue
            elif response in ('s', 'd'):
                break
            else:
                print('Will use region %s' % (response,))
                config[workshop]['region'] = response

        # If we got 's' or 'd', we have more work to do
        if response == 'd':
            print('Deleting configruation for workshop %s' % (workshop,))
            del config[workshop]
            continue
        if response == 's':
            print('Not setting a region.  Your default region will be used.')
    # Done with missing-region code.

    # Check the template
    spinner.next()

    # Make a small subroutine to check a region/template
    def check_template(region, template):
        boto3_client = boto3.client(
            'ec2',
            region_name = region
        )
        try:
            boto3_client.describe_launch_templates(
                LaunchTemplateIds=[template],
            )
            return True
        except Exception as e:
            return (False, e)
    # Done defining check_template

    # Check the template
    aws_region = config[workshop]['region']
    aws_template = config[workshop]['template'] if 'template' in config[workshop] else None
    if (
        ('template' not in config[workshop]) or
        (check_template(aws_region, config[workshop]['template']) is not True)
    ):
        # If we have a problem, first, print a reason
        if 'template' not in config[workshop]:
            print(' Missing Setting!')
            print('Each workshop needs an EC2 launch template, and this one was missing.')
        else:
            print(' Invalid Setting!')
            print(
                'Each workshop needs an EC2 launch template, and your template (%s) could not be validated in region %s.' %
                (config[workshop]['template'], aws_region)
            )

        # Next, find out what the user wants to do
        while True:
            print('What would you like to do?  Here are your options:')
            print('  t to enter a new EC2 Launch Template ID')
            print('  r to enter a different EC2 region')
            print('  s to continue without making a change (dangerous)')
            print('  q to quit')

            # Loop through asking for a new template
            response = None
            while response not in ('t', 'r', 's', 'q'):
                try:
                    response = input('Make a selection: ')
                except (EOFError, KeyboardInterrupt):
                    response = 'q'

            # 's' and 'q' are easy.
            if response == 'q':
                print('Goodbye')
                exit()
            elif response == 's':
                print('Skipping')
                break
            
            # For 'r', ask for a new region
            elif response == 'r':
                # Capture a region
                response = ''
                while response == '':
                    try:
                        response = input('Enter a new region: ')
                    except (EOFError, KeyboardInterrupt):
                        print('Goodbye')
                        exit()
                    if response != '':
                        aws_region = response

            # If the response is 't', or no template is set, ask for it.
            if response == 't' or aws_template is None:
                # Capture a template ID
                response = ''
                while response == '':
                    try:
                        response = input('Enter an EC2 instance template ID: ')
                    except (EOFError, KeyboardInterrupt):
                        print('Goodbye')
                        exit()
                    if response != '':
                        aws_template = response

            # Let's try the new region/template combo
            print('Checking for template %s in region %s…' % (
                aws_template,
                aws_region,
            ))
            sys.stdout.flush()
            response = check_template(aws_region, aws_template)
            if response is True:
                print('Region/Template good!')
                config[workshop]['region'] = aws_region
                config[workshop]['template'] = aws_template
                break
            else:
                print('Check failed.  Details: ', response[1])
        # End of the "template not good" loop
 
    # Done with missing-template code

    # Check the instructions
    spinner.next()
    if (
        ('instructions' not in config[workshop]) or 
        (config[workshop]['instructions'] == '')
    ):
        print(' Missing Setting!')
        print('The workshop "%s" does not have instructions.' % (workshop,))
        print('Instructions tell you how to access the instances that you created.')
        print('Would you like to enter instructions? Your choices:')
        print('  y to provide instructions.')
        print('  n to skip instructions.')
        print('  d to delete this workshop\'s configuration')
        print('  q to quit')
        while True:
            try:
                response = input('Make a selection: ')
            except (EOFError, KeyboardInterrupt):
                response = 'q'
            if response == 'q':
                print('Goodbye')
                exit()
            elif response in ('y', 'n', 'd'):
                break
            else:
                continue

        # d and n are simple
        if response == 'd':
            print('Deleting configruation for workshop %s' % (workshop,))
            del config[workshop]
            continue
        elif response == 'n':
            print('Not setting instructions.  An empty string will be stored.')
            config[workshop]['instructions'] = ''
        elif response == 'y':
            # For y, we collect multi-line input.  We end on a solitary dot, or EOF.
            responses = list()
            print('Go ahead and start entering your instructions.  Multiple lines are OK.')
            print('To end your input, type a line with a solitary dot (.) character.')
            try:
                while True:
                    response = input('> ')
                    if response == '.':
                        break
                    responses.append(response)
            except KeyboardInterrupt:
                print('Goodbye')
                exit()
            except EOFError:
                pass
            config[workshop]['instructions'] = "\n".join(responses)
            print('Instructions stored!')
    # Done with missing-instructions code

    # Check the maximum
    spinner.next()
    if 'maximum' in config[workshop]:
        try:
            int(config[workshop]['maximum'])
        except ValueError:
            del config[workshop]['maximum']
    if 'maximum' in config[workshop] and config.getint(workshop, 'maximum') <= 0:
        del config[workshop]['maximum']
    if 'maximum' not in config[workshop]:
        print(' Missing setting!')
        print('For each workshop, there needs to be a limit on how many instances can be spun up in each invocation of `create_instances`.  This is a safety check, to keep someone from accidentally creating too many instances.')
        print('If you\'re not sure what number to choose, try 25.')
        while 'maximum' not in config[workshop]:
            try:
                response = input('What limit would you like to use for "%s"? ' % (workshop,))
                int(response)
            except (EOFError, KeyboardInterrupt):
                print('Goodbye')
                exit()
            except ValueError:
                print('Please enter an integer')
                continue
            if int(response) <= 0:
                print('Please enter a positive integer')
                continue
            print('Using %d' % (int(response),))
            config[workshop]['maximum'] = response
    # Done with missing-maximum code

# Spinner needs a blank line to end
print('')

# Write out any changes.  This includes creating a blank config, if needed.
config_fh.seek(0, 0)
config_fh.truncate(0)
config.write(config_fh)
config_fh.close()

# Done with the script config
del config
del config_fh

# We're done!

print('')
print('Congratulations, we\'re done!')
print('You can now run `create_workshop` to set up a new workshop')
print('For existing workshops, you can run `create_instances`')
