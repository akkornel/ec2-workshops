#!python3
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# First, import modules from the standard library
import configparser
import datetime
import dateutil.tz
import ipaddress
import os
from os import environ
import sys
from sys import exit
import time

# Try importing other stuff
try:
    import boto3
    from progress.bar import Bar
    from progress.spinner import Spinner
    from termcolor import colored
except ModuleNotFoundError as e:
    print('Failed to import module %s' % (e.name,))
    print('Run `finish_install`')
    exit()

print('Welcome to Instance L̶a̶u̶n̶c̶h̶e̶r̶ Destroyer')

# Worker timeout is in seconds
worker_timeout = 600

# Look for our config file
spinner = Spinner('Checking Configuration ')
for var in (
    'AWS_CONFIG_FILE',
    'AWS_SHARED_CREDENTIALS_FILE',
    'CREATE_INSTANCES_CONFIG',
):
    spinner.next()
    if var not in environ:
        print('Environment variable %s is missing.  Re-run `finish_install`.' % (
            var,
        ))
        exit()
    if not os.path.isfile(environ[var]):
        print('The %s file appears to be missing.  Re-run `finish_install`.' % (
            var,
        ))
        exit()

# Try loading our config
spinner.next()
config = configparser.ConfigParser()
try:
    config.read(environ['CREATE_INSTANCES_CONFIG'])
    spinner.next()
except Exception as e:
    print('ERROR')
    print('The instance configuration file could not be read.')
    print('Here is the error: ', e)
    print('Re-run `finish_install`')
    exit()
print(' Complete')

# Check for connectivity and permissions
spinner = Spinner('Talking to AWS ')

# Our EC2 client uses the default region for this check.
try:
    ec2_client = boto3.client('ec2')
    ec2_client.describe_instances(MaxResults=5)
    spinner.next()
except Exception as e:
    print('ERROR!')
    print('We were unable to get a list of running EC2 instances.')
    print('The exact error we got:', e)
    print('Re-run `finish_install`')
    exit()
print(' Complete')

# Prepare to build an indexed list of configs
config_names_as_list = list()
config_names_as_list.append('(Quit)')
spinner = Spinner('Checking %s workshop(s) ' % (
    len(config.sections()),
))

# Build our list of usable workshops
for workshop in config.sections():
    # Make sure the required keys are in each workshop.
    for var in (
        'template',
        'region',
        'instructions',
        'maximum',
    ):
        # Skip if we're missing a var
        if var not in config[workshop]:
            print(' WARNING')
            print('Workshop "%s" missing config item \'%s\'.' % (
                workshop,
                var
            ))
            print('Skipping this entry for now.  Re-run `finish_install` to fix.')
            next

        # For maximum, do number tests
        if var == 'maximum':
            try:
                config[workshop].getint('maximum')
            except ValueError:
                config[workshop]['maximum'] = -1
            if config[workshop].getint('maximum') <= 0:
                print(' WARNING')
                print('Workworkshop "%s" has invalid item \'maximum\'.' % (
                    workshop,
                ))
                print('Skipping this entry for now.  Re-run `finish_install` to fix.')
                next

    # Done checking over individual vars.

    # Change ec2_client to this workshop's region
    ec2_client = boto3.client('ec2',
        region_name=config[workshop]['region'],
    )

    # Make sure we can access the launch template
    try:
        ec2_client.describe_launch_templates(LaunchTemplateIds=[config[workshop]['template']])
    except Exception as e:
        print(' WARNING')
        print('Unable to pull up the launch template for workworkshop "%s"' % (
            workshop,
        ))
        print('Skipping this entry for now.  Re-run `finish_install` to fix.')
        next

    # We have a good workshop!
    config_names_as_list.append(workshop)
    spinner.next()

# Done checking configuration
print(' Complete')

# We now have a list of workshops, and a working Boto3 client.
# Which workshop does the user wish to access?

print('')
print('The following workshops are available:')
for i in range(0, len(config_names_as_list)):
    print('%3d: %s' % (i, config_names_as_list[i]))
choice_index = -1
while choice_index == -1:
    try:
        choice_index = input('Please choose a number from 0 to %d: ' % (len(config_names_as_list)-1,))
    except (EOFError, KeyboardInterrupt):
        choice_index = 0
    try:
        choice_index = int(choice_index)
    # Make sure we have an integer in the range [0, len(config_names_as_list))
    except ValueError:
        print('Please enter a valid base 10 integer')
        choice_index = -1
        continue
    if choice_index < 0:
        print('Please enter a non-negative integer')
        choice_index = -1
    if choice_index >= len(config_names_as_list):
        print('Please enter an integer less than %d' % (len(config_names_as_list),))
        choice_index = -1

# Report the selection, or exit
if choice_index == 0:
    print('Goodbye')
    exit()
chosen_config = config_names_as_list[choice_index]
print('')
print('Selected workshop %s' % (chosen_config))
del choice_index
del config_names_as_list

# Do our final ec2_client re-creation
ec2_client = boto3.client('ec2',
    region_name = config[chosen_config]['region'],
)

# Before we get instance info, we need to set up the place to store the info.

# Since we're using a paginator, we'll be getting multiple pages of results.
# That means we can't simply do one mass transformation to build our dict.
instances = dict()
instances_by_state = list()
instances_by_creation = list()
instances_by_id = list()
instances_by_ip = list()

# Our default display is the "by-id" list.
display_list = instances_by_id


# Define a subroutine that fetches our instances
def load_instances(
    instances_dict,
    instances_by_state_list,
    instances_by_id_list,
    instances_by_creation_list,
    instances_by_ip_list,
    instance_filter,
):
    # First, clear everything
    instances_dict.clear()
    instances_by_state_list.clear()
    instances_by_id_list.clear()
    instances_by_creation_list.clear()
    instances_by_ip_list.clear()

    # Make a dict of instance states, to help in building the list later
    instances_by_state_dict = dict()

    # Let's grab a list of instances.
    print('Loading instance information…')
    instance_iterator = ec2_client.get_paginator('describe_instances').paginate(Filters=[
        {
            'Name': 'tag:Workshop',
            'Values': (chosen_config,),
        },
        {
            'Name': 'instance-state-name',
            'Values': instance_filter,
        },
    ])

    # Go through each page of results
    for page in instance_iterator:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                # First, add the instance to the main list
                instance_id = instance['InstanceId']
                instances_dict[instance_id] = instance

                # Next, add to the appropriate by-status entry
                instance_state = instance['State']['Name']
                if instance_state not in instances_by_state_dict:
                    instances_by_state_dict[instance_state] = list()
                instances_by_state_dict[instance_state].append(instance_id)

                # Store the ipaddress object in the instance
                instance_ip = None
                if 'PublicIpAddress' in instance:
                    instance_ip = ipaddress.IPv4Address(instance['PublicIpAddress'])
                instance['PublicIpAddress'] = instance_ip

                # Convert the time to the local time zone
                instance['LaunchTime'] = instance['LaunchTime'].astimezone(
                    dateutil.tz.gettz()
                )
                instance_creation = instance['LaunchTime']

                # Next, add to the by-creation, by_id, and by_ip lists
                instances_by_creation_list.append((
                    instance_creation,
                    instance_id
                ))
                instances_by_id_list.append((
                    instance_id,
                    instance_id,
                ))
                instances_by_ip_list.append((
                    0 if instance_ip is None else int(instance_ip),
                    instance_id
                ))
    # We have finished processing our `describe_instances` call!

    # Now, sort our lists
    for l in (
        instances_by_creation_list,
        instances_by_id_list,
        instances_by_ip_list,
    ):
        l.sort(
            key=lambda val: val[0]
        )

    # Merge the state dict entries into the state list, in our specific order.
    for state in ('pending', 'running', 'stopping', 'stopped', 'shutting-down', 'terminated'):
        if state in instances_by_state_dict:
            instances_by_state_list.extend(
                (state, instance_id) for instance_id in instances_by_state_dict[state]
            )

# Done with the instance-population sub! 


# Define a subroutine that prints our instance list
def print_list(
    display_list,
    instances_by_id_list,
    instances_by_creation_list,
    instances_by_ip_list,
    instances_by_state_list,
):
    # Output some stats
    print('')
#    print('%3d instances found!\n    %3d running\n    %3d stopped (or shutting down)\n    %3d terminated (or terminating)' % (
#        len(instances),
#        len(instances_by_state['running']),
#        len(instances_by_state['stopped']),
#        len(instances_by_state['terminated']),
#    ))

    # First, the header
    print('================================================================================')

    # How we list a column depends on if we're sorting by it
    header_id = '     Instance ID     '
    header_ip = '    Public IP    '
    header_creation = '      Created      '
    header_state = '     State     '
    print('   |%s|%s|%s|%s|' % (
        colored(header_id, attrs=['bold']) if display_list is instances_by_id_list else header_id,
        colored(header_ip, attrs=['bold']) if display_list is instances_by_ip_list else header_ip,
        colored(header_creation, attrs=['bold']) if display_list is instances_by_creation_list else header_creation,
        colored(header_state, attrs=['bold']) if display_list is instances_by_state_list else header_state,
    ))

    # Next, print the instances using whichever sorting method was selected
    for i in range(1, len(display_list)+1):
        # Each list contains tuples; the second item in the tuple is the instance ID.
        instance_id = display_list[i-1][1]
        instance = instances[instance_id]
        print('%3d| %19s | %15s | %17s | %13s |' % (
            i,
            instance_id,
            instance['PublicIpAddress'],
            instance['LaunchTime'].strftime('%a, %b %d %H:%M'),
            instance['State']['Name']
        ))
    #nnn: i-01137d37bc2f6c2ea | 123.456.789.012 | Mon, Jan 11 XX:XX | shutting-down |

    # Finally, print the footer
    print('================================================================================')


# Define a subroutine to work our what the user wants to do
def get_selection():
    # Get a selection from the user
    while True:
        try:
            response = input('Make a selection: ')
        except (EOFError, KeyboardInterrupt):
            response = 'q'

        # Immediately return on the clear responses
        if response in ('q', 'r', 'fr', 'fs', 'ft', 'si', 'sp', 'sc', 'ss'):
            return response

        # At this point, we have a range to parse out
        # (Using a set does de-duplication for us automatically!)
        response_list = set()

        # Fist, split on commas
        for comma_group in response.split(','):
            # Skip any empty group
            if comma_group == '':
                continue

            # Next, split up any hyphens
            hyphen_group = comma_group.split('-')
            if len(hyphen_group) == 1:
                # We didn't have a hyphen, so add one item
                try:
                    a = int(hyphen_group[0])
                except ValueError:
                    print('Could not parse "%s"' % (comma_group,))
                    response_list = list()
                    break
                response_list.add(a)
            elif len(hyphen_group) == 2:
                # We have a range to expand
                try:
                    a = int(hyphen_group[0])
                    b = int(hyphen_group[1])
                except ValueError:
                    print('Could not parse "%s-%s"' % (comma_group,))
                    response_list = ()
                    break
                response_list.update(set(range(a, b+1)))
            else:
                # We got something weird
                print('Could not parse %s' % (comma_group,))
                response_list = ()
                break

            # Done working on this comma group

        # If we didn't get any actual numbers, then ask again, else break
        if len(response_list) == 0:
            continue
        else:
            break

    # Done getting a response
    return response_list
# Done with the selection-getting code!


# Define a subroutine to destroy a set of instances
def destroy_instances(instance_list):

    # Print the warning, and give the user a change to abort.
    print('')
    print(
        colored('WARNING!!!', attrs=['bold']),
        '  You have decided to destroy the following instances:',
        sep=''
    )
    print_list(instance_list, list(), list(), list(), list())
    response = None
    while response is None:
        try:
            response = input('Are you sure you wish to proceed (y/n/q)? ')
        except (EOFError, KeyboardInterrupt):
            response = 'q'
        if response not in ('y', 'n', 'q'):
            response = None
    if response == 'q':
        print('Goodbye')
        exit()
    elif response == 'n':
        print('Taking no action.')
        return

    # OK, we're destroying some instances
    if len(instance_list) <= 0:
        print('No instances were actually specified!  Nothing to kill.')
    else:
        print('Requesting instance termination… ', end='')
        sys.stdout.flush()
        ec2_client.terminate_instances(InstanceIds=list(
            # The list we got is a list of tuples of (sort key, instance ID).
            # We need to extract the instance ID.
            x[1] for x in instance_list
        ))
        print('Complete')
    
# Done with the instance-destroying code!


# Now we have our "event loop"!

# First, make a note of what we're filtering on.
instance_filter = (
    'pending', 'running',
    'shutting-down', 'terminated',
    'stopping', 'stopped',
)

while True:

    # If our instance dict is empty, reload it
    if len(instances) == 0:
        load_instances(
            instances,
            instances_by_state_list=instances_by_state,
            instances_by_id_list=instances_by_id,
            instances_by_creation_list=instances_by_creation,
            instances_by_ip_list=instances_by_ip,
            instance_filter=instance_filter,
        )

    # Print the list, and our options
    print_list(
        display_list,
        instances_by_id_list=instances_by_id,
        instances_by_creation_list=instances_by_creation,
        instances_by_ip_list=instances_by_ip,
        instances_by_state_list=instances_by_state
    )
    print('                                                Current Time: %s' % (
        datetime.datetime.now(tz=dateutil.tz.gettz()).strftime('%a, %b %d %H:%M')
    ))
    print('(Terminated instances will clean up themselves after a few minutes...)')
    print('To destroy instances, enter a range of row numbers (use hyphens and commas)')
    print('Or enter one of the following commands:')
    print('  q  to quit')
    print('  r  to reload the list and reset the sort/filter')
    print('  To only show certain instances:')
    print('     fr to only show running instances')
    print('     fs ............ stopped instances')
    print('     ft ............ terminated instances')
    print('  To sort the results:')
    print('     si to sort by instance ID')
    print('     sp .......... public IP')
    print('     sc .......... creation date')
    print('     ss .......... status')

    # Find out what the user wants to do
    response = get_selection()

    # Start working on our selections

    if type(response) is set:
        # Translate the set into a list of instances
        destruction_list = list()
        for i in response:
            if i > 0 and i <= len(display_list):
                # NOTE: The lists we display are 1-indexed, but Python lists are 0-indexed.
                destruction_list.append(display_list[i-1])
        # Call the destruction code
        destroy_instances(destruction_list)
        # Clear our instance info, to trigger a reload
        instances.clear()
    elif response == 'q':
        break
    elif response == 'r':
        # Wipe our instance dict, for it to reload on the next loop
        instances.clear()
        # Reset the list of instances to display
        instance_filter = (
            'pending', 'running',
            'shutting-down', 'terminated',
            'stopping', 'stopped',
        )
        # Reset the sort
        display_list = instances_by_id

    # The filter options clear the instance dict and set a new filter.
    elif response == 'fr':
        instances.clear()
        instance_filter = (
            'pending', 'running',
        )
    elif response == 'fs':
        instances.clear()
        instance_filter = (
            'stopping', 'stopped',
        )
    elif response == 'ft':
        instances.clear()
        instance_filter = (
            'shutting-down', 'terminated',
        )


    # The sort options simply involve changing our display list
    elif response == 'si':
        display_list = instances_by_id
    elif response == 'sp':
        display_list = instances_by_ip
    elif response == 'sc':
        display_list = instances_by_creation
    elif response == 'ss':
        display_list = instances_by_state

    # We validated input in `get_selection()`, so we should never reach here
    else:
        print('Something went wrong!  Please make a new selection.')
        print('Got "%s" (a %s)' % (response, type(response)))

# Done with the event loop

# All done!
print('Goodbye')
exit()
