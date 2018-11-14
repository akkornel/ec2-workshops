**EC2 Workshop Manager** is a set of scripts to make it easy for you to spin up
multiple EC2 instances for a workshop.

Imagine you want to host a workshop, and part of the workshop involves having
people do labs or hands-on work (such as following along on their machines,
while you demonstrate something).  Although people are fairly likely to have a
laptop, you can't count on them running a specific OS, or having a specific
software stack available.

In situations like this, cloud providers have a good solution: You can create a
software image that includes an OS and all the software required for your
workshop.  Create as many instances as needed, using that image.  Attendees can
connect using SSH, X Windows, RDP, VNC, or whatever.

One of the downsides of this method is the work required to set up an
environment for the workshop machines, plus the work involved in launching the
instances, plus the clean up at the end.

These scripts assist in automating those busywork tasks.

# Requirements

Before you do anything in the _Setup_ instructions, you will need to have the
following ready:

* *Python 3.4+*.  These scripts are written for Python 3, and will use a `venv`
  to contain the required modules.  The modules will be set up as part of this
  guide, so the only prerequisite is that you have Python 3.4 or later.

* *The ability to create an IAM User*.  These scripts need an IAM User that has
  the `AmazonEC2FullAccess` policy applied.  This access is required because
  there will be a fair amount of work involved in creating and destroying VPCs
  (and related components), EC2 launch templates, and EC2 instances.

* *Increased EC2 Limits*.  AWS accounts have limits on how many resources they
  can consume.  Some limits are hard-coded and may not be changed; other limits
  may be increased with a support request.  [Read more about EC2 limits](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-resource-limits.html).

  You should consider requesting limit increases for the following resources:

  * The number of running instances, for the instance type(s) you will be
    using.

  * The number of VPCs.  Each workshop will use one VPC.

* *Network Connectivity*.  If people are bringing their own laptops, you will
  need to make sure there is good network connectivity in your workshop's
  location.  As a starting point, try planning on one in-sight access point for
  every 20 people (including yourself).  Include time for people to connect to
  wireless.

  If you will be hosting workshops regularly, consider joining
  [eduroam](https://www.eduroam.org).

If you are an education or research institution, you should consider applying
for a Data Egress Discount, especially if you plan on doing any workshops that
involve a large amount of data transfer out of EC2.  [Read about data egress](https://aws.amazon.com/blogs/publicsector/tag/data-egress/)

If you are a not-for-profit, and you are not charging people to attend a
workshop, you should also consider reaching out to your AWS Account Manager to
see if any AWS service credits are available.

# Setup

Setup is a three-step process:

1. Create an IAM User with full access to EC2.

2. Install Python 3.4 or later, either system-wide or in a module.  Create a
   venv.  Update `setup.sh` with any steps needed to make Python 3.4+
   available.

3. Run `finish_install` to install packages and check everything.

The latter two steps are detailed below.

If you "upgrade" by checking out a different version of this code, you should
re-run the last step.

## Create the environment

To begin, `cd` to the root of the Git checkout, and run `pythonXX -m venv
venv`.In place of `pythonXX`, specify the Python executable to use.  For
example, `python3.4` or `python3.6`.

The venv creation should run silently, and once complete, you should have a
`venv` directory in the root of your Git checkout!

Now, open the file at path `scripts/setup.sh`.  If you needed to do anything
special to make Python 3.x available for use, then you should add those
commands to the marked part of this script (search for `module load`).  This is
especially useful for environments where you have to load a module, or
otherwise modify `$PATH`.

Once you are done, close the file, and return to the root of the Git checkout
to finish installation.

## Run the setup program

To finish setup, go back to the root of the Git checkout and run
`finish_install`.  This script will make sure all the necessary packages are
installed into the venv, and will check your configuration.

If this is the first time you have run this script, you will be walked through
choosing a default region, and collecting AWS credentials.  If you have run
this script before, your region selection and credentials will be validated.

This script is safe to run multiple times, and you should run it every time you
do a `git pull` or a branch change.

# Create a Workshop

TBD

# Create Workshop Instances

Before you can create instances for a workshop, you need to complete all of the
steps in the _Setup_ and _Create a Workshop_ sections.

Once you have a workshop configured, and ready to use, you can go ahead and
create instances.  This uses the EC2 instance template that was created for
you, and which you customized with the identifier of the AMI that you created.

To create instances, run the `create_instances` script.  That will ask you for
a workshop (the workshop you created in the _Create a Workshop_ step), and ask
you how many instances you want to create.

Each workshop has a limit on how many instances can be created at one time.
(The limit was set in the _Create a Workshop_ step.)  If you need to create
more instanaces, then you will need to run this script multiple times.  You may
safely run this script multiple times in separate windows (or `screen`
sessions, etc.).

Once instances are launched (powering up), you will be given the unique EC2
instance IDs for all of the instances.  Then, the script will wait for the
instances to power on, and for EC2's instance and system status checks to pass.

At the end of the process, you will get a list of IP addresses of all the
instances which were able to power on and pass status checks.

Instances are given five minutes to power on, and a further five minutes to
pass EC2's status checks.  If an instance powers off, fails a status check, or
fails to meet the five-minute time limit, then a warning will be displayed.
The warning will include the unique EC2 instance ID of the problem instance,
and you will not get that instance's IP address.

If any instances had problems, then the number of IP addresses displayed will
be less than the number you requested.  In that case, you will need to run this
script again.  You can use the `destroy_instances` script to destroy any
instances that had problems.

# Destroy Workshop Instances

Once your workshop has wrapped up, you should destroy the instances you
created.  You can do this with the `destroy_instances` script.

After asking you to select a workshop, the script will display a list of
instances, and ask you which ones to terminate.  Each instance will show its
unique EC2 Instance ID, the time it was created, and the instance's current
status.  Running instances will also display the instance's public IP address.
Times will be displayed, if possible, using the system time zone, or (if the
`TZ` environment variable is set) your preferred time zone, or UTC.  The
current time will also be displayed, for comparison.

You will have options to filter the list to only show instances in a specific
state, and you can also sort the list by any of its columns.

To destroy instances, provide a list of row numbers.  Numbers can be listed
individually (for example, `1,2,3`), or as a range (`1-4`), or both
(`1,2,4-6`).

You will be given one opportunity to confirm the list, before instance
termination begins.  **Once instance termination begins, it may not be
stopped!**

Terminated instances will remain in the list for some time, until EC2 cleans
them up.

# Destroy a Workshop

TBD

# License

The contents of this repository are Copyright © 2018 The Board of Trustees of
the Leland Stanford Junior University.

All of the code—with the exception of example code—is licensed under the [GNU
General Public License, Version 3](LICENSE).  Documentation (including
documentation embedded in code) is licensed under the [Creative Commons
Attribution-ShareAlike 3.0 Unported](LICENSE.cc-by-sa-3) license.  All examples
(example code, example configuration, etc.) are licensed under the [Creative
Common CC0 1.0 Universal](LICENSE.cc0) license.
